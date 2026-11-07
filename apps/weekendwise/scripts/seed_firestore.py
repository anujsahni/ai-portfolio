#!/usr/bin/env python3
"""MVP-04: load data/seed/ into Firestore with Vertex AI embeddings (`make seed`).

Runs as the weekendwise-ingest service account (impersonated; no key files).
Idempotent: unchanged documents aren't rewritten and unchanged chunks aren't re-embedded.

Usage:
  python scripts/seed_firestore.py --index-dimension 768 [--dry-run] [--include-fixtures]
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from weekendwise import seed  # noqa: E402
from weekendwise.config import load_settings  # noqa: E402
from weekendwise.errors import WeekendWiseError  # noqa: E402
from weekendwise.gcp import firestore_client, service_account  # noqa: E402
from weekendwise.vertex import VertexClient  # noqa: E402

BATCH_LIMIT = 400  # Firestore allows 500 writes per batch


def read_existing(db, collections: list[str]) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {}
    for coll in collections:
        out[coll] = {}
        for snap in db.collection(coll).stream():
            data = snap.to_dict() or {}
            vec = data.get("embedding")
            if vec is not None and not isinstance(vec, list):
                data["embedding"] = list(vec)  # Firestore Vector -> list
            out[coll][snap.id] = data
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--index-dimension", type=int, required=True, help="dimension of the Firestore vector index (terraform output)")
    parser.add_argument("--dry-run", action="store_true", help="show what would change; no embeddings, no writes")
    parser.add_argument("--include-fixtures", action="store_true", help="also load trip_scenarios, sample_itineraries, evaluation_cases")
    args = parser.parse_args()

    try:
        settings = load_settings()
        if settings.embedding_dimension != args.index_dimension:
            print(f"✗ VERTEX_EMBEDDING_DIMENSION is {settings.embedding_dimension} but the Firestore vector index is "
                  f"{args.index_dimension}. Make them match (see guide 04) before seeding.")
            return 1
        ingest_sa = service_account(settings.project_id, "ingest")
        model, dim = settings.embedding_model_id, settings.embedding_dimension
        collections = seed.RUNTIME_COLLECTIONS + (seed.FIXTURE_COLLECTIONS if args.include_fixtures else [])

        print(f"project:    {settings.project_id}  (database (default))")
        print(f"identity:   {ingest_sa}")
        print(f"embeddings: {model} @ {settings.embedding_location}, {dim} dimensions")
        print(f"mode:       {'DRY RUN (nothing is written)' if args.dry_run else 'write'}\n")

        desired = seed.load_seed(ROOT / "data" / "seed", collections)
        db = firestore_client(settings.project_id, impersonate=ingest_sa)
        existing = read_existing(db, collections)
        plan = seed.plan_sync(desired, existing, model, dim)

        print(f"{'collection':<20}{'new':>6}{'update':>8}{'same':>7}{'delete':>8}")
        for coll, p in plan.collections.items():
            print(f"{coll:<20}{len(p.create):>6}{len(p.update):>8}{len(p.unchanged):>7}{len(p.delete):>8}")
        print(f"\nchunks to embed: {len(plan.to_embed)}   stored vectors reused: {len(plan.reuse_embedding)}")

        if not plan.has_changes:
            print("\n✓ Firestore already matches data/seed/. Nothing to do.")
            return 0
        if args.dry_run:
            print("\nDry run complete. Run without DRY_RUN=1 to apply.")
            return 0

        # Embed only what changed.
        vectors: dict[str, list[float]] = {}
        if plan.to_embed:
            vertex = VertexClient(replace(settings, impersonate_service_account=ingest_sa))
            chunks = desired[seed.CHUNKS]
            start = time.monotonic()
            values = vertex.embed_documents([seed.embedding_input(chunks[i]) for i in plan.to_embed])
            vectors.update(zip(plan.to_embed, values))
            print(f"✓ embedded {len(values)} chunks in {time.monotonic() - start:.1f}s")
        for cid in plan.reuse_embedding:
            vectors[cid] = existing[seed.CHUNKS][cid]["embedding"]

        # Write in batches.
        from google.cloud import firestore
        from google.cloud.firestore_v1.vector import Vector

        batch, pending, written, deleted = db.batch(), 0, 0, 0

        def flush():
            nonlocal batch, pending
            if pending:
                batch.commit()
                batch, pending = db.batch(), 0

        for coll, p in plan.collections.items():
            for doc_id in p.create + p.update:
                doc = seed.build_document(coll, desired[coll][doc_id], vector=vectors.get(doc_id), model=model, dimension=dim)
                if coll == seed.CHUNKS:
                    doc["embedding"] = Vector(doc["embedding"])
                doc["seededAt"] = firestore.SERVER_TIMESTAMP
                batch.set(db.collection(coll).document(doc_id), doc)
                pending, written = pending + 1, written + 1
                if pending >= BATCH_LIMIT:
                    flush()
            for doc_id in p.delete:
                batch.delete(db.collection(coll).document(doc_id))
                pending, deleted = pending + 1, deleted + 1
                if pending >= BATCH_LIMIT:
                    flush()
        flush()

        summary = {
            "finishedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "embeddingModel": model,
            "embeddingDimension": dim,
            "collections": {c: {"new": len(p.create), "update": len(p.update), "same": len(p.unchanged), "delete": len(p.delete)}
                            for c, p in plan.collections.items()},
            "chunksEmbedded": len(plan.to_embed),
            "vectorsReused": len(plan.reuse_embedding),
            "seededBy": seed.SEEDED_BY,
        }
        db.collection("ingestion_runs").document("latest").set(summary)
        print(f"✓ wrote {written} documents, deleted {deleted}; summary saved to ingestion_runs/latest")
        print("\nNext: make verify  (includes a sample search per city)")
        return 0
    except WeekendWiseError as err:
        print(f"\n✗ {type(err).__name__}: {err.message}")
        if err.hint:
            print(f"  Next step: {err.hint}")
        return 1
    except Exception as err:  # noqa: BLE001 - show a safe, short message
        name = type(err).__name__
        hint = "Check that make apply has run and new permissions have had a minute to apply."
        if "PermissionDenied" in name or "403" in str(err)[:40]:
            hint = "weekendwise-ingest or your impersonation grant may be missing: run make apply, wait 1–2 minutes, retry."
        print(f"\n✗ {name} while seeding Firestore. {hint}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

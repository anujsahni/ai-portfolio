"""Plan an idempotent sync of data/seed/ into Firestore (MVP-04).

Pure functions only (no network), so the sync rules are unit-tested:
- A document is written only if it is new or its seed content changed.
- A guide chunk is re-embedded only if its text, title, embedding model, or dimension changed;
  otherwise the stored vector is reused.
- Documents previously written by `make seed` that no longer exist in data/seed/ are deleted.
  Documents written by anything else are never touched.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

SEEDED_BY = "make seed"
CHUNKS = "guide_chunks"

# Read by the app at runtime.
RUNTIME_COLLECTIONS = [
    "app_config", "cities", "interests", "budget_categories", "local_conditions",
    "guide_sources", "guide_chunks", "corpus_manifests",
]
# Test/demo fixtures: stay in the repo unless explicitly requested.
FIXTURE_COLLECTIONS = ["trip_scenarios", "sample_itineraries", "evaluation_cases"]

# Fields added by the seeder (excluded from the content checksum).
SEED_META = {"seedChecksum", "seededBy", "seededAt"}
EMBED_FIELDS = {"embedding", "embeddingModel", "embeddingDimension", "embeddingStatus", "embedChecksum"}


def load_seed(seed_dir: Path, collections: list[str]) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {}
    for coll in collections:
        folder = seed_dir / coll
        if not folder.is_dir():
            raise FileNotFoundError(f"{folder} is missing; run python3 scripts/build_seed_data.py")
        out[coll] = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))}
    return out


def content_checksum(data: dict) -> str:
    clean = {k: v for k, v in data.items() if k not in SEED_META | EMBED_FIELDS}
    return hashlib.sha256(json.dumps(clean, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def embedding_input(chunk: dict) -> str:
    """Text sent to the embedding model: the guide title gives each paragraph context."""
    return f"{chunk['title']}\n\n{chunk['text']}"


def embed_checksum(chunk: dict, model: str, dimension: int) -> str:
    return hashlib.sha256(f"{model}|{dimension}|{embedding_input(chunk)}".encode()).hexdigest()


@dataclass
class CollectionPlan:
    create: list[str] = field(default_factory=list)
    update: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    delete: list[str] = field(default_factory=list)


@dataclass
class SyncPlan:
    collections: dict[str, CollectionPlan]
    to_embed: list[str]      # chunk IDs needing new vectors
    reuse_embedding: list[str]  # chunk IDs whose stored vector is still valid and will be written again

    @property
    def has_changes(self) -> bool:
        return any(p.create or p.update or p.delete for p in self.collections.values())


def plan_sync(desired: dict[str, dict[str, dict]], existing: dict[str, dict[str, dict]], model: str, dimension: int) -> SyncPlan:
    """Compare seed files with what's in Firestore. `existing` holds the stored documents' fields."""
    plans: dict[str, CollectionPlan] = {}
    to_embed: list[str] = []
    reuse: list[str] = []
    for coll, docs in desired.items():
        plan = CollectionPlan()
        stored = existing.get(coll, {})
        for doc_id, data in docs.items():
            current = stored.get(doc_id)
            content_changed = current is None or current.get("seedChecksum") != content_checksum(data)
            needs_vector = False
            if coll == CHUNKS:
                needs_vector = (
                    current is None
                    or current.get("embedChecksum") != embed_checksum(data, model, dimension)
                    or not current.get("embedding")
                )
            if current is None:
                plan.create.append(doc_id)
            elif content_changed or needs_vector:
                plan.update.append(doc_id)
            else:
                plan.unchanged.append(doc_id)
            if coll == CHUNKS and (current is None or content_changed or needs_vector):
                (to_embed if needs_vector else reuse).append(doc_id)
        plan.delete = sorted(i for i, d in stored.items() if i not in docs and d.get("seededBy") == SEEDED_BY)
        plans[coll] = plan
    return SyncPlan(plans, to_embed, reuse)


def build_document(coll: str, data: dict, *, vector: list[float] | None, model: str, dimension: int) -> dict:
    """Fields to write. For chunks, `vector` is the new or reused embedding values."""
    doc = {k: v for k, v in data.items() if k not in EMBED_FIELDS}
    doc["seedChecksum"] = content_checksum(data)
    doc["seededBy"] = SEEDED_BY
    if coll == CHUNKS:
        if vector is None or len(vector) != dimension:
            raise ValueError(f"chunk {data.get('chunkId')} needs a {dimension}-dimension vector")
        doc.update({
            "embedding": vector,  # converted to a Firestore Vector by the writer
            "embeddingModel": model,
            "embeddingDimension": dimension,
            "embeddingStatus": "ready",
            "embedChecksum": embed_checksum(data, model, dimension),
        })
    return doc

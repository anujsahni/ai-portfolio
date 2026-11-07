#!/usr/bin/env python3
"""IAC-04 check: Firestore database, vector index, and runtime read access.

- (default) database exists, Native mode, in the expected location, delete protection on
- guide_chunks vector index (cityId, active, embedding) is READY with the configured dimension
- the dimension matches VERTEX_EMBEDDING_DIMENSION in .env
- weekendwise-run can read guide_chunks (a count query; nothing is written)

Usage: python scripts/verify_firestore.py PROJECT_ID [EXPECTED_LOCATION]
"""
from __future__ import annotations

import sys
from pathlib import Path

import google.auth
from google.auth import impersonated_credentials
from google.auth.transport.requests import AuthorizedSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from weekendwise.config import read_dotenv  # noqa: E402

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
COLLECTION = "guide_chunks"


def main(project: str, expected_location: str | None) -> int:
    base = f"https://firestore.googleapis.com/v1/projects/{project}/databases/(default)"
    source, _ = google.auth.default(scopes=SCOPES, quota_project_id=project)
    admin = AuthorizedSession(source)
    failures = 0

    def check(ok: bool, good: str, bad: str) -> None:
        nonlocal failures
        print(f"{'✓' if ok else '✗'} {good if ok else bad}")
        failures += 0 if ok else 1

    # Database
    r = admin.get(base, timeout=30)
    if r.status_code == 404:
        print("✗ Firestore (default) database not found. Run: make apply")
        return 1
    r.raise_for_status()
    db = r.json()
    loc, mode, protection = db.get("locationId"), db.get("type"), db.get("deleteProtectionState")
    check(mode == "FIRESTORE_NATIVE", f"database (default): Native mode, {loc}", f"database type is {mode}, expected FIRESTORE_NATIVE")
    if expected_location:
        check(loc == expected_location, f"location matches region ({loc})", f"location is {loc}, expected {expected_location}")
    check(protection == "DELETE_PROTECTION_ENABLED", "delete protection: on", f"delete protection is {protection}; expected on")

    # Vector index
    r = admin.get(f"{base}/collectionGroups/{COLLECTION}/indexes", timeout=30)
    r.raise_for_status()
    vector_indexes = []
    for idx in r.json().get("indexes", []):
        fields = idx.get("fields", [])
        vec = next((f for f in fields if "vectorConfig" in f), None)
        if vec:
            vector_indexes.append((idx, [f["fieldPath"] for f in fields if f.get("fieldPath") != "__name__"], int(vec["vectorConfig"]["dimension"])))
    if not vector_indexes:
        check(False, "", f"no vector index on {COLLECTION}. Run: make apply")
    for idx, paths, dim in vector_indexes:
        state = idx.get("state")
        label = f"vector index on {COLLECTION} ({' + '.join(paths)}), dimension {dim}"
        if state == "CREATING":
            print(f"… {label}: still CREATING (can take several minutes; rerun make verify)")
            failures += 1
        else:
            check(state == "READY", f"{label}: READY", f"{label}: {state}")
        env_dim = read_dotenv(Path(".env")).get("VERTEX_EMBEDDING_DIMENSION")
        if env_dim:
            check(int(env_dim) == dim, f"matches VERTEX_EMBEDDING_DIMENSION in .env ({env_dim})",
                  f"index dimension {dim} ≠ VERTEX_EMBEDDING_DIMENSION {env_dim} in .env")

    # Runtime read access (count query as weekendwise-run; nothing is written)
    run_sa = f"weekendwise-run@{project}.iam.gserviceaccount.com"
    run = AuthorizedSession(impersonated_credentials.Credentials(source_credentials=source, target_principal=run_sa, target_scopes=SCOPES))
    body = {"structuredAggregationQuery": {"structuredQuery": {"from": [{"collectionId": COLLECTION}]},
                                           "aggregations": [{"alias": "n", "count": {}}]}}
    r = run.post(f"{base}/documents:runAggregationQuery", json=body, timeout=30)
    if r.ok:
        rows = [x for x in r.json() if "result" in x]
        n = int(rows[0]["result"]["aggregateFields"]["n"]["integerValue"]) if rows else 0
        print(f"✓ weekendwise-run can read {COLLECTION}: {n} documents" + ("  (empty until make seed)" if n == 0 else ""))
    else:
        check(False, "", f"weekendwise-run could not read {COLLECTION} (HTTP {r.status_code})")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None))

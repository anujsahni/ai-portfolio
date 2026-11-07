# MVP-03 Cloud Run smoke test — 2026-11-06T22:57:40+00:00

Service `weekendwise` in `projects/weekendwise-demo-jytx/locations/us-central1/services/weekendwise/revisions/weekendwise-00002-cgp`, image tag `20261106-224657`. Run by `make smoke-cloud`. The service URL is kept out of this file.

| Check | Result | Detail |
|---|---|---|
| min instances is 0 (scale to zero) | ✅ | 0 |
| max instances is bounded | ✅ | 2 |
| runs as the dedicated runtime identity | ✅ | weekendwise-run |
| app image deployed (not the placeholder) | ✅ | tag 20261106-224657 |
| private: a request without a token is rejected | ✅ | HTTP 403 |
| /health answers as you | ✅ | HTTP 200, 0.2s incl. any cold start, version 20261106-224657 |
| reported version matches the deployed tag | ✅ | 20261106-224657 vs 20261106-224657 |
| /readyz: Firestore readable as weekendwise-run | ✅ | {"status":"ready","detail":"ok","version":"20261106-224657"} |
| live plan through Cloud Run (Vertex AI + Firestore as weekendwise-run) | ✅ | 18.5s, 5 steps, 1 model call(s), 7 citations, budget ON TRACK, request 22227161aa784bd3 |

Runtime identity can't write Firestore: proven by `make verify` (scripts/verify_iam.py, IAC-03).

# IAC-04 — Firestore database and vector index with Terraform

**Type:** Infrastructure as code + data  
**Priority:** P0  
**Estimate:** 3–5 hours  
**Story points:** 3 (database, composite vector index, and teardown behavior)  

## User story

As the WeekendWise backend, I want the Firestore database and the vector index created by Terraform so that retrieval works the same way every time the environment is rebuilt.

## Scope

In `infra/stack/`:

- `google_firestore_database` named `(default)`, Native mode, in the configured location. Set its delete protection and deletion policy from variables so `make destroy` can really delete it (the provider default may only abandon it).
- `google_firestore_index` on collection `guide_chunks`: ascending `cityId`, ascending `active`, and the vector field `embedding` with `dimension = var.embedding_dimension` (flat index). This supports the city/active pre-filtered nearest-neighbor query in MVP-05.
- Fail the plan if `embedding_dimension` is unset or over Firestore's current maximum.
- Output the database ID and index name for app configuration.
- Seed loading stays in application code (`make seed`, MVP-04). Terraform does not write documents.

**Out of scope:** named (non-default) databases, Firestore security rules for browser clients (the browser never talks to Firestore), backups and PITR, and Vertex AI Vector Search.

## Acceptance criteria

- [x] `make apply` creates the `(default)` database and the composite vector index; `make verify` reports the index as READY.
- [x] Changing `embedding_dimension` plans a replacement of the index (not a silent mismatch).
- [ ] `make destroy` removes the index and the database (or clearly documents any platform delay before `(default)` can be recreated).
- [ ] After `make apply` + `make seed`, a known query returns expected source IDs (checked in MVP-05 tests).
- [x] Guide 04 is updated to describe Terraform as the provisioning path, with the console steps kept as a reference.

## Dependencies and deliverables

**Dependencies:** IAC-02, and the embedding dimension confirmed in MVP-02.  
**Deliverables:** `infra/stack/firestore.tf`, outputs, and verify checks.

## Completion evidence

`make verify` output with database location, index state READY, and vector dimension.

## Completion record (2026-11-06) ✅ Done

- `infra/stack/firestore.tf`: `(default)` database (Native, Standard, `us-central1`, delete protection on, `deletion_policy = DELETE`) and the composite vector index on `guide_chunks` (`cityId` ASC, `active` ASC, `embedding` flat 768). Plan: 2 to add.
- `embedding_dimension` defaults to 768, is validated as 1–2048, and changing it replaces the index.
- `make destroy` / `make destroy-all` now lift delete protection (targeted apply), then destroy.
- `scripts/verify_firestore.py` (run by `make verify`) checks mode, location, protection, that the index is READY with the right dimension, that it matches `.env`, and a count query as `weekendwise-run`.
- Guides 00 and 04 updated.
- Owner ran `make apply` (2 added). The first `make verify` found drift: Firestore inserts a `__name__` ASC field before the vector field, so Terraform wanted to rebuild the index on every plan. Fixed by declaring `__name__` explicitly; no re-apply was needed.
- `make verify` now passes: Native mode in `us-central1`, delete protection on, index READY at dimension 768 (matches `.env`), and `weekendwise-run` can read `guide_chunks` (0 documents before seeding).
- The known-query check runs after `make seed` (MVP-04/MVP-05). Destroy/recreate is covered by IAC-06's full-cycle rehearsal.

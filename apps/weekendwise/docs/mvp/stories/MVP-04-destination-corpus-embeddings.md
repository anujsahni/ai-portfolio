# MVP-04 — Firestore destination corpus and vector index

**Type:** Google Cloud data setup + ingestion  
**Priority:** P0  
**Estimate:** 5–8 hours  
**Story points:** 5 (four-city corpus ingestion and embeddings via `make seed`; database, index, and IAM are in IAC-03/IAC-04)  

## User story

As a traveler, I want destination-guide passages and their embeddings stored in a shared managed database so that the online app can retrieve grounded recommendations without bundling its vector data into every application container.

## Scope

> The Firestore database, composite vector index, and the separate ingestion/runtime identities are provisioned by [IAC-03](IAC-03-service-identities-iam.md) and [IAC-04](IAC-04-firestore-database-vector-index.md). This story delivers the corpus and the `make seed` ingestion command.


- Create the default Firestore Standard database in the selected region and use a `guide_chunks` collection for the MVP corpus.
- Create an original or synthetic Markdown corpus for each supported city (San Francisco, Portland, Santa Cruz, and Napa Valley), with at least 10 documents per city.
- In every city, cover neighborhoods, attractions, transit, accessibility, food/coffee, every interest offered in the UI, weather planning, approximate price ranges, and caveats to verify hours/prices.
- Include one stale/conflicting example and one unsupported request for evaluation.
- Chunk documents with stable IDs and metadata; generate embeddings with the Vertex AI model configured in MVP-02; upsert text, vector, source metadata, city, and active/version fields into Firestore.
- Create the required Firestore vector index and any composite vector index needed for city/active pre-filters.
- Make ingestion repeatable/idempotent. Keep corpus source Markdown and ingestion manifest in the repository; Firestore is the query store.
- Use a separate ingestion/developer identity for writes. Cloud Run uses read-only Firestore access.
- Document provenance and review date for each source.

**Out of scope:** scraping copyrighted travel guides, private customer data, live web search, multi-tenant onboarding, automated background ingestion, Firestore chat/session storage, Vertex AI Vector Search, or authoritative live prices/hours.

## Acceptance criteria

- [x] The repository contains at least 10 clearly identified guide documents per supported city, with source ID, city, section/title, and last-reviewed metadata, and at least one guide per city for every UI interest.
- [x] Each document is original/synthetic or has documented permission/attribution for demo use; no copied long-form copyrighted guide content is included.
- [x] Firestore setup guide documents creation of the default database in the chosen region, collection/document schema, vector index, IAM, verification, and cleanup.
- [x] Chunking produces stable document/chunk IDs and preserves enough metadata to render source citations.
- [x] The ingestion command uses the configured Vertex AI embedding model and writes vectors as Firestore vector values; it fails clearly if dimensions do not match the configured vector index.
- [x] Re-running ingestion on unchanged input is idempotent and does not create duplicate chunks; changed content/model versions refresh the corresponding documents and index as documented.
- [x] Runtime service identity is read-only for Firestore data; corpus writes are performed by an explicitly separate setup/ingestion identity.
- [x] Firestore data remains within the documented MVP size and vector dimension limits; the configured embedding dimension is confirmed against current Firestore limits.
- [x] Sample queries map to expected document IDs; unrelated/out-of-corpus requests are represented.

## Dependencies and deliverables

**Dependencies:** MVP-02, IAC-03, and IAC-04.  
**Deliverables:** [synthetic guide corpus](../../../data/README.md), Firestore collection/index configuration, pinned `google-cloud-firestore` dependency, ingestion/upsert command, corpus manifest, source/provenance notes, and [Firestore setup guide 04](../guides/04-firestore-vector-search.md).

## Completion evidence

Include a small corpus manifest and ingestion summary (document/chunk counts, model ID, vector dimension, Firestore database/region, index state). Confirm a known seeded chunk can be read by the runtime identity and cannot be written/deleted by it. Do not publish unlicensed source material.

## Completion record (2026-11-06) ✅ Done

**Ingestion summary**

| Item | Value |
|---|---|
| Project / database / region | `weekendwise-demo-jytx` / `(default)` / `us-central1` |
| Embedding model / dimension | `gemini-embedding-001` / 768 (index READY at 768) |
| Sources / chunks | 47 guides (17 SF, 10 Portland, 10 Santa Cruz, 10 Napa Valley) / 95 chunks |
| Documents written | 175 across 8 runtime collections; 95 chunks embedded in 3.8 s |
| Second run | `✓ Firestore already matches data/seed/. Nothing to do.` (0 embedded, 0 written) |
| Identity | Written as `weekendwise-ingest` (impersonated, no key); `weekendwise-run` can read only (IAC-03 check) |

**Sample searches** (as `weekendwise-run`, top 3, cosine): 7 of 7 passed. SFMOMA, rainy-day, Portland Pearl, Santa Cruz West Cliff, and Napa tasting each ranked first for their city; the inactive `SF-RETIRED-CABLECAR` and the Portland guide never appeared in San Francisco results.

**Safeguards checked:** a dimension mismatch stops before any work (`VERTEX_EMBEDDING_DIMENSION is 768 but the Firestore vector index is 512`). 8 offline tests cover create, no-op, re-embed on text/model/dimension change, vector reuse on metadata change, and deleting only seeder-owned documents.

**For MVP-05:** on-topic matches scored 0.25–0.31; off-topic queries still return neighbours at about 0.32–0.40. A distance threshold must be calibrated so weak matches become "insufficient evidence."

Code: `weekendwise/seed.py`, `weekendwise/gcp.py`, `scripts/seed_firestore.py`, `scripts/check_retrieval.py`, `tests/test_seed.py`; `google-cloud-firestore==2.34.1` pinned.

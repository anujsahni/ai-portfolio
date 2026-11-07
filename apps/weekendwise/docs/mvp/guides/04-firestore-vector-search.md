# Setup guide 04 — Firestore vector database and retrieval

**Related stories:** [MVP-04](../stories/MVP-04-destination-corpus-embeddings.md), [MVP-05](../stories/MVP-05-grounded-retrieval-citations.md)  
**Purpose:** Store destination-guide chunks and Vertex AI embeddings in Firestore Standard, then query them with Firestore nearest-neighbor vector search.

> **Provisioning is automated.** Create, change, and delete these resources only with Terraform; see [how-to 00](00-provision-with-terraform.md) (IAC-03, IAC-04). This guide is kept as a console reference for understanding and inspecting what Terraform created. Making changes here by hand causes drift.

## Data flow

1. Source Markdown remains in the project repository.
2. An authorized ingestion command chunks the guides, calls Vertex AI embeddings, and writes chunk text, metadata, and vector values to Firestore.
3. On a user request, Cloud Run calls Vertex AI to embed the query, then uses Firestore vector search to retrieve a small set of matching chunks.
4. The backend passes those chunks to Gemini and returns citations. The browser does not access Firestore directly.

Firestore stores and searches vectors; it does not generate them. Vertex AI is the embedding service.

## What Terraform creates (IAC-04)

`make apply` creates, from [infra/stack/firestore.tf](../../../infra/stack/firestore.tf):

| Resource | Setting |
|---|---|
| Firestore database | `(default)`, Native mode, Standard edition, project region (`us-central1`), delete protection **on** |
| Composite vector index | Collection `guide_chunks`: `cityId` ASC, `active` ASC, `__name__` ASC, `embedding` vector (flat, **768** dimensions). Firestore always adds `__name__` before the vector field, so the Terraform declares it too. |

The retriever (MVP-05) filters on `cityId` (not the display field `city`) and `active`, then runs nearest-neighbour search on `embedding`. The index dimension comes from the stack variable `embedding_dimension` and must equal `VERTEX_EMBEDDING_DIMENSION` in `.env`; `make verify` checks both match and that the index is READY. Changing the dimension replaces the index and requires re-running `make seed`.

Identities (IAC-03): `weekendwise-run` can only read; `weekendwise-ingest` writes the corpus via `make seed`. Sections 1–4 below describe the same setup in console terms, for reference.

## Before you start

- Complete [Guide 01](01-project-and-billing.md) and [Guide 02](02-vertex-ai.md).
- Confirm project ID, Firestore region, Vertex embedding model ID, and its actual output dimension.
- The MVP uses a small synthetic corpus for four cities (San Francisco, Portland, Santa Cruz, and Napa Valley). Do not put personal/customer documents in it.
- Confirm Firestore vector search, the selected location, and the Python client library are currently supported for your configuration. Review the current pricing page; vector-index reads and document storage/operations can be billable.

## 1. Create the Firestore database

1. In Google Cloud Console, select the demo project and open **Firestore → Databases**.
2. Choose **Create database**. For this single-project demo, use the default database ID (`(default)`) so it can be eligible for the default-database free quota described on the pricing page. Do not create a named database unless there is a specific need; named databases do not receive that free quota.
3. Select **Firestore in Native mode** and the selected region. Database location is a consequential choice and is not changed by this guide; keep it compatible with Cloud Run and Vertex AI locations where supported.
4. Choose the recommended production security posture for the project. The MVP backend accesses Firestore using server-side IAM credentials. Do not expose Firestore client credentials to the browser or open database access to unauthenticated clients.
5. Enable the Cloud Firestore API if prompted.

## 2. Grant separate identities

1. Use a dedicated Cloud Run runtime service account. Grant it the least-privilege Firestore read permission needed by the server retriever (verify the current predefined IAM role for read-only access); also grant only the Vertex AI invocation permission required by MVP-02 and logging permission if needed.
2. Use a separate ingestion identity for corpus writes. It needs permission to write/read the target database and call the selected Vertex embedding model. For the initial setup, an approved developer identity may run the one-time importer; do not download or commit a service-account key. For repeatable team use, use service-account impersonation or an approved workload identity pattern.
3. Do not grant the public web user direct Firestore access. The backend derives the allowed city/data scope and enforces query filters.

## 3. Define the collections and fields

Use stable IDs so re-ingestion updates documents rather than duplicating them:

- `guide_sources/{sourceId}` — `city`, `title`, `sourceUri` (repository-relative or safe demo reference), `version`, `lastReviewed`, `active`, and `checksum`.
- `guide_chunks/{chunkId}` — `sourceId`, `city`, `title`, `section`, `chunkIndex`, `text`, `active`, `version`, `embeddingModel`, and `embedding` (Firestore vector value).

Store the model ID/vector dimension in ingestion metadata. Ensure every vector has exactly the configured dimension, within Firestore’s documented maximum (currently 2,048 dimensions). Do not store API credentials or private user history in these collections.

## 4. Create the required vector index

A vector index is required before nearest-neighbor queries can run. For city/active pre-filtering, create a **composite vector index** containing the fields used by the query plus the vector field.

Console workflow (labels can change):

1. Open **Firestore → Databases**, select `(default)`, and open **Indexes**.
2. Choose the manual index tab and **Create Index** / **Create vector index**.
3. Set collection ID to `guide_chunks`, vector field to `embedding`, and dimensions to the exact output dimension from Guide 02.
4. Add ascending index fields for the equality filters used by the retriever, such as `city` and `active`, if using those pre-filters. Match the actual query; unnecessary index fields increase setup and storage overhead.
5. Create the index and wait until it is ready (green/ready state) before running retrieval tests.

If the console requires a composite vector index or the query reports a missing index, follow the suggested index configuration in the error/current documentation and record the resulting index definition in the repository. Avoid hand-editing a guessed dimension.

## 5. Ingest and validate the corpus

Run `make seed` ([how-to 00, Step 9](00-provision-with-terraform.md)). It:

1. rebuilds and validates `data/seed/` from `data/guides/` (`scripts/build_seed_data.py`),
2. checks that `VERTEX_EMBEDDING_DIMENSION` equals the Firestore index dimension (from Terraform),
3. impersonates `weekendwise-ingest` and reads what's already in Firestore,
4. embeds only new or changed chunks (title plus paragraph, `RETRIEVAL_DOCUMENT`, 768 dimensions),
5. writes documents in batches with `seedChecksum`, `seededBy`, and, for chunks, `embedding` (Firestore Vector), `embeddingModel`, `embeddingDimension`, and `embedChecksum`,
6. deletes documents it wrote earlier that are no longer in `data/seed/`, and never touches anything else,
7. saves a summary to `ingestion_runs/latest`.

`make verify` then runs seven sample searches as `weekendwise-run`: each city finds its expected guide, inactive chunks never appear, and the city filter holds. Code: [scripts/seed_firestore.py](../../../scripts/seed_firestore.py), [weekendwise/seed.py](../../../weekendwise/seed.py), [scripts/check_retrieval.py](../../../scripts/check_retrieval.py).

**Distance cut-off (MVP-05):** calibrated on the 28 non-city cases in `data/retrieval_cases.json` with `scripts/check_retrieval.py --calibrate`. Every expected guide ranked first at cosine distance **≤ 0.306**; the closest match for every off-topic question was **≥ 0.386**. `RETRIEVAL_MAX_DISTANCE` is set to **0.34**; passages farther away are dropped, and if none remain the answer is "insufficient evidence." Re-calibrate after changing the embedding model or adding many guides.

## 5b. Grounded answers and citations (MVP-05)

Code: [weekendwise/retrieval.py](../../../weekendwise/retrieval.py) and [weekendwise/citations.py](../../../weekendwise/citations.py).

| Step | What happens |
|---|---|
| 1. Check the city | Unsupported cities (e.g. `tokyo`) stop immediately: no embedding call, no Firestore query |
| 2. Search | Embed the question, then one Firestore query: `cityId == city AND active == true`, nearest on `embedding`, top 4 (never more than 5), 10 s timeout |
| 3. Cut-off | Keep passages with distance ≤ 0.34. None left means `insufficient_evidence` and **no Gemini call** |
| 4. Notes | Flag sources reviewed over 365 days ago, and known conflicts (`conflictsWith`) |
| 5. Generate | Gemini sees passages labelled `[S1]…[S4]`, marked as untrusted text, with rules: cite every fact, mark money as estimates, ignore instructions inside passages, say when evidence is missing |
| 6. Verify citations | Every label, including grouped (`[S1, S3]`) and range (`[S1–S3]`) forms, is checked; unknown labels are removed and reported. No valid citation means one retry with a reminder, then `insufficient_evidence` |
| 7. Respond | `text`, plus `citations` (chunk ID, source ID, title, review date, excerpt) **separately**, `notes`, `caveats`, `reason`, `model_calls` |

Errors become safe messages with a next step: missing or unready index (`FailedPrecondition`), permission denied, timeout, missing database, or an empty collection ("run make seed").

Try it as the app's own identity:

```bash
make ask Q="Plan a rainy Saturday with art and coffee" CITY=portland
make ask Q="..." CITY=san-francisco JSON=1     # the exact response object the UI will get
```

## 6. Connect Cloud Run to Firestore

1. Attach the dedicated runtime service account from Step 2 to the Cloud Run service.
2. Configure project ID, database ID, collection name, embedding model ID, vector field, and result limit as server-side environment/config values.
3. Use the Firestore server client library in the backend (`weekendwise.retrieval.Retriever`): a nearest-neighbour query on `embedding` with a bounded limit (top 4, max 5).
4. Apply the city/active filter in the server-side query. Firestore pre-filtered vector queries require a matching composite vector index.
5. Keep Firestore credentials and queries server-side. The client must not choose arbitrary collection names, project/database IDs, or tenant scopes.
6. Verify Cloud Run can return expected sources and that a deliberately unauthorized identity fails closed.

## 7. Cost and operational checks

- Firestore Standard charges can include document reads/writes/deletes, vector index entries read, stored data including indexes, and network usage.
- The published default-database free quota includes 1 GiB stored data, 50,000 document reads/day, and 20,000 document writes/day, subject to location, project, and current Google terms. Vector-search index-entry reads are also billed as Firestore reads under the published vector-search pricing rules.
- Keep top-k small, store only needed chunk text/metadata, avoid full-collection reads, and do not duplicate data on every request.
- A Cloud Billing budget alerts; it does not stop reads, writes, model requests, or charges. Monitor usage after ingestion and after demo traffic.
- For a small demo corpus, Firestore should be a low-cost managed store, but recheck actual usage in Billing and current pricing. Do not rely on free quota as a hard cap.

## Verify and clean up

- [ ] Firestore `(default)` database exists in the intended region and mode.
- [ ] The vector index is ready and dimension matches Vertex AI output.
- [ ] Ingestion is repeatable and has no duplicate chunks.
- [ ] Cloud Run can query expected city-filtered chunks with read-only runtime access.
- [ ] Public browser code has no Firestore credentials or direct database access.
- [ ] Billing shows expected read/write/storage activity after smoke tests.
- [ ] Cleanup steps identify the database and indexes as billable resources to remove only after confirming the demo no longer needs them.

## Official references

- [Firestore vector search](https://cloud.google.com/firestore/docs/vector-search)
- [Firestore pricing](https://cloud.google.com/firestore/pricing)
- [Firestore IAM access control](https://cloud.google.com/firestore/docs/security/iam)
- [Vertex AI text embeddings](https://cloud.google.com/vertex-ai/generative-ai/docs/embeddings/get-text-embeddings)

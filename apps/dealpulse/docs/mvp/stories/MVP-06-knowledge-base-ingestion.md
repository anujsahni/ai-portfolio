# MVP-06 — Knowledge base ingestion (`make seed`)

**Type:** RAG data pipeline  
**Priority:** P0  
**Estimate:** 5–8 hours  
**Story points:** 5 (chunking, metadata, embeddings, bulk load and safe re-runs)  

## User story

As the demo owner, I want one command that loads deal notes, the playbook and win/loss reviews into OpenSearch with the right metadata so that retrieval can find the right passages and never mix up accounts.

## Scope

- `dealpulse/seed.py` (`make seed`, run as `dealpulse-ingest`):
  - reads activity notes from `crm-snapshot/` and shared documents from `knowledge/` in S3;
  - splits into passages of about 300–500 tokens on paragraph or section boundaries (activity notes usually stay whole);
  - sets metadata: `passage_id` (stable, derived from source ID and position), `doc_type` (`call_note`, `email`, `meeting`, `playbook`, `policy`, `win_loss`), `account_id` and `opportunity_id` (empty for shared docs), `date`, `author_role`, `title`, `checksum`;
  - embeds only new or changed passages with Titan (batched, with retry on throttling);
  - bulk-indexes into `deal_passages` and marks removed passages inactive or deletes them;
  - prints a summary: passages by type, new / changed / unchanged / removed, embedding calls and estimated cost.
- Validate before writing: every deal-scoped passage has both IDs; every shared passage has neither; no passage exceeds the size cap.
- Write guide 03 (second part): how the knowledge base is built and how to inspect it.

**Out of scope:** real-time ingestion from Salesforce, PDF or HTML parsing, OCR and multi-language content.

## Acceptance criteria

- [ ] `make seed` loads about 1,000 passages; counts by `doc_type` match the source files.
- [ ] A second `make seed` with no changes makes **zero** embedding calls and changes nothing.
- [ ] Editing one note re-embeds and updates only that note's passages.
- [ ] Metadata validation rejects a deal passage missing `opportunity_id` and a shared passage that has one (unit-tested).
- [ ] The run uses `dealpulse-ingest`; the same command as `dealpulse-run` fails with a clear permission message.
- [ ] The prompt-injection trap note and the look-alike account notes are indexed like any other note (they are needed for evaluation).
- [ ] Seeding cost is printed and is well under $0.10.

## Dependencies and deliverables

**Dependencies:** MVP-02, MVP-03, IAC-04.  
**Deliverables:** `dealpulse/seed.py`, chunking and metadata tests, `make seed`, guide 03 (second part).

## Completion evidence

The `make seed` summary for a first run and a no-change re-run.

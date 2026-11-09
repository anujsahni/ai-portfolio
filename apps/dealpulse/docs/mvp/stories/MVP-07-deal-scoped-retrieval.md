# MVP-07 — Deal-scoped hybrid retrieval and citations

**Type:** RAG capability  
**Priority:** P0  
**Estimate:** 5–8 hours  
**Story points:** 5 (hybrid queries, two scopes, driver-based queries, threshold calibration and citation checks)  

## User story

As a sales manager, I want every statement in a deal brief to link to the note or playbook section it came from, and never to another customer's notes, so that I can trust and check what the assistant says.

## Scope

- `dealpulse/retrieval.py`:
  - `search_deal(opportunity_id, queries)`: hybrid search (keyword + vector, through the search pipeline) with a **filter on `opportunity_id` set in code**; top 6 overall after merging queries;
  - `search_guidance(queries, segment=None)`: hybrid search limited to `doc_type in (playbook, policy, win_loss)`; top 4;
  - `queries_from_drivers(drivers)`: turns the top 3 negative drivers into short queries using a fixed phrase map (e.g. "no executive meeting" → "executive sponsor meeting", "decision maker");
  - a calibrated minimum score; a driver with no passage above it returns "no supporting notes found".
- Results are deduplicated, carry `passage_id`, score, `doc_type`, date, title and an excerpt, and are returned separately from any generated text.
- `dealpulse/citations.py`: checks that every cited `passage_id` was in the retrieved set **and** belongs to this opportunity or to a shared document; unknown or out-of-scope IDs are removed and reported.
- `data/retrieval_cases.json`: 30 cases (deal, query or driver, expected passage IDs, forbidden passage IDs), including the look-alike accounts.
- `scripts/check_retrieval.py` (`make check-retrieval`, with `--calibrate` to print score distributions for on-topic and off-topic queries).

**Out of scope:** reranking models, query rewriting with an LLM, cross-deal search ("find deals like this one") and Bedrock Knowledge Bases.

## Acceptance criteria

- [ ] Every search sent to OpenSearch includes the scope filter; a unit test fails if a query is built without it.
- [ ] Expected passage in the top 5 for at least 90% of the 30 retrieval cases.
- [ ] **Zero** results from another opportunity across all cases, including both look-alike accounts.
- [ ] Off-topic queries (e.g. "holiday party plans") return "no supporting notes found" for at least 9 of 10 cases.
- [ ] Hybrid search beats vector-only on the case set (both numbers recorded), or the report explains why not.
- [ ] Citation checks reject unknown IDs, IDs from another deal and malformed IDs (unit-tested).
- [ ] Timeouts, a missing index and a permission error produce safe, specific messages.

## Dependencies and deliverables

**Dependencies:** MVP-06.  
**Deliverables:** `retrieval.py`, `citations.py`, `data/retrieval_cases.json`, `scripts/check_retrieval.py`, unit tests, `docs/mvp/evidence/MVP-07-retrieval.md`.

## Completion evidence

The retrieval report: hit rate at 5, leak count, off-topic rejections, hybrid vs. vector-only, chosen threshold with its calibration numbers.

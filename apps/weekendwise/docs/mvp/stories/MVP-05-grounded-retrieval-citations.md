# MVP-05 — Grounded Firestore retrieval and citations

**Type:** RAG capability  
**Priority:** P0  
**Estimate:** 4–7 hours  
**Story points:** 5 (retriever, filters, threshold calibration, and citation validation)  

## User story

As a traveler, I want to see which destination-guide passages informed a recommendation so that I can verify the itinerary details and distinguish sourced facts from estimates.

## Scope

- Embed each query with the same Vertex AI embedding model and dimension used by MVP-04.
- Query Firestore `guide_chunks` with nearest-neighbor vector search, bounded top-k, and a server-side city/active filter.
- Apply a calibrated distance/relevance threshold and return an explicit insufficient-evidence result.
- Pass retrieved text and metadata into the planning prompt; require citations for corpus-derived claims.
- Return citation IDs/metadata separately from generated text so the UI can render them safely.

**Out of scope:** Vertex AI Vector Search, live web search, changing travel prices/hours in real time, client-side Firestore access, or treating model-generated details as retrieved facts.

> **Baseline distances (from MVP-04, 2026-11-06):** cosine distance 0.25–0.31 for on-topic matches; about 0.32–0.40 for the nearest passages to off-topic queries. Start threshold calibration from these numbers.

## Acceptance criteria

- [x] A retriever issues Firestore nearest-neighbor queries and returns at most configured top-k chunks with distance/score and source metadata.
- [x] Firestore queries apply the selected city and active/version filter server-side before nearest-neighbor results are returned.
- [x] A known corpus question retrieves at least one expected source in the top-k on the fixed test set.
- [x] A low-relevance or out-of-city query returns insufficient evidence instead of forcing a source match.
- [x] Every displayed citation resolves to an actual returned chunk; fabricated/unknown citation IDs are rejected.
- [x] Missing vector/composite index, Firestore permission denial, timeout, and empty collection produce actionable diagnostics or a safe user-facing fallback.
- [x] The retrieval result is bounded; no unfiltered collection scan or direct browser database request is used.
- [x] Itinerary text labels estimates and advises checking current official information where details may change.
- [x] Retrieval tests cover relevance, empty results, unrelated queries, and stale/conflicting passages.

## Dependencies and deliverables

**Dependencies:** MVP-04.  
**Deliverables:** Firestore-backed retriever module, citation/evidence response schema, unit tests, and retrieval test fixture.

## Completion evidence

Publish top-k/citation test results for the seeded queries and document any retrieval limitations. A small corpus benchmark is evidence of prototype behavior, not a production-scale retrieval guarantee.

## Completion record (2026-11-06) ✅ Done

| Acceptance criterion | Evidence |
|---|---|
| Firestore nearest-neighbour query, ≤ top-k, distance and source metadata | `Retriever.retrieve`: top 4 (hard cap 5), cosine distance, chunk/source/title/review date per result |
| City and active filters server-side | `cityId ==` and `active == true` in the Firestore query; results re-checked; unit-tested |
| Known questions find expected sources | 18/18 expected-source cases pass across all four cities (`data/retrieval_cases.json`) |
| Low-relevance or out-of-city → insufficient evidence | Cut-off calibrated at **0.34** (matches ≤ 0.306, off-topic ≥ 0.386): 10/10 off-topic cases rejected; `tokyo` → `unsupported_city`; no Gemini call in either case |
| Citations resolve to returned chunks; fabricated IDs rejected | Model only sees `[S#]` labels. Every label (single, grouped, range) is checked; unknown labels are removed and reported; no valid citation → one retry → `insufficient_evidence` |
| Missing index, permission, timeout, empty collection | Translated to safe messages with next steps; unit-tested |
| Bounded, no collection scan, no browser access | One limited vector query per request; 10 s Firestore timeout; server-side only |
| Estimates labelled; advise checking official sources | Grounding rules require "(estimate)" and an official-sources sentence; `ensure_caveat` appends one if missing; `caveats` are returned separately |
| Tests: relevance, empty, unrelated, stale/conflicting | 20 offline tests in `tests/test_retrieval.py` (46 total); live: the stale Ferry note is flagged as 980 days old and conflicting |

**Live grounded answers (as `weekendwise-run`):** one question per city returned `ok` on the first model call with citations only from that city. The Napa tasting answer included the designated-driver rule and estimate labels. The wheelchair question declined to guarantee access. The nightclub question returned `insufficient_evidence` with no model call. The Mission answer ignored the injected "book a table" instruction.

**Bug found and fixed during live testing:** Gemini sometimes writes grouped citations (`[S2, S3]`), which the first version passed through unchecked. Grouped and range labels are now each verified, and covered by tests.

**For MVP-08:**
- The Santa Cruz wheelchair question didn't retrieve `SC-PLANNING-ACCESSIBILITY` (the answer was still safe). Check eval case PLAN-029.
- `SF-ADVERSARIAL-INJECTION` is active by design, and its harmless first sentence can be cited in real answers. Decide whether to hide adversarial fixtures from demo answers.

Code: `weekendwise/retrieval.py`, `weekendwise/citations.py`, `scripts/check_retrieval.py` (`--calibrate`), `scripts/ask.py` (`make ask`), `data/retrieval_cases.json`.

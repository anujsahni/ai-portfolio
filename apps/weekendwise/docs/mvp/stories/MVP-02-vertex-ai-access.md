# MVP-02 — Vertex AI Gemini and embedding access

**Type:** AI platform setup + how-to documentation  
**Priority:** P0  
**Estimate:** 3–5 hours  
**Story points:** 3 (small client/config module and smoke tests; some quota/availability risk)  

## User story

As the WeekendWise backend, I want authorized access to a Gemini generation model and a text-embedding model through Vertex AI so that I can plan itineraries and retrieve relevant destination-guide passages.

## Scope

> API enablement and the runtime identity's permissions are provisioned by [IAC-02](IAC-02-project-billing-apis-budget.md) and [IAC-03](IAC-03-service-identities-iam.md). This story selects models and delivers the client/config module and smoke tests.


- Confirm model and embedding availability, region, quotas, and pricing before selecting model IDs.
- Enable Vertex AI API and configure least-privilege runtime identity.
- Store project, region, and model IDs in server-side configuration.
- Add smoke tests for generation and embeddings, plus useful permission/quota error messages.
- Deliver a repeatable how-to guide.

**Out of scope:** tuning/training models, provisioned throughput, client-side API calls, downloaded service-account keys, or choosing a model solely by brand name without verifying availability and cost.

## Acceptance criteria

- [x] `docs/mvp/guides/02-vertex-ai.md` explains API enablement, runtime identity, model selection, config, smoke tests, failure diagnosis, and cost check.
- [x] A short harmless prompt returns a Gemini response through the server-side Vertex AI client.
- [x] A text embedding request returns a non-empty vector; the app records and validates the expected vector dimension.
- [x] Document and query embeddings use the same configured embedding model; model IDs are configurable, not scattered literals.
- [x] The Cloud Run runtime identity (from MVP-03) has only the required model invocation permissions and uses attached identity, not a key file.
- [x] Missing config, permission denied, quota exhaustion, and timeout produce an actionable, non-sensitive error.
- [x] Prompt sizes, retrieved context, output tokens, and retries have application-level limits.

## Dependencies and deliverables

**Dependencies:** MVP-01.  
**Deliverables:** Vertex AI client/config module, generation and embedding smoke tests, and setup guide 02.

## Completion evidence

Record model IDs, selected location, a successful smoke-test result, and observed vector dimension. Never commit prompts containing personal data or credentials.

## Completion record (2026-11-06) ✅ Done

| Acceptance criterion | Status |
|---|---|
| Guide 02 covers enablement, identity, model choice, config, smoke tests, failures, cost | ✅ Rewritten around the verified setup |
| Short prompt returns a Gemini response via the server-side client | ✅ `gemini-3.8-flash` @ `global` replied `ok` (7 in / 1 out / 57 thinking tokens, ~4 s) |
| Embedding returns a non-empty vector; dimension recorded and validated | ✅ `gemini-embedding-001` @ `us-central1`, 768 dimensions; mismatches raise `EmbeddingDimensionError` |
| Documents and queries use the same configured model; IDs not scattered | ✅ Only `weekendwise/config.py` reads model IDs; unit-tested |
| Runtime identity has only required permissions, no key | ✅ `make smoke-vertex AS=run` passed as `weekendwise-run` (no key; impersonation). `make verify` confirms its permissions. Attachment to Cloud Run is re-checked in IAC-05. |
| Missing config, permission denied, quota, timeout give actionable, non-sensitive errors | ✅ Unit tests for each; live-checked wrong model, wrong location, bad dimension |
| Prompt, output, retry, and timeout limits | ✅ 24,000 chars, 2,048 tokens, 1 retry (429/5xx only), 45 s |

Code: `weekendwise/config.py`, `weekendwise/vertex.py`, `weekendwise/errors.py`, `scripts/smoke_vertex.py`, `tests/` (18 offline tests).
Observed latency as `weekendwise-run`: about 3–4 s for generation and 1.6–2 s for embeddings. The first call after the account was created took 55 s: the first attempt hit the 45 s timeout and the single retry succeeded. **Worst case per call is therefore about 90 s (timeout × 2)**; MVP-06 must budget total request time with this in mind.

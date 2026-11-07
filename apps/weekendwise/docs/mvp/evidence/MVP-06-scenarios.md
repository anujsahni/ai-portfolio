# MVP-06 scenario run — 2026-11-07T20:53:00+00:00

Model `gemini-3.8-flash` (thinking LOW), embeddings `gemini-embedding-001` (768), run as `weekendwise-run`. Full responses: `reports/scenarios-latest.json` (git-ignored).

| Scenario | Result | Tool call | Review | Budget | Usage | Time |
|---|---|---|---|---|---|---|
| SCENARIO-01-ART-COFFEE | ❌ fail | 0 (expected 0) | - (expected approved) | $0 / $0 - (expected on-track) | model -, tool -, searches -, 0 citations | 1.0 s |
| SCENARIO-02-RAINY-SATURDAY | ❌ fail | 0 (expected 1) | - (expected approved) | $0 / $0 - (expected on-track) | model -, tool -, searches -, 0 citations | 0.2 s |
| SCENARIO-03-TIGHT-BUDGET | ❌ fail | 0 (expected 0) | - (expected approved) | $0 / $0 - (expected over-budget) | model -, tool -, searches -, 0 citations | 0.3 s |
| SCENARIO-04-PORTLAND-RAINY | ❌ fail | 0 (expected 1) | - (expected approved) | $0 / $0 - (expected on-track) | model -, tool -, searches -, 0 citations | 0.2 s |
| SCENARIO-05-SANTA-CRUZ-COAST | ❌ fail | 0 (expected 0) | - (expected approved) | $0 / $0 - (expected on-track) | model -, tool -, searches -, 0 citations | 0.2 s |
| SCENARIO-06-NAPA-HOT-TASTING | ❌ fail | 0 (expected 1) | - (expected approved-after-revision) | $0 / $0 - (expected over-budget) | model -, tool -, searches -, 0 citations | 0.2 s |

**Failures** (break the contract):

- SCENARIO-01-ART-COFFEE: status error: Google sign-in failed or expired while calling the embedding model gemini-embedding-001 in us-central1. Run: gcloud auth application-default login
- SCENARIO-02-RAINY-SATURDAY: status error: Google sign-in failed or expired while calling the embedding model gemini-embedding-001 in us-central1. Run: gcloud auth application-default login
- SCENARIO-03-TIGHT-BUDGET: status error: Google sign-in failed or expired while calling the embedding model gemini-embedding-001 in us-central1. Run: gcloud auth application-default login
- SCENARIO-04-PORTLAND-RAINY: status error: Google sign-in failed or expired while calling the embedding model gemini-embedding-001 in us-central1. Run: gcloud auth application-default login
- SCENARIO-05-SANTA-CRUZ-COAST: status error: Google sign-in failed or expired while calling the embedding model gemini-embedding-001 in us-central1. Run: gcloud auth application-default login
- SCENARIO-06-NAPA-HOT-TASTING: status error: Google sign-in failed or expired while calling the embedding model gemini-embedding-001 in us-central1. Run: gcloud auth application-default login

**Differences from the scripted expectation** (model judgement, not failures):

- none

**Reviewer issues on first drafts** (fixed by the single revision when the outcome says so):

- none

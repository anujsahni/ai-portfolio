# WeekendWise MVP backlog

This folder is the implementation source of truth for the WeekendWise interview demo. Each story has a bounded scope, dependencies, deliverables, and testable acceptance criteria. The initial prototype uses synthetic destination content and simulated local conditions; it does not make bookings or use live travel APIs.

## Product outcome

A traveler enters destination, dates, party size, budget, interests, and constraints in a web app. The backend uses a bounded LangGraph workflow, Gemini and text embeddings through Vertex AI, Firestore vector search, and one allowlisted mock conditions tool to return a cited draft itinerary. A reviewer step checks evidence and constraints. The UI shows progress, itinerary, budget estimate, sources, and demo-data limitations.

## MVP stack

- **Infrastructure as code:** Terraform (two root modules: `infra/bootstrap` and `infra/stack`) driven by `make` targets. No manual console provisioning.
- **Google Cloud:** Firestore Standard (chunk/vector storage and nearest-neighbor retrieval), Vertex AI (Gemini and text embeddings), Cloud Run, Cloud Build, Artifact Registry, Cloud Logging, IAM/service identities, Cloud Billing budgets.
- **Application:** Python, LangGraph, and a small Starlette/Uvicorn web server that serves the approved mockup's screens (Streamlit was the original plan; see MVP-07).
- **RAG:** original/synthetic Markdown destination documents for four cities (San Francisco, Portland, Santa Cruz, and Napa Valley), at least 10 per city; embeddings generated through Vertex AI, stored with chunk metadata in Firestore, and retrieved with Firestore vector indexes.
- **Tool:** one read-only, deterministic `check_local_conditions` fixture. It is not a real weather, map, venue-hours, booking, or payment integration.

## Story order

Stories are listed in build order. **IAC** stories provision infrastructure with Terraform; **MVP** stories build the product on top of it.

| # | ID | Story | Depends on | Points |
|---|---|---|---|---|
| 1 | [IAC-01](stories/IAC-01-terraform-foundation-state.md) | Terraform foundation, state, and make commands | — | 3 |
| 2 | [IAC-02](stories/IAC-02-project-billing-apis-budget.md) | Project, billing, APIs, budget (Terraform) | IAC-01 | 3 |
| 3 | [MVP-01](stories/MVP-01-project-billing-guardrails.md) | Project, billing, guardrails (approve and verify) | IAC-02 | 1 |
| 4 | [MVP-02](stories/MVP-02-vertex-ai-access.md) | Vertex AI model and embedding access | MVP-01 | 3 |
| 5 | [IAC-03](stories/IAC-03-service-identities-iam.md) | Service identities and IAM (Terraform) | IAC-02 | 3 |
| 6 | [IAC-04](stories/IAC-04-firestore-database-vector-index.md) | Firestore database and vector index (Terraform) | IAC-02, MVP-02 | 3 |
| 7 | [MVP-04](stories/MVP-04-destination-corpus-embeddings.md) | Destination corpus and ingestion (`make seed`) | MVP-02, IAC-03, IAC-04 | 5 |
| 8 | [IAC-05](stories/IAC-05-artifact-registry-cloud-run.md) | Artifact Registry, build, and Cloud Run (Terraform) | IAC-03 | 5 |
| 9 | [MVP-03](stories/MVP-03-cloud-run-deploy.md) | App container on Cloud Run | MVP-02, MVP-04, IAC-05 | 3 |
| 10 | [MVP-05](stories/MVP-05-grounded-retrieval-citations.md) | Grounded retrieval and citations | MVP-04 | 5 |
| 11 | [MVP-06](stories/MVP-06-langgraph-planner-tool-reviewer.md) | LangGraph planner, tool, and reviewer | MVP-02, MVP-05 | 8 |
| 12 | [MVP-07](stories/MVP-07-traveler-web-screens.md) | Traveler screens and interaction flow | MVP-03, MVP-06 | 5 |
| 13 | [MVP-08](stories/MVP-08-evaluation-and-safety.md) | Evaluation, safety, and regression tests | MVP-05, MVP-06, MVP-07 | 5 |
| 14 | [IAC-06](stories/IAC-06-teardown-destroy.md) | Safe, complete teardown (Terraform) | IAC-02, IAC-03, IAC-04, IAC-05 | 3 |
| 15 | [MVP-09](stories/MVP-09-observability-release-demo.md) | Observability, release, and demo runbook | MVP-03, MVP-08, IAC-06 | 3 |

## Provisioning and setup guides

- **[00 — Provision and destroy with Terraform](guides/00-provision-with-terraform.md)**: the only supported way to create, change, or remove infrastructure.
- [01 — Project, billing, APIs, and budget](guides/01-project-and-billing.md)
- [02 — Vertex AI Gemini and embeddings](guides/02-vertex-ai.md)
- [03 — Cloud Build, Artifact Registry, and Cloud Run](guides/03-cloud-run-deployment.md)
- [04 — Firestore database and vector search](guides/04-firestore-vector-search.md)
- [05 — The itinerary planner (LangGraph)](guides/05-planner.md)
- [06 — The web app](guides/06-web-app.md)
- [07 — Evaluation and safety tests](guides/07-evaluation.md)
- **[Runbook: demo, operations, and teardown](runbook.md)**

Guides 01–04 are console references for understanding and inspecting what Terraform creates; don't use them to change resources by hand. Google Cloud console labels, model availability, IAM roles, quotas, and pricing can change; confirm them before use. Linking billing, enabling public access, or incurring charges requires the account owner's authorization.

## Definition of MVP done

- A browser user can complete all six scripted trip scenarios end to end (three San Francisco, one each for Portland, Santa Cruz, and Napa Valley).
- Itinerary claims reference returned source IDs; missing evidence is called out rather than invented.
- Destination chunks and embeddings persist in Firestore; the Cloud Run backend retrieves only bounded, relevant passages.
- The mock conditions tool is allowlisted, deterministic, and read-only; the workflow has bounded model/tool/review calls.
- The app clearly states that guide content and conditions are demo data and no booking is made.
- All infrastructure is created by `make bootstrap` / `make apply` and fully removed by `make destroy-all`, with no manual console steps beyond sign-in and billing access.
- The deployed app uses a Cloud Run service identity, has conservative instance limits, emits privacy-conscious logs, and has a cost-alert plan.
- Evaluation results and a 3–5 minute demo runbook are checked in.

## Scope guardrails

No BigQuery, Vertex AI Vector Search, Firebase Authentication, Agent Engine, Kubernetes, public live travel data, reservations, payments, or real personal data in this MVP. Terraform is limited to one demo environment; CI-driven applies are a later option. Firestore is the MVP’s database; Vertex AI Vector Search remains a possible later option for larger retrieval workloads.

The visual prototype is in [artifacts/google-cloud-ai-copilot/weekendwise-mockups/index.html](../../artifacts/google-cloud-ai-copilot/weekendwise-mockups/index.html). The learning overview is [the Google technology brief](../../artifacts/google-cloud-ai-copilot/google-tech-brief.md).

## Implementation status

_Last updated: 2026-11-06_

**Stories done: 11 of 15.** All code is written and tested, and the app has run on Cloud Run: deployed, smoke-tested (9 of 9 checks, including a live plan), then removed with `make destroy` as the first step of the teardown rehearsal. The last 4 stories each need one more live run: a rollback, a timed demo rehearsal, and the rest of the teardown cycle.

The real app works end to end on your computer: `make run`, then open http://localhost:8080. In headless Chrome, all six scripted trips across all four cities pass at desktop and phone sizes ([walkthrough](evidence/MVP-07-ui-walkthrough.md)), and 29 of 30 evaluation cases pass ([report](evidence/MVP-08-evaluation.md)).

| | Stories | Story points |
|---|---|---|
| ✅ Done | 11 of 15 (IAC-01, IAC-02, MVP-01, MVP-02, IAC-03, IAC-04, MVP-04, MVP-05, MVP-06, MVP-07, MVP-08) | 44 of 58 |
| 🟡 Partly verified live, one run left each | 4 (IAC-05, MVP-03, IAC-06, MVP-09) | 14 |
| ⚪ Not started | 0 | 0 |
| **Left to finish** | **4** | **14** |

**To finish them** (the stack is currently removed; the project, budget and state bucket remain). See how-to 00, Steps 12–14:

1. **Rebuild:** `make apply && make seed && make release`, then `make smoke-cloud`. This proves a rebuild needs no manual steps (IAC-06).
2. **Rollback:** the new registry starts empty, so run `make release` a second time, then `make images` and `make deploy IMAGE=<older tag>`, then `make smoke-cloud`. This completes IAC-05 and MVP-03.
3. **Rehearse the demo:** `make proxy`, run the [runbook](runbook.md) demo script once in a clean browser with timings, plus one failure path (for example, deploy a bad tag and roll back). This completes MVP-09.
4. **Full teardown when you're done:** `make destroy-all CONFIRM=<project-id>` → `make verify-destroyed`, and a billing check a few days later. This completes IAC-06.

By track: IAC 20 points (6 stories), MVP 38 points (9 stories). MVP-01, MVP-03, and MVP-04 were re-pointed (2→1, 5→3, 8→5) when their infrastructure work moved into IAC stories, so nothing is counted twice.

Points use a Fibonacci scale (1, 2, 3, 5, 8, 13) for relative size, based on each story's hour estimate, number of moving parts, and risk. A story counts as done only when every acceptance criterion is met, so the points for stories waiting on a live run still count as left.

| ID | Story | Points | Status | Delivered | Still needed |
|---|---|---|---|---|---|
| IAC-01 | Terraform foundation, state, and make commands | 3 | ✅ Done | `infra/bootstrap` + `infra/stack` (GCS state), pinned providers and lock files, `Makefile`, [how-to 00](guides/00-provision-with-terraform.md); live run clean | — |
| IAC-02 | Project, billing, APIs, budget (Terraform) | 3 | ✅ Done | Project `weekendwise-demo-jytx`, billing linked, 11 APIs, $20/month budget (max enforced; 4 alert rules), versioned state bucket | — |
| MVP-01 | Project, billing, guardrails (approve and verify) | 1 | ✅ Done | Owner ran how-to 00 end to end; budget and billing verified | — |
| MVP-02 | Vertex AI model and embedding access | 3 | ✅ Done | `gemini-3.8-flash` (global) + `gemini-embedding-001` (us-central1, 768); limits and safe errors; smoke test as `weekendwise-run` | — |
| IAC-03 | Service identities and IAM (Terraform) | 3 | ✅ Done | 3 service accounts, 8 roles, operator impersonation, no keys; `make verify` proves run = read-only Firestore | — |
| IAC-04 | Firestore database and vector index (Terraform) | 3 | ✅ Done | `(default)` database (protected) + 768-dim vector index READY | — |
| MVP-04 | Destination corpus and ingestion (`make seed`) | 5 | ✅ Done | 47 guides / 95 chunks embedded and loaded by `make seed` as `weekendwise-ingest`; idempotent | — |
| IAC-05 | Artifact Registry, build, and Cloud Run (Terraform) | 5 | 🟡 Deployed | `registry.tf`, `run.tf` (min 0 / max 2, runtime identity, private by default, protection flag), `make build/deploy/release/images/proxy/smoke-cloud`; live: applied, 3 images deployed, `make verify` no changes, 403 without a token | One rollback rehearsal |
| MVP-03 | App container on Cloud Run | 3 | 🟡 Deployed | `Dockerfile`, `cloudbuild.yaml`, `.gcloudignore`, `/health` + `/readyz`; `make smoke-cloud` 9/9 on Cloud Run incl. a live plan ([evidence](evidence/MVP-03-cloud-run-smoke.md)); [guide 03](guides/03-cloud-run-deployment.md) | Restore an earlier revision once |
| MVP-05 | Grounded retrieval and citations | 5 | ✅ Done | Firestore retriever (city/active filter, cut-off 0.34), verified `[S#]` citations, stale/conflict notes; 29/29 retrieval cases | — |
| MVP-06 | LangGraph planner, tool, and reviewer | 8 | ✅ Done | Bounded planner, allowlisted conditions tool, deterministic reviewer; 6/6 scenarios live ([report](evidence/MVP-06-scenarios.md)); now also streams progress | — |
| MVP-07 | Traveler screens and interaction flow | 5 | ✅ Done | The mockup's screens wired to the planner, all 4 cities, live progress, sources, error states, request IDs; 31/31 browser checks ([walkthrough](evidence/MVP-07-ui-walkthrough.md)); [guide 06](guides/06-web-app.md). Since added: interactive Architecture page, an address per page, in-page dropdowns and calendar | — |
| MVP-08 | Evaluation, safety, and regression tests | 5 | ✅ Done | `make evaluate` (30 cases, deterministic vs heuristic vs expectation), 29/30 pass ([report](evidence/MVP-08-evaluation.md)); 6 offline safety tests; `make build` runs tests first; [guide 07](guides/07-evaluation.md) | — |
| IAC-06 | Safe, complete teardown (Terraform) | 3 | 🟡 Routine teardown verified | `make destroy` shows the list first and lifts Firestore + Cloud Run protection only there; live `make destroy` + `make verify-destroyed` passed (nothing left but the project, budget and state) | Rebuild, then `make destroy-all` + `make verify-destroyed` |
| MVP-09 | Observability, release, and demo runbook | 3 | 🟡 Runbook ready | JSON logs with request IDs (no prompts or user text), `make logs`, [runbook](runbook.md) with demo script and fallback (`make mockups`), Architecture page for the close, root [README](../../README.md) | Timed rehearsal on Cloud Run (clean browser + one failure path) |

**Scope (updated 2026-11-05):** the MVP covers four cities: San Francisco, Portland, Santa Cruz, and Napa Valley. Each city has its own guides, simulated conditions, scripted scenario(s), and evaluation cases. The static mockup only renders the San Francisco sample; the real app (MVP-07) supports all four.

**Scope (updated 2026-11-06):** the web app serves the approved mockup's HTML/CSS from a Python server instead of Streamlit, so the screens match exactly; see MVP-07.

**Scope (updated 2026-11-06):** all infrastructure is provisioned and destroyed with Terraform (IAC-01 to IAC-06). Console guides are reference only.

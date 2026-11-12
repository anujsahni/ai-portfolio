# ContextLoop MVP backlog

This folder is the implementation source of truth for the ContextLoop demo. Each story has a bounded scope, dependencies, deliverables and testable acceptance criteria. All data is synthetic. Everything runs locally in Docker; nothing connects to a real SAP system, Salesforce org or Zendesk instance.

What the demo is and why: [README](../../README.md).

## Product outcome

A presenter runs `make demo` on a laptop with only Docker installed, opens http://127.0.0.1:8501 and walks an audience through five acts in ten minutes (or twenty with deep dives):

1. **The confident wrong answer**: an agent with raw SQL access answers the COO's question and gets it wrong, and the app shows exactly why.
2. **Move**: Fivetran Connector SDK connectors land SAP-shaped and Postgres data with incremental sync, soft deletes, history mode and a live schema change; a sync log shows freshness and MAR.
3. **Transform and Trust**: dbt builds tested, contracted models and a semantic layer; trusted marts are published as Iceberg and read by two engines.
4. **Context**: the same agent, through the dbt MCP server and two small MCP servers, answers correctly with cited definitions, lineage and freshness, and outscores Act 1 on a golden question set.
5. **Activate**: the at-risk list is synced to a mock Salesforce API and posted to Slack.

Plus an **interactive architecture page** that steps through the acts and a **proof-of-value scorecard** for the sales engineering view.

## Stack

- **Runtime:** Docker Compose. One application image (`contextloop`) plus pinned public images for Postgres, RustFS (S3-compatible; MinIO images are no longer published), the Iceberg REST catalog and Trino. Published ports on `127.0.0.1` only.
- **Move:** Fivetran Connector SDK (Python), run with `fivetran debug`; Fivetran landing conventions (`_fivetran_synced`, `_fivetran_deleted`, history-mode columns).
- **Warehouse and lakehouse:** DuckDB (raw, staging); Apache Iceberg via PyIceberg, REST catalog and RustFS (trusted marts); Trino as the second engine.
- **Transform and trust:** dbt Core with `dbt-duckdb`; dbt tests and model contracts; MetricFlow semantic layer.
- **Context and agent:** dbt MCP server (`dbt-mcp`); two small MCP servers (metrics, freshness) using the Python MCP SDK over streamable HTTP; Claude (set by `CONTEXTLOOP_MODEL`; the recordings use `claude-haiku-5-5`) via the Anthropic Python SDK, with a small bridge that exposes the MCP tools to Claude's tool use.
- **Activation:** a diff-based reverse ETL sync to a mock Salesforce REST API (FastAPI); optional Slack incoming webhook.
- **App:** Streamlit, with the architecture page embedded as HTML, CSS and JavaScript (the DealPulse pattern).

## Phases and stories

Stories are listed in build order. Points use a Fibonacci scale (1, 2, 3, 5, 8) for relative size. A story counts as done only when every acceptance criterion is met.

| Phase | # | ID | Story | Depends on | Pts | Day | Priority | Status |
|---|---|---|---|---|---|---|---|---|
| **0 · Foundation** | 1 | [CL-01](stories/CL-01-demo-narrative-talk-track.md) | Demo narrative, golden question and talk track | — | 3 | Wed | P0 | ✅ Done |
|  | 2 | [CL-02](stories/CL-02-docker-foundation.md) | Docker Compose foundation, image, Makefile and modes | — | 3 | Wed | P0 | ✅ Done |
| **1 · Move** | 3 | [CL-03](stories/CL-03-synthetic-source-systems.md) | Synthetic source systems, hidden truth and traps | CL-01, CL-02 | 5 | Wed | P0 | ✅ Done |
|  | 4 | [CL-04](stories/CL-04-sap-connector-sdk.md) | SAP-shaped Fivetran Connector SDK connector | CL-03 | 5 | Wed–Thu | P0 | ✅ Done |
|  | 5 | [CL-05](stories/CL-05-postgres-saas-landing-sync-log.md) | Postgres connector, SaaS landing and sync log | CL-03, CL-04 | 3 | Thu | P0 | ✅ Done |
| **2 · Transform and Trust** | 6 | [CL-06](stories/CL-06-dbt-project-tests-contracts.md) | dbt project: models, tests, contracts and lineage | CL-04, CL-05 | 8 | Thu | P0 | ✅ Done |
|  | 7 | [CL-07](stories/CL-07-semantic-layer-metricflow.md) | Semantic layer with MetricFlow | CL-06 | 3 | Thu | P0 | ✅ Done |
|  | 8 | [CL-08](stories/CL-08-iceberg-lakehouse-two-engines.md) | Iceberg lakehouse: publish marts, read from two engines | CL-06 | 5 | Thu–Fri | P1 | ✅ Done |
| **3 · Context** | 9 | [CL-09](stories/CL-09-naive-agent-baseline.md) | Naive agent baseline (raw SQL only) | CL-05 | 3 | Fri | P0 | ✅ Done |
|  | 10 | [CL-10](stories/CL-10-governed-agent-mcp.md) | Governed agent via dbt MCP, metrics and freshness MCP servers | CL-07, CL-09 | 8 | Fri | P0 | ✅ Done |
|  | 11 | [CL-11](stories/CL-11-eval-and-replay.md) | Golden-question evaluation and replay recordings | CL-09, CL-10 | 3 | Fri | P0 | ✅ Done |
| **4 · Experience** | 12 | [CL-12](stories/CL-12-streamlit-story-mode.md) | Streamlit story mode: the five acts | CL-05, CL-06, CL-11 | 8 | Sat | P0 | ✅ Done |
|  | 13 | [CL-13](stories/CL-13-interactive-architecture-page.md) | Interactive architecture page | CL-02, CL-12 | 5 | Sat | P0 | ✅ Done |
|  | 17 | [CL-17](stories/CL-17-story-charts-with-vs-without.md) | Story charts and the "without vs with the stack" view | CL-11, CL-12 | 5 | Wed | P0 | ✅ Done |
|  | 18 | [CL-18](stories/CL-18-pitch-video.md) | Narrated pitch video on the architecture page | CL-11, CL-13 | 5 | Wed | P1 | ✅ Done |
| **5 · Activate and close** | 14 | [CL-14](stories/CL-14-activation-reverse-etl.md) | Activation: reverse ETL to mock Salesforce and Slack | CL-10, CL-12 | 3 | Sun | P0 | ✅ Done |
|  | 15 | [CL-15](stories/CL-15-pov-scorecard.md) | Proof-of-value scorecard and specialist view | CL-11, CL-12 | 3 | Sun | P1 | ✅ Done |
|  | 16 | [CL-16](stories/CL-16-rehearsal-runbook.md) | Rehearsal, runbook and Q&A preparation | All | 2 | Sun | P0 | 🟡 In progress |

**By phase:** Foundation 6 · Move 13 · Transform and Trust 16 · Context 14 · Experience 23 · Activate and close 8 · **Total 80 points**.

## Schedule

| Day | Date | Goal by end of day | Stories |
|---|---|---|---|
| Wed | 11 Nov 2026 | Story agreed; `make up` starts the stack; data generated; SAP connector syncing | CL-01, CL-02, CL-03, CL-04 (start) |
| Thu | 12 Nov | Raw data landed with a sync log; dbt builds green; metrics answer correctly | CL-04, CL-05, CL-06, CL-07, CL-08 (start) |
| Fri | 13 Nov | Both agents run; governed agent beats naive on the golden set; runs recorded | CL-08, CL-09, CL-10, CL-11 |
| Sat | 14 Nov | The five acts and the architecture page work end to end in replay mode | CL-12, CL-13 |
| Sun | 15 Nov | Activation, scorecard, two timed rehearsals | CL-14, CL-15, CL-16 |
| Mon | 16 Nov | **Interview** | — |

## Cut line

If the schedule slips, cut in this order, without breaking the story:

1. **CL-08, Trino part:** keep the Iceberg publish and read it with DuckDB only; show Trino on the architecture page instead.
2. **CL-15:** show a static scorecard built from the evaluation report rather than an interactive one.
3. **CL-14, Slack part:** keep the mock Salesforce sync, which is the visible loop-closing moment.
4. **CL-05, schema-change scene:** describe it on the architecture page instead of running it live.

Never cut: Act 1's wrong answer, Act 4's side-by-side comparison with the score, replay mode, and the architecture page. They are the core of the demo.

## Definition of MVP done

- On a clean machine with only Docker and `make`, `make demo` brings the stack up and the app loads in under five minutes (images pulled beforehand).
- Replay mode runs all five acts with no network access and no API key.
- In live mode, the governed agent answers the headline question with the exact at-risk account list from the hidden truth, and scores at least 5 of 6 on the golden set; the naive agent scores 2 or fewer, and every one of its mistakes is explained by a named trap.
- The SAP connector is real Connector SDK code: it syncs incrementally from saved state, emits deletes, and survives a schema change without code changes.
- `dbt build` passes; at least one test fails on purpose when a trap is re-introduced (demonstrated in the app).
- The same Iceberg mart returns identical results from two engines (or from DuckDB alone if the cut line is used).
- Activation shows a diff (inserts, updates, unchanged) and an audit log entry for every write to the mock CRM.
- The app labels all data as synthetic and never claims to touch a real system.
- A talk track, a runbook and a Q&A sheet are checked in, and the demo has been rehearsed twice against the clock.

## Scope guardrails

No real SAP, Salesforce, Zendesk or Slack workspace data; no paid Fivetran or dbt platform account; no cloud infrastructure (Snowflake reading the Iceberg tables is a stretch goal, not part of the MVP); no Kubernetes; no login; no real customer data; no writes to a real CRM. Every container image is pinned to an exact version, and no secrets are baked into images.

## Implementation status

Build, test and close one story at a time. **Done: 78 of 80 points.**

| ID | Story | Points | Status | Delivered | Still needed |
|---|---|---|---|---|---|
| CL-01 | Demo narrative, golden question and talk track | 3 | ✅ Done | [narrative](../demo/narrative.md), [talk track](../demo/talk-track.md); signed off by the owner 11 Nov; [record](evidence/CL-01-narrative.md) | — |
| CL-02 | Docker Compose foundation, image, Makefile and modes | 3 | ✅ Done | Image (2 envs), Compose, Makefile, RustFS for MinIO, SDK spike passed; [evidence](evidence/CL-02-docker-foundation.md) | — |
| CL-03 | Synthetic source systems, hidden truth and traps | 5 | ✅ Done | Generator, hidden truth (9 at-risk), traps T1–T6 proven; [evidence](evidence/CL-03-data-summary.md) | — |
| CL-04 | SAP-shaped Fivetran Connector SDK connector | 5 | ✅ Done | SDK connector via fivetran debug: incremental, deletes, schema change, resume; [evidence](evidence/CL-04-sync-runs.md) | — |
| CL-05 | Postgres connector, SaaS landing and sync log | 3 | ✅ Done | Postgres SDK connector, SaaS landings, history mode, sync log, MAR, T6; [evidence](evidence/CL-05-landing-and-sync-log.md) | — |
| CL-06 | dbt project: models, tests, contracts and lineage | 8 | ✅ Done | 27 models, contracts, tests, lineage, make break; marts equal truth; [evidence](evidence/CL-06-dbt-build.md) | — |
| CL-07 | Semantic layer with MetricFlow | 3 | ✅ Done | MetricFlow on DuckDB, 8 metrics, saved query equals truth; [evidence](evidence/CL-07-semantic-layer.md) | — |
| CL-08 | Iceberg lakehouse: publish marts, read from two engines | 5 | ✅ Done | PyIceberg publish, DuckDB and Trino agree, snapshots; [evidence](evidence/CL-08-lakehouse.md) | — |
| CL-09 | Naive agent baseline | 3 | ✅ Done | Naive agent (raw SQL only, same prompt and budget), 18 live traces; wrong on G1 in 3 of 3 runs; traps T1, T4, T5, T6 named; bar restated with owner 11 Nov; [evidence](evidence/CL-09-CL-11-baseline-and-eval.md) | — |
| CL-10 | Governed agent via MCP | 8 | ✅ Done | 3 MCP servers + bridge; governed agent 6/6 in 3 of 3 runs on Haiku, exact G1 list, T6 caveat, definitions and lineage; [evidence](evidence/CL-10-governed-agent.md) | — |
| CL-11 | Golden-question evaluation and replay recordings | 3 | ✅ Done | make record (3 runs × 6 questions × 2 agents), replay, report with restated bar: governed 6.0 vs naive 2.7 → pass; drift test; [evidence](evidence/CL-09-CL-11-baseline-and-eval.md) | — |
| CL-12 | Streamlit story mode: the five acts | 8 | ✅ Done | Five acts, live/replay, real-job buttons, step descriptions, side-by-side with traps; warm loads under 0.5 s; [evidence](evidence/CL-12-story-mode.md) | — |
| CL-13 | Interactive architecture page | 5 | ✅ Done | Standalone and embedded page, hover cards, act steps, request flow, two views, themes; [evidence](evidence/CL-13-architecture-page.md) | — |
| CL-14 | Activation: reverse ETL to mock Salesforce and Slack | 3 | ✅ Done | Mock CRM, diff sync (idempotent), audit, AI-drafted labels, Slack preview; [evidence](evidence/CL-14-activation.md) | — |
| CL-15 | Proof-of-value scorecard and specialist view | 3 | ✅ Done | Scorecard: 8 of 8 criteria pass, scores read from the evaluation report (tested), static fallback regenerated; [evidence](evidence/CL-15-scorecard.md) | — |
| CL-16 | Rehearsal, runbook and Q&A preparation | 2 | 🟡 In progress | [Runbook](../demo/runbook.md), [Q&A](../demo/qa.md) (13 answers, fact-checked 11 Nov 2026 with sources), [getting started](../getting-started.md) | Two timed rehearsals (owner); runbook failure drills (deferred so the shared stack isn't disrupted) |
| CL-17 | Story charts and the "without vs with the stack" view | 5 | ✅ Done | Without-vs-with page, charts on home and Acts 1, 2, 4, bulleted answers; 113 tests pass; [evidence](evidence/CL-17-story-charts.md) | — |
| CL-18 | Narrated pitch video on the architecture page | 5 | ✅ Done | Narrated 1080p pitch (5:03, captions, poster) on the Architecture page; drives the real diagram; own-voice takes; [evidence](evidence/CL-18-pitch-video.md) | — |

Status key: ⬜ To do · 🟡 In progress · ✅ Done · ⛔ Blocked.

# MVP-09 — Observability, release, and interview demo runbook

**Type:** Operations and demo readiness  
**Priority:** P1 (required before sharing a public URL)  
**Estimate:** 3–5 hours  
**Story points:** 3 (logging fields, runbook, and rehearsal; mostly documentation)  

## User story

As the demo owner, I want enough operational visibility and a rehearsed demo path to diagnose failures, control avoidable spend, and present the prototype honestly in an interview.

## Scope

- Add structured Cloud Logging fields for request ID, workflow stage, model ID, latency, token usage if available, Firestore retrieval latency/result count, tool count, result status, and error category.
- Redact prompts/user data by default; never log credentials or hidden chain-of-thought.
- Document Cloud Run limits, Vertex quota checks, budget alert expectations, revision rollback, and cleanup.
- Prepare a 3–5 minute demo runbook plus a local/recorded fallback.

**Out of scope:** full SRE dashboards, on-call rotation, multi-region recovery, SLA, user analytics/retention, or a hard budget kill switch.

## Acceptance criteria

- [ ] Successful and failed requests can be correlated with a request ID in Cloud Logging.
- [ ] Firestore retrieval failures and latency can be distinguished from Vertex AI/model failures without logging full guide text or user prompts.
- [ ] Logs do not include secret values, complete user prompts, or internal model reasoning by default.
- [ ] The deployed Cloud Run service has scale-to-zero and an explicit max-instance setting; relevant budget alerts are configured per MVP-01.
- [ ] The runbook covers checking Cloud Run health/logs, model/API access and quotas, rollback (`make deploy IMAGE=<previous tag>`), and teardown (`make destroy` / `make destroy-all`).
- [ ] Demo script walks through a preference-based plan, simulated conditions/tool use, and an insufficient-evidence or caveat case, and shows at least one city besides San Francisco.
- [ ] UI and spoken demo state that destination content/conditions are sample data and no booking is made.
- [ ] A fallback is available if the network/model quota fails during an interview.

## Dependencies and deliverables

**Dependencies:** MVP-03, MVP-08, and IAC-06.  
**Deliverables:** structured logs, demo/release runbook, rollback/cleanup checklist, and fallback recording or local demo instructions.

## Completion evidence

Run a clean-browser rehearsal and one failure-path rehearsal; capture timing, logs, and issues to fix before sharing the URL.

## Progress record — 🟡 Logging and runbook done, waiting for a rehearsal on Cloud Run (2026-11-06)

Done:
- `weekendwise/observability.py`: one JSON line per event with `requestId`, `stage`, `component` (firestore / vertex-ai), `modelId`, `latencyMs`, token counts, `resultCount`, tool/model counts, `status`, and `errorCategory`. No prompts, notes, guide text, model output, or credentials. Tests prove user notes and queries never appear.
- Request IDs: generated per plan, returned as `X-Request-ID`, shown in the UI footer and error messages. `make logs RID=<id>` / `make logs ERRORS=1`.
- Verified locally: one Portland plan produced correlated `embedding`, `retrieval`, `model call`, `stage`, and `plan finished` lines under a single request ID.
- Scale to zero and max instances are set in Terraform. Budget alerts are from MVP-01.
- [Runbook](../runbook.md): pre-demo checklist, a 3–5 minute demo script (preference plan, simulated conditions/tool, caveat or over-budget case, a city besides San Francisco), troubleshooting split by Firestore vs model, log queries, cost limits, rollback, teardown, and fallback.

Still needed (owner): after the first deploy, a clean-browser rehearsal through `make proxy` and one failure-path rehearsal (e.g. deploy a bad tag, then roll back), with timings and any issues to fix.

**Demo preparation added 2026-11-06:**
- The app's **Architecture** page is the closing step of the runbook's demo script: an interactive diagram with an **i** card on each service and a step-by-step walkthrough (see [MVP-07](MVP-07-traveler-web-screens.md#additions-after-completion-2026-11-06)).
- A root [README](../../../README.md) explains the demo for anyone who clones the repo. It includes the architecture image (`docs/images/architecture.png`, captured from the app), the request flow, the services, guardrails, results, cost, and setup.
- No-network fallback: `make mockups` serves the static mockup with clean page addresses at http://localhost:8000/plan.
- Partly exercised on Cloud Run: `make smoke-cloud` ran one live plan through the deployed service, and the app was opened through `make proxy`. The timed clean-browser rehearsal and the failure-path rehearsal are still to do.

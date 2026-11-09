# MVP-12 — Observability, release and demo runbook

**Type:** Operations + demo readiness  
**Priority:** P1  
**Estimate:** 3–5 hours  
**Story points:** 3 (structured logs, release checklist, runbook and a timed rehearsal)  

## User story

As the demo owner, I want useful, privacy-safe logs, a repeatable release and a short demo script so that I can troubleshoot quickly and present DealPulse confidently in 3–5 minutes.

## Scope

- **Structured JSON logs** from every workflow step: request ID, persona type (not name), deal ID, step, model or endpoint, latency, token counts, guardrail outcome, reviewer outcome, error category. **Never** prompts, note text, brief text or contact details. Bedrock model-invocation logging stays off.
- `make logs` tails `/dealpulse/app` filtered by request ID or step.
- A small CloudWatch Logs Insights query file for: briefs per day, p50/p95 brief latency, Claude calls per brief, guardrail blocks, reviewer failures.
- **Release checklist** in the runbook: offline tests → build → deploy → `make smoke-cloud` → `make evaluate` (when prompts or the model changed) → tag.
- **Runbook** (`docs/mvp/runbook.md`): setup recap, daily start (`make resume`, `make proxy`), the demo script, troubleshooting (cold start, model access, OpenSearch 403, guardrail block), cost checks, `make pause` and teardown.
- **Demo script (3–5 minutes):** Pipeline page and the flagged Commit deal → open the brief and its drivers → click a citation → ask one follow-up → show the injection deal handled safely → Model page (beats the baseline) → Architecture walkthrough to close.
- **Fallback:** if AWS is unavailable, open the static Architecture page and the offline UI fixtures (`OFFLINE=1 make run`).
- Update the app README's status, results and cost sections with measured numbers.

**Out of scope:** dashboards and alarms beyond the budget, tracing with X-Ray or OpenTelemetry, on-call processes.

## Acceptance criteria

- [ ] Every log line is valid JSON with a request ID; an automated test scans a sample run and finds no note text, prompt text or contact details.
- [ ] `make logs REQUEST=<id>` shows all steps for one brief.
- [ ] The Logs Insights queries return results after a test run.
- [ ] The runbook's commands all exist and work; a reviewer can follow it without help.
- [ ] One timed rehearsal on ECS, from a clean browser, completes in under 5 minutes, including one failure path (e.g. cold start or no evidence).
- [ ] The README shows measured results instead of targets.

## Dependencies and deliverables

**Dependencies:** MVP-09, MVP-11, IAC-07.  
**Deliverables:** logging updates, `make logs`, `infra/stack/queries/*.query` (or `docs/`), `docs/mvp/runbook.md`, README updates.

## Completion evidence

The rehearsal notes (timing, what went wrong, fixes) and the log-privacy test result.

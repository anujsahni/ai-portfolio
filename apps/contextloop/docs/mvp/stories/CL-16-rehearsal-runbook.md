# CL-16 — Rehearsal, runbook and Q&A preparation

**Phase:** 5 · Activate and close  
**Type:** Demo readiness  
**Priority:** P0  
**Estimate:** 2–3 hours  
**Story points:** 2  
**Target day:** Sun 15 Nov

## User story

As the presenter, I want a tested runbook, a fallback for every likely failure and answers to the hardest questions, so that the demo on Monday is calm and goes to plan.

## Scope

- **`docs/demo/runbook.md`:** the night-before checklist (pull images, `make demo`, run replay end to end, check the key for live mode, close other apps); the five-minutes-before checklist; how to reset between runs; and what to do if something fails (switch to replay mode, restart one service, use screenshots).
- **Two timed rehearsals** (10-minute and 20-minute versions), recorded in the completion record with the actual times and what was cut or changed.
- **`docs/demo/qa.md`:** prepared answers to likely questions, each in two or three sentences, for example:
  - How does this differ from the native SAP connectors or hybrid deployment, and when would you use each?
  - Why Iceberg, and how does Managed Data Lake Service fit with Snowflake or Databricks?
  - What does dbt MCP give an agent that a schema dump doesn't?
  - How do you stop an agent from following instructions hidden in ticket text?
  - How would you size MAR and cost for this customer?
  - How would you run this as a specialist-team engagement: who owns what, and how do you measure it?
  - What would you change to run this at a customer in production?
- **Interview framing:** a one-page note on how the demo maps to the role (specialties, proofs of value, field enablement, AI workloads), plus how the demo itself could become reusable field enablement material.

**Out of scope:** slides.

## Acceptance criteria

- [ ] From a clean `make clean`, following the runbook ends with the app ready in under 10 minutes.
- [ ] Two rehearsals completed and timed, within 10% of the target length.
- [ ] Each failure in the runbook has been tried once (for example, stopping `mcp-metrics` and switching to replay).
- [x] The Q&A sheet has at least 10 questions with answers checked against the current product documentation.

## Dependencies and deliverables

**Dependencies:** all other stories.  
**Deliverables:** `docs/demo/runbook.md`, `docs/demo/qa.md`, `docs/demo/role-mapping.md`.

## Completion evidence

The rehearsal log with times and the runbook dry-run result.

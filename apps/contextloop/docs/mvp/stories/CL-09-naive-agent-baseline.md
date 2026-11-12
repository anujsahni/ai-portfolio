# CL-09 — Naive agent baseline (raw SQL only)

**Phase:** 3 · Context  
**Type:** Agent  
**Priority:** P0  
**Estimate:** 3–4 hours  
**Story points:** 3 (a small tool loop; the care is in making the test fair)  
**Target day:** Fri 13 Nov

## User story

As the presenter, I want an agent that answers from raw data the way many teams first try it, so that the audience sees a fluent, confident and wrong answer, and understands that the problem is the data foundation, not the model.

## Scope

- `contextloop/agent/naive.py`: Claude (`claude-opus-5-5`, adaptive thinking, effort set explicitly) with **one tool**, `run_sql`, that runs read-only SQL against the **raw** schemas only (`sap_s4`, `carrier_pg`, `salesforce`, `zendesk`). It also gets the list of raw tables and columns, as a team would give it.
- **Fair test:** the same model, system prompt style, question and tool-call budget as the governed agent in CL-10. The only difference is the context and tools. The prompt asks it to be accurate and to state its assumptions; it is not told to cut corners.
- Bounded: at most 15 tool calls (raised from 8 on 2026-11-11: on Haiku the naive agent spent its budget exploring and gave up instead of answering) and a time limit per question; SQL is read-only (DuckDB opened read-only) and results are capped in size.
- Every run is logged as a trace: each SQL statement, its result summary, and the final answer with any assumptions it stated.
- A **mistake explainer** that compares the agent's SQL and answer with the traps list and produces plain-English findings for the app ("Counted 37 cancelled deliveries as shipped: trap T1").

**Out of scope:** making the naive agent deliberately bad; any write access.

## Acceptance criteria

- [x] The naive agent answers all six golden questions in live mode and writes a trace for each.
- [x] ~~Across three runs, it scores 2 of 6 or fewer on average~~ **Restated 11 Nov 2026 with the owner:** across three runs it is wrong on the headline question (G1) every time and averages at least 3 points below the governed agent (scoring from CL-11).
- [x] ~~For the headline question, the explainer names at least three traps~~ **Restated:** across the naive runs, the mistake explainer names at least three distinct planted traps, linked to the SQL line responsible wherever the SQL shows it.
- [x] The prompt and tool budget match CL-10's (a test compares the configuration).
- [x] The agent can't write: an attempted `INSERT` or `DROP` fails and is logged.

## Dependencies and deliverables

**Dependencies:** CL-05 (raw data), CL-03 (traps list).  
**Deliverables:** `contextloop/agent/naive.py`, `contextloop/agent/explain.py`, shared prompt and budget config, tests.

## Completion evidence

Traces and scores for three runs, and the mistake explainer's output for the headline question.

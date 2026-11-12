# CL-11 — Golden-question evaluation and replay recordings

**Phase:** 3 · Context  
**Type:** Evaluation  
**Priority:** P0  
**Estimate:** 3–4 hours  
**Story points:** 3 (scoring rules and a deterministic replay format)  
**Target day:** Fri 13 Nov

## User story

As the presenter, I want each agent's answers scored against the known truth and recorded, so that the comparison in Act 4 is evidence rather than opinion and the demo runs safely with no network.

## Scope

- **Scoring** (`contextloop/eval/`): for each golden question, compare the agent's structured answer with the hidden truth. Lists use exact set match (with precision and recall shown); numbers use a tolerance of 0.5 percentage points or 1%; yes or no questions use exact match. Overall score is out of 6.
- `make eval` runs both agents on all six questions (live mode), three times each, and writes `reports/eval-<date>.md` with scores, averages, cost in tokens, and time per question.
- **Recordings** (`make record`): save each run's full trace (tool calls, tool results, final answer, timings) to `recordings/` as JSON. Recordings are checked in.
- **Replay mode:** the app plays a recording back step by step at a natural pace, without calling Claude or needing a key. Replays show a small "recorded run" label.
- The recording used in the demo is chosen from runs that passed, and its scores are re-checked on load.

**Out of scope:** LLM-as-judge scoring (the truth is exact, so code scoring is enough).

## Acceptance criteria

- [x] `make eval` produces a report with both agents' scores; the governed agent is at least 5 of 6 ~~and the naive agent 2 or fewer~~ **(restated 11 Nov 2026 with the owner:** the naive agent at least 3 points lower and wrong on G1 in every run).
- [x] `make record` writes recordings for both agents on all six questions.
- [x] With no network and no API key, `CONTEXTLOOP_MODE=replay` plays every recording and shows the same scores as the report.
- [x] A test fails if a recording's stored answer no longer matches the current hidden truth (for example after a data change).

## Dependencies and deliverables

**Dependencies:** CL-09, CL-10.  
**Deliverables:** `contextloop/eval/`, `make eval`, `make record`, `recordings/`, the replay player, `reports/`.

## Completion evidence

The evaluation report and a screenshot of a replayed run.

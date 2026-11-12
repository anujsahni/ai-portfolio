# CL-09 and CL-11 evidence — Naive baseline, evaluation and replay

**Date:** 11 Nov 2026 · **Model:** claude-haiku-5-5, effort high · **Runs:** 3 per question per agent, recorded live with `make record`, re-scored in replay with `make eval` · **Report:** [reports/eval-2026-11-12.md](../../../reports/eval-2026-11-12.md) (container clock is UTC)

## The bar, restated with the owner (11 Nov 2026)

The original bar asked the naive agent to score **2 or fewer of 6** and the explainer to name **3 or more traps on G1**. The recorded runs score naive 2, 3, 3 (average **2.7**). The naive agent gets the arithmetic questions right more often than planned (G3 revenue 3 of 3, G5 freshness 3 of 3). It is never right on the headline list. Rigging the agent to fail more often would make the demo dishonest, so the owner agreed to restate the bar as what the demo actually proves:

- **The gap:** governed at least 5 of 6 on average, naive at least **3 points** lower.
- **The headline:** the naive agent is wrong on G1 in **every** run.
- **Traceable mistakes:** across the naive runs, the explainer names at least three distinct planted traps.

The bar is coded in `contextloop/eval/run.py::passes` and tested in `tests/test_agents.py::test_pass_bar_is_the_gap_and_the_headline_list`.

## Result

| Agent | Run 1 | Run 2 | Run 3 | Average |
|---|---|---|---|---|
| naive | 2 | 3 | 3 | **2.7** |
| governed | 6 | 6 | 6 | **6.0** |

Report verdict: governed 6.0, naive 2.7 (gap 3.3), naive wrong on G1 in 3 of 3 runs → **pass**.

## Traps the explainer ties to the naive runs

| Question | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| G1 | wrong list, no named trap | T5 | T1, T5 |
| G2 | T4 | T1, T4 | T4 |
| G3 | T4, T6 | T4 | T4, T5 |
| G4 | T4, T5 | T4, T5 | T4, T5 |
| G5 | T1, T4, T5 | T1, T4, T5 | T1, T4, T5 |
| G6 | T1, T4, T5 | T4, T5 | T4, T5 |

Distinct traps named: **T1, T4, T5, T6** (four of six). T2 (planned vs actual date) and T3 (currency) did not trip the naive agent in these runs: it found the carrier's delivered event and converted EUR on its own. **Disclosed limit:** on G1 run 1 the list is wrong, but the explainer can't attribute the error to a planted trap; it reports it as "the list itself".

## Acceptance criteria

**CL-09**
- [x] Live answers and a trace for all six questions: `recordings/runs/naive/G1-r1.json` … `G6-r3.json` (18 traces).
- [x] Restated score bar: wrong on G1 in 3 of 3 runs; average 2.7 vs governed 6.0.
- [x] Restated trap bar: four distinct traps named, tied to SQL lines where the SQL shows them (table above).
- [x] Same prompt and budget as CL-10: `test_prompts_share_everything_but_context_and_tools`, `test_both_agents_use_one_runner_configuration`.
- [x] Can't write: `test_naive_agent_cannot_write` (DROP, INSERT, DELETE refused and logged).

**CL-11**
- [x] `make eval` writes the report with both agents' scores and the restated pass bar (**pass**).
- [x] `make record` wrote 3 runs × 6 questions for both agents, plus the demo picks in `recordings/demo/`.
- [x] Replay plays every recording with no network or key, and the app shows the report's averages (`test_scorecard_scores_match_the_evaluation_report`, `test_page_renders_without_errors`).
- [x] A test fails if a stored answer drifts from the truth: `test_recorded_scores_still_match_the_current_truth`.

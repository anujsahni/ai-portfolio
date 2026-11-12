# CL-12 completion record: Streamlit story mode, the five acts

**Date:** 11 Nov 2026 · **Result:** all acceptance criteria met. One criterion, the presenter's full timed run, is met by the app; the timing itself is measured by a person in CL-16's rehearsals.

| Criterion | Evidence |
|---|---|
| All five acts work end to end in replay mode with no network | Replay plays `recordings/demo/` (Haiku, three-run recording of 11 Nov). Acts 2, 3 and 5 use only the local stack and the mock CRM. Screenshots of every act are in [CL-12-screens/](CL-12-screens/). |
| Each act loads in under 2 s (warm) | Measured in Chrome with Playwright, second visit: home 0.49 s · Act 1 0.48 s · Act 2 0.43 s · Act 3 0.37 s · Act 4 0.45 s · Act 5 0.40 s · scorecard 0.37 s · architecture 0.46 s. |
| "Run incremental sync" and "Break it" run real jobs | `scripts/capture_guide.py` pressed both. The sync landed SAP batch 2 and `ZZ_CARRIER_ID` (`04-act2-incremental-sync.png`). Break it failed a named dbt test, then restored the build (`06-act3-break-it.png`). |
| Side-by-side comparison shows both answers, both scores and the traps behind each naive mistake | Act 4, checked through Streamlit's testing API after **Ask the governed agent**: both columns show an answer and a Correct/Wrong score, and the naive column lists "Traps behind its mistakes" (T1, T5 for the replayed G1). A caption under the six-question board gives the three-run averages from the evaluation report. |
| A presenter can go from Act 1 to Act 5 using only the navigator | The sidebar navigator and the next/previous buttons on every page reach every act. The automated walkthrough above did the full path, including the jobs. The timed rehearsals against the talk track are part of CL-16. |
| UI tests cover each act's main path | `tests/test_ui.py`: every page renders without errors, the main buttons work, and the scorecard matches the evaluation report. 109 tests pass in total. |

## Changes made while closing the story

- **Step descriptions.** Each tool call in Acts 1 and 4 is labelled in plain English (`contextloop/ui/step_describe.py`), for example "Counts and summarises Salesforce accounts, grouped by tier_c". Failed steps say why: a syntax error, a missing column, or the query budget used up. New naive runs also record the agent's own purpose for each query.
- **Act 4 averages caption.** The demo replays the naive agent's wrong runs, so the board alone would understate it. The caption gives the averages over all recorded runs.

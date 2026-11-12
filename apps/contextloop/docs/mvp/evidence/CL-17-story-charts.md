# CL-17 evidence — Story charts and the "without vs with the stack" view

**Date:** 11 Nov 2026 · **Mode:** replay (recorded runs, no network) · **Screens:** [CL-17-screens/](CL-17-screens/), captured from the running app in headless Chrome

## What was built

| Where | What it shows |
|---|---|
| New page **The difference: without vs with** (`/difference`, step 7 of 8) | Two columns, same model and questions: score (2 vs 6 of 6), the data path, and four judged facts per agent (headline accounts, governed definitions, lineage through dbt models, freshness). The account-by-account chart, all six questions, and "what each layer fixes" (T1–T6, with the traps hit in these runs marked). |
| Opening page | "On-time delivery to strategic accounts has fallen to 84%": monthly trend against the 85% threshold; a "Where this ends" card linking to the comparison. |
| Act 1 | Answer as bullets; "It looks right. It isn't.": the agent's accounts and rates against the trusted model, with a verdict per account. |
| Act 2 | Days since each source's last successful sync against the 24-hour window (Zendesk 2.4 days behind). |
| Act 4 | Answer as bullets; the nine at-risk accounts as bars from 0% with the 85% line; a link to the comparison page. |

## Acceptance criteria

- [x] **Reads from the recordings and the hidden truth, no live call.** The page uses the replay recordings, `truth.json`, `traps.json`, the `account_risk` mart and the dbt semantic manifest.
- [x] **Every number matches the scorer and the marts.** `tests/test_ui.py::test_compare_view_agrees_with_the_scorer` checks wrong and missed accounts against `score()`, the per-agent totals, the truly at-risk set, and that only the governed agent's definitions are governed and only it flags Zendesk. Citations are judged, not counted: the naive answer lists 5 definitions (its own wording, 0 governed), 3 lineage paths (raw tables only) and a freshness check that missed Zendesk, and the page shows each as a failure.
- [x] **Each chart states its point, has a legend or direct labels, and a table view.** Titles are the finding ("…has fallen to 84%", "Zendesk is behind…"). Verdicts carry a symbol and a word as well as color (the green and red pair is in the CVD floor band, so color alone is never used). Table views exist on the opening page and the comparison page, and the account detail is in the bullets and the expander on Acts 1 and 4.
- [x] **Renders in replay mode with no errors.** AppTest renders all nine pages without an exception; the browser capture found no `stException` on any of the five screens.

## Tests

`make test`: **113 passed** (new: `test_compare_view_agrees_with_the_scorer`, `test_answer_bullets_split_sentences_and_list_accounts_worst_first`, and `compare` added to the page-render test).

## Found while checking the screens

- A rightly-excluded account (Vornridge for the governed agent) was first labelled "Missed": added the "Correctly left out" verdict; the scorer test caught it.
- The naive agent's on-time *rates* match the trusted ones; its error is which accounts count. The sentence under the chart is now generated from the data rather than asserted.
- The threshold rule forced the trend chart's y-axis to start at 0%, flattening the decline: fixed.

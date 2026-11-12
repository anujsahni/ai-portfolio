# CL-15 completion record: proof-of-value scorecard and specialist view

**Date:** 11 Nov 2026 · **Result:** all acceptance criteria met. Screenshot: [`11-scorecard.png`](../../images/guide/11-scorecard.png).

All eight success criteria pass on the current stack:

| ID | Criterion | Result | Proved in |
|---|---|---|---|
| SC1 | Headline question answered with the exact at-risk accounts | Pass: exact list of 9 accounts | Act 4 |
| SC2 | Governed ≥ 5 of 6 on the golden set and beats the baseline | Pass: governed 6/6 vs naive 2.7/6 (average of 3 runs, evaluation report) | Act 4 |
| SC3 | SAP replicates incrementally, with soft deletes | Pass: 10 incremental syncs, 310 soft-deleted deliveries kept | Act 2 |
| SC4 | A new SAP column flows through with no code change | Pass: `LIKP.ZZ_CARRIER_ID` landed | Act 2 |
| SC5 | One tested definition of on-time delivery | Pass: defined once; 89 nodes built and tested, 0 failing | Act 3 |
| SC6 | The agent knows when data is stale | Pass: the answer flags Zendesk as two days old | Act 4 |
| SC7 | One open-format copy read by two engines | Pass: Iceberg table with 19 snapshots; DuckDB and Trino identical | Act 3 |
| SC8 | The answer reaches the CRM with an audit trail | Pass: 9 audited CRM writes from `marts.account_risk` | Act 5 |

- **Every criterion links to the act that proves it.** Each row has an **Evidence** link, and `test_ui.py` checks that every `evidence` value in `pov.yml` is an act.
- **Scores match the evaluation report (test).** SC2 now reads `reports/latest.json`, the average over every recorded run. It used to score the demo recordings, which are picked from the naive agent's wrong runs and gave 2/6 against the report's 2.7. `test_scorecard_scores_match_the_evaluation_report` checks this.
- **MAR figures match the sync log.** They are computed from `fivetran_log`, as before.
- **Specialist map** covers the six specialties named in the README.
- **Cost figures** are labelled as estimates and listed with their assumptions.
- **Static fallback.** [`docs/demo/pov-scorecard.md`](../../demo/pov-scorecard.md) was regenerated with `python -m contextloop.ui.scorecard_data`.

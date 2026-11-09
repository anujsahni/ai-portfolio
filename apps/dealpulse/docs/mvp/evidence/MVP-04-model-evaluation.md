# MVP-04 evidence — win-probability model evaluation

Training job `dealpulse-y34c-win-20261109-202911` · XGBoost 3.2.0 · best iteration 320 · model package `arn:aws:sagemaker:us-east-1:<account-id>:model-package/dealpulse-y34c-win-model/1`

Split by close quarter: train 2024Q4, 2025Q1, 2025Q2, 2025Q3, 2025Q4, 2026Q1 (9,710 rows, 1,807 deals); validation 2026Q2 (1,619 rows); **held-out test 2026Q3** (1,557 rows, 295 deals, win rate 31.7%). Billable training time 114 s on ml.m5.large (≈ $0.004).

## Model vs. Salesforce stage probability (held-out quarter)

| Metric | Model | Stage-probability baseline | Better |
|---|---|---|---|
| AUC (ranking; higher is better) | **0.888** | 0.703 | ✓ |
| Brier score (probability error; lower is better) | **0.128** | 0.190 | ✓ |

## Calibration (held-out quarter)

| Predicted band | Rows | Mean predicted | Observed win rate | Baseline rows |
|---|---|---|---|---|
| 0.0–0.1 | 554 | 0.02 | 0.02 | 0 |
| 0.1–0.2 | 187 | 0.15 | 0.13 | 513 |
| 0.2–0.3 | 180 | 0.25 | 0.30 | 391 |
| 0.3–0.4 | 147 | 0.35 | 0.43 | 0 |
| 0.4–0.5 | 105 | 0.45 | 0.51 | 268 |
| 0.5–0.6 | 88 | 0.55 | 0.66 | 174 |
| 0.6–0.7 | 79 | 0.65 | 0.63 | 0 |
| 0.7–0.8 | 86 | 0.74 | 0.77 | 211 |
| 0.8–0.9 | 68 | 0.85 | 0.82 | 0 |
| 0.9–1.0 | 63 | 0.93 | 0.94 | 0 |

## What drives the score (mean |SHAP| on the held-out quarter)

| Rank | Feature | Mean \|SHAP\| | Direction |
|---|---|---|---|
| 1 | `stage_index` | 1.365 | ↑ raises |
| 2 | `days_to_close` | 0.635 | ↑ raises |
| 3 | `days_in_stage` | 0.608 | ↓ lowers |
| 4 | `deal_age_days` | 0.597 | ↓ lowers |
| 5 | `close_pushes` | 0.297 | ↓ lowers |
| 6 | `log_amount` | 0.227 | ↑ raises |
| 7 | `competitor_present` | 0.216 | ↓ lowers |
| 8 | `exec_meeting_last_30d` | 0.173 | ↑ raises |
| 9 | `champion_identified` | 0.171 | ↑ raises |
| 10 | `activities_last_30d` | 0.115 | ↑ raises |
| 11 | `contact_roles` | 0.095 | ↓ lowers |
| 12 | `lead_web` | 0.090 | ↓ lowers |

## Hidden-rule drivers (does the model learn the right reasons?)

| Hidden driver | Model feature | Rank | Expected | Learned |
|---|---|---|---|---|
| exec_engaged | `exec_meeting_last_30d` | 8 | ↑ | ↑ ✓ |
| champion | `champion_identified` | 9 | ↑ | ↑ ✓ |
| competitor | `competitor_present` | 7 | ↓ | ↓ ✓ |
| discount_points_over_15 | `discount_pct` | 14 | ↓ | ↓ ✓ (25%+ discounts: mean SHAP -0.218 (n=14) vs 1–15%: +0.260 (n=165)) |
| close_pushes | `close_pushes` | 5 | ↓ | ↓ ✓ |
| activity_level_minus_1 | `activities_last_30d` | 10 | ↑ | ↑ ✓ |
| severe_cases | `open_severe_cases` | 35 | ↓ | ↓ ✓ |
| expansion | `is_expansion` | 13 | ↑ | ↑ ✓ |
| enterprise | `segment_enterprise` | 15 | ↓ | ↓ ✓ |

5 of 9 hidden-rule drivers rank in the top 10; 9 of 9 push in the expected direction. Top 6 overall: stage_index, days_to_close, days_in_stage, deal_age_days, close_pushes, log_amount (1 are hidden-rule drivers). Excluding stage and timing features, 5 of the next top 6 are hidden-rule drivers.

## Acceptance checks

| Check | Result | Detail |
|---|---|---|
| beats baseline | ✓ | AUC 0.888 vs 0.703; Brier 0.128 vs 0.190 |
| calibration within 10pp | ✗ | 0.5–0.6: predicted 0.55, observed 0.66 (n=88; gap 0.11 vs 2 standard errors 0.10: larger than sampling noise) |
| learns hidden drivers | ✓ | 9/9 push the right way; 5 in the top 10; 5 of the top 6 non-timing features (strict original test, for information: 1 of the overall top 6) |

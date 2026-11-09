# MVP-04 — Win-probability model: features, training, evaluation, registry

**Type:** Machine learning  
**Priority:** P0  
**Estimate:** 8–12 hours  
**Story points:** 8 (shared features, SageMaker training and inference scripts, time-based evaluation, registry flow)  

## User story

As a RevOps analyst, I want a win-probability model trained on past deals and tested against Salesforce's stage-based probability so that I can trust the score more than the stage default, or know when not to.

## Scope

- `dealpulse/features.py`: the ~20 features in [design §4](../../design.md#4-the-scoring-model-sagemaker-ai), computed from a deal's state as of a date. Imported by both training and serving. Excludes owner, rep win rate, `Probability`, `ForecastCategoryName` and free text.
- `ml/train.py` (SageMaker XGBoost framework container, script mode): reads `training/` from S3, splits **by time** (quarters 1–6 train, 7 validate with early stopping, 8 held-out test), trains a binary classifier and saves the model plus a feature list.
- `ml/inference.py`: accepts one or many feature rows as JSON and returns probability and per-feature SHAP contributions (`pred_contribs`) in one response.
- `ml/evaluate.py`: on quarter 8, computes AUC and Brier score for the model and for the **stage-probability baseline**, a calibration table (10 bins) and the top features by mean |SHAP|; compares top features with `hidden_rule.json`. Writes `reports/model/<run-id>.json` and a Markdown summary.
- `make train`: uploads code, starts a SageMaker Training job on `ml.m5.large` as `dealpulse-training`, waits, runs evaluation and **registers a model package** in `dealpulse-win-model` with status `PendingManualApproval` and the metrics attached.
- `make approve-model MODEL=<arn>`: shows the metrics and asks for confirmation before setting `Approved`.
- Write guide 04 (SageMaker: training, registry and endpoint).

**Out of scope:** hyperparameter tuning jobs, Autopilot, feature store, model monitoring, retraining schedules and deep learning models.

## Acceptance criteria

- [ ] `make train` finishes in under 15 minutes and costs under $0.50 (recorded), registering a pending model package with metrics.
- [ ] On the held-out quarter, the model's **AUC and Brier score are both better** than the stage-probability baseline; numbers are in the evaluation report.
- [ ] Calibration: in each bin with ≥ 50 rows, the mean predicted probability is within 10 percentage points of the observed win rate (or the report explains why not).
- [ ] The model learns the hidden rule's drivers: all 9 push in the expected direction, at least 4 rank in the top 10 by mean |SHAP|, and at least 4 of the top 6 *non-timing* features (excluding stage, days in stage, deal age, days to close) are drivers. *Revised 2026-11-09 with the owner's approval; was "at least 4 of the top 6 features are hidden-rule drivers". Stage and timing features rank first because a deal's progress partly results from the drivers (losing deals stall), so the original test mostly measured that. The strict count is still printed in the report.*
- [ ] Unit tests prove the feature code gives identical results for the same deal and date whether called from training or serving code paths, and that no feature uses data after the snapshot date.
- [ ] `inference.py` returns probability + contributions for 1 and for 60 rows; contributions plus base value sum to the model's raw score (within tolerance).
- [ ] A package can't be deployed until `make approve-model` has approved it (enforced together with IAC-05).

## Dependencies and deliverables

**Dependencies:** MVP-03, IAC-05.  
**Deliverables:** `dealpulse/features.py`, `ml/train.py`, `ml/inference.py`, `ml/evaluate.py`, make targets, unit tests, `docs/mvp/evidence/MVP-04-model-evaluation.md`, guide 04.

## Completion evidence

The evaluation report: AUC and Brier vs. baseline, calibration table, top drivers vs. hidden rule, training time and cost.

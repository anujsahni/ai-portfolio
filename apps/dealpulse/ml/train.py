"""Train and evaluate the DealPulse win-probability model (SageMaker XGBoost container, script mode).

Input  (channel "train"): rows.csv from `make data`: one point-in-time snapshot per row, with
        opportunity_id, snapshot_date, close_quarter, is_won, stage_probability and the feature columns.
Split  by close quarter so no deal appears in two splits and the test is "the future":
        oldest quarters → train, next-to-last → validation (early stopping), last → held-out test.
Output (model dir): xgboost-model.json, features.json, evaluation.json (also copied to the output dir).

Runs the same way locally:
    SM_CHANNEL_TRAIN=data/out/training SM_MODEL_DIR=/tmp/m SM_OUTPUT_DATA_DIR=/tmp/o python ml/train.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import auc, brier, calibration_table  # noqa: E402

META_COLUMNS = ["opportunity_id", "snapshot_date", "close_quarter", "is_won", "stage_probability"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--max_depth", type=int, default=4)
    p.add_argument("--eta", type=float, default=0.05)
    p.add_argument("--num_round", type=int, default=800)
    p.add_argument("--early_stopping_rounds", type=int, default=50)
    p.add_argument("--subsample", type=float, default=0.8)
    p.add_argument("--colsample_bytree", type=float, default=0.8)
    p.add_argument("--min_child_weight", type=float, default=5)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--train", default=os.environ.get("SM_CHANNEL_TRAIN", "data/out/training"))
    p.add_argument("--model_dir", default=os.environ.get("SM_MODEL_DIR", "model"))
    p.add_argument("--output_dir", default=os.environ.get("SM_OUTPUT_DATA_DIR", "output"))
    return p.parse_args()


def split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    quarters = sorted(df["close_quarter"].unique())
    if len(quarters) < 3:
        raise SystemExit(f"Need at least 3 close quarters, found {quarters}")
    test_q, valid_q, train_q = quarters[-1], quarters[-2], quarters[:-2]
    parts = (df[df["close_quarter"].isin(train_q)], df[df["close_quarter"] == valid_q], df[df["close_quarter"] == test_q])
    return (*parts, {"train": train_q, "validation": [valid_q], "test": [test_q]})


def main() -> None:
    args = parse_args()
    df = pd.read_csv(Path(args.train) / "rows.csv")
    features = [c for c in df.columns if c not in META_COLUMNS]
    train, valid, test, quarters = split(df)

    dtrain = xgb.DMatrix(train[features], label=train["is_won"], feature_names=features)
    dvalid = xgb.DMatrix(valid[features], label=valid["is_won"], feature_names=features)
    dtest = xgb.DMatrix(test[features], label=test["is_won"], feature_names=features)
    params = {
        "objective": "binary:logistic", "eval_metric": ["logloss", "auc"], "max_depth": args.max_depth,
        "eta": args.eta, "subsample": args.subsample, "colsample_bytree": args.colsample_bytree,
        "min_child_weight": args.min_child_weight, "seed": args.seed, "tree_method": "hist",
    }
    booster = xgb.train(params, dtrain, num_boost_round=args.num_round, evals=[(dvalid, "validation")],
                        early_stopping_rounds=args.early_stopping_rounds, verbose_eval=100)
    best = booster.best_iteration + 1

    prob = booster.predict(dtest, iteration_range=(0, best))
    contribs = booster.predict(dtest, pred_contribs=True, iteration_range=(0, best))  # last column = bias
    mean_abs = np.abs(contribs[:, :-1]).mean(axis=0)
    importance = sorted(zip(features, mean_abs.tolist()), key=lambda kv: -kv[1])
    # Direction of each feature's effect: does a higher value push the probability up (+1) or down (-1)?
    xs = test[features].to_numpy(dtype=float)
    direction = {}
    for i, name in enumerate(features):
        if xs[:, i].std() > 0 and contribs[:, i].std() > 0:
            direction[name] = float(np.sign(np.corrcoef(xs[:, i], contribs[:, i])[0, 1]))
    # Discounts are only recorded from Proposal stage on, so "any discount" also means "got far".
    # Compare deep discounts with modest ones instead of the overall direction.
    discount_effect = None
    if "discount_pct" in features:
        k = features.index("discount_pct")
        modest = (xs[:, k] > 0) & (xs[:, k] <= 15)
        deep = xs[:, k] >= 25
        if modest.any() and deep.any():
            discount_effect = {"modest_1_15": float(contribs[modest, k].mean()), "deep_25_plus": float(contribs[deep, k].mean()),
                               "n_modest": int(modest.sum()), "n_deep": int(deep.sum())}
    y = test["is_won"].to_numpy()
    baseline = test["stage_probability"].to_numpy()

    evaluation = {
        "algorithm": f"XGBoost {xgb.__version__}", "best_iteration": best, "hyperparameters": params,
        "quarters": quarters,
        "rows": {"train": len(train), "validation": len(valid), "test": len(test)},
        "deals": {"train": int(train["opportunity_id"].nunique()), "validation": int(valid["opportunity_id"].nunique()),
                  "test": int(test["opportunity_id"].nunique())},
        "test_win_rate": float(y.mean()),
        "model": {"auc": auc(y, prob), "brier": brier(y, prob)},
        "baseline_stage_probability": {"auc": auc(y, baseline), "brier": brier(y, baseline)},
        "calibration": calibration_table(y, prob),
        "baseline_calibration": calibration_table(y, baseline),
        "top_features": [{"feature": f, "mean_abs_shap": v} for f, v in importance[:12]],
        "feature_effects": [{"feature": f, "rank": r + 1, "mean_abs_shap": v, "direction": direction.get(f)}
                            for r, (f, v) in enumerate(importance)],
        "discount_effect": discount_effect,
    }
    model_dir, output_dir = Path(args.model_dir), Path(args.output_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    booster.save_model(model_dir / "xgboost-model.json")
    (model_dir / "features.json").write_text(json.dumps({"features": features, "best_iteration": best}))
    for folder in (model_dir, output_dir):
        (folder / "evaluation.json").write_text(json.dumps(evaluation, indent=2))
    print(json.dumps({k: evaluation[k] for k in ("model", "baseline_stage_probability", "rows")}, indent=2))


if __name__ == "__main__":
    main()

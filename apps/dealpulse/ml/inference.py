"""Serve the win-probability model on SageMaker (XGBoost container, script mode).

Request  (application/json): {"features": [names in order], "rows": [[values], ...]}   (1–100 rows)
Response (application/json): {"predictions": [{"probability": p, "base_value": b,
                                               "contributions": {feature: value, ...}}, ...]}
`base_value + sum(contributions)` equals the model's raw score (log-odds) for that row, so every
probability can be explained feature by feature (SHAP values from XGBoost's pred_contribs).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import xgboost as xgb

MAX_ROWS = 100


def model_fn(model_dir: str):
    booster = xgb.Booster()
    booster.load_model(str(Path(model_dir) / "xgboost-model.json"))
    meta = json.loads((Path(model_dir) / "features.json").read_text())
    return {"booster": booster, "features": meta["features"], "best": meta["best_iteration"]}


def input_fn(request_body, content_type: str = "application/json") -> dict:
    if content_type != "application/json":
        raise ValueError(f"Unsupported content type {content_type}; send application/json")
    body = json.loads(request_body)
    if not isinstance(body, dict) or "rows" not in body or "features" not in body:
        raise ValueError('Request must be {"features": [...], "rows": [[...], ...]}')
    if not 1 <= len(body["rows"]) <= MAX_ROWS:
        raise ValueError(f"Send between 1 and {MAX_ROWS} rows")
    return body


def predict_fn(body: dict, model: dict) -> list[dict]:
    if body["features"] != model["features"]:
        raise ValueError("Feature names or order don't match the model; rebuild rows with dealpulse.features")
    rows = np.asarray(body["rows"], dtype=float)
    if rows.ndim != 2 or rows.shape[1] != len(model["features"]):
        raise ValueError(f"Each row needs {len(model['features'])} values")
    data = xgb.DMatrix(rows, feature_names=model["features"])
    rng = (0, model["best"])
    contribs = model["booster"].predict(data, pred_contribs=True, iteration_range=rng)
    out = []
    for row in contribs:
        margin = float(row.sum())
        out.append({
            "probability": 1 / (1 + math.exp(-margin)),
            "base_value": float(row[-1]),
            "contributions": {name: float(v) for name, v in zip(model["features"], row[:-1])},
        })
    return out


def output_fn(predictions: list[dict], accept: str = "application/json"):
    return json.dumps({"predictions": predictions}), "application/json"

#!/usr/bin/env python3
"""Score feature rows with a trained model through ml/inference.py (runs where XGBoost is installed).

Usage: python scripts/score_rows.py MODEL_DIR ROWS_IN.json SCORES_OUT.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
import inference  # noqa: E402

model_dir, rows_in, scores_out = sys.argv[1:4]
model = inference.model_fn(model_dir)
data = json.loads(Path(rows_in).read_text())
deals = []
for start in range(0, len(data["rows"]), inference.MAX_ROWS):
    chunk = data["rows"][start:start + inference.MAX_ROWS]
    body = inference.input_fn(json.dumps({"features": data["features"], "rows": [r["values"] for r in chunk]}), "application/json")
    for row, pred in zip(chunk, inference.predict_fn(body, model)):
        deals.append({**row, **pred})
Path(scores_out).write_text(json.dumps({"features": data["features"], "deals": deals}))
print(f"scored {len(deals)} deals")

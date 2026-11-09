#!/usr/bin/env python3
"""MVP-04: exercise ml/inference.py against a locally trained model (run inside the check container).

Loads the model the way SageMaker does (model_fn), sends 1 and 60 rows through input_fn/predict_fn/
output_fn, and checks that base value + contributions add up to each row's log-odds.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
import inference  # noqa: E402


def main(model_dir: str, rows_csv: str) -> int:
    model = inference.model_fn(model_dir)
    with open(rows_csv) as fh:
        reader = csv.DictReader(fh)
        rows = [r for _, r in zip(range(60), reader)]
    feats = model["features"]
    matrix = [[float(r[f]) for f in feats] for r in rows]
    ok = True
    for n in (1, 60):
        body = inference.input_fn(json.dumps({"features": feats, "rows": matrix[:n]}), "application/json")
        preds = inference.predict_fn(body, model)
        payload, ctype = inference.output_fn(preds, "application/json")
        decoded = json.loads(payload)["predictions"]
        worst = max(abs(1 / (1 + math.exp(-(p["base_value"] + sum(p["contributions"].values())))) - p["probability"])
                    for p in decoded)
        good = len(decoded) == n and worst < 1e-6 and ctype == "application/json"
        ok &= good
        print(f"{'✓' if good else '✗'} {n} row(s): {len(decoded)} predictions; contributions add up (max error {worst:.1e}); "
              f"first probability {decoded[0]['probability']:.3f}")
    for bad, label in ((json.dumps({"features": feats[::-1], "rows": matrix[:1]}), "wrong feature order"),
                       (json.dumps({"features": feats, "rows": []}), "no rows"),
                       ("[1,2,3]", "wrong shape")):
        try:
            inference.predict_fn(inference.input_fn(bad, "application/json"), model)
            print(f"✗ {label} was accepted"); ok = False
        except ValueError as exc:
            print(f"✓ {label} rejected: {exc}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))

"""MVP-04: evaluation metrics and report logic (no AWS calls, no XGBoost needed)."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from dealpulse import model_report

spec = importlib.util.spec_from_file_location("metrics", Path(__file__).parents[1] / "ml" / "metrics.py")
metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)


def test_auc_known_values():
    assert metrics.auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert metrics.auc([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1]) == 0.0
    assert metrics.auc([0, 1], [0.5, 0.5]) == 0.5           # ties count half
    assert metrics.auc([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]) == pytest.approx(0.75)


def test_brier_and_calibration():
    assert metrics.brier([1, 0], [1.0, 0.0]) == 0.0
    assert metrics.brier([1, 0], [0.5, 0.5]) == 0.25
    rows = metrics.calibration_table(np.array([0, 1, 1, 0]), np.array([0.05, 0.95, 0.91, 0.12]))
    assert sum(r["n"] for r in rows) == 4
    assert rows[9]["observed_rate"] == 1.0 and rows[0]["observed_rate"] == 0.0


def _evaluation(order, directions, discount=None):
    return {
        "model": {"auc": 0.88, "brier": 0.13}, "baseline_stage_probability": {"auc": 0.70, "brier": 0.19},
        "calibration": [{"bin": "0.5–0.6", "n": 80, "mean_predicted": 0.55, "observed_rate": 0.60}],
        "feature_effects": [{"feature": f, "rank": i + 1, "mean_abs_shap": 1 / (i + 1), "direction": directions.get(f, 1.0)}
                            for i, f in enumerate(order)],
        "discount_effect": discount,
        "algorithm": "XGBoost 3.2.0", "best_iteration": 300, "test_win_rate": 0.3,
        "quarters": {"train": ["2025Q1"], "validation": ["2025Q2"], "test": ["2025Q3"]},
        "rows": {"train": 100, "validation": 20, "test": 20}, "deals": {"train": 10, "validation": 2, "test": 2},
        "baseline_calibration": [{"bin": "0.5–0.6", "n": 80, "mean_predicted": 0.6, "observed_rate": 0.5}],
    }


ALL = ["stage_index", "close_pushes", "exec_meeting_last_30d", "competitor_present", "champion_identified",
       "activities_last_30d", "is_expansion", "segment_enterprise", "discount_pct", "open_severe_cases",
       "economic_buyer_identified", "activity_trend_30d", "days_to_close"]
RIGHT = {"close_pushes": -1.0, "competitor_present": -1.0, "segment_enterprise": -1.0, "discount_pct": -1.0,
         "open_severe_cases": -1.0}


def test_driver_check_counts_rule_drivers_and_directions():
    ev = _evaluation(ALL, RIGHT)
    d = model_report.driver_check(ev)
    assert d["rule_drivers_in_top6"] == 5         # all but stage_index
    assert d["directions_ok"] == len(model_report.RULE_FEATURES)
    ok = model_report.checks(ev)
    assert ok["beats_baseline"][0] and ok["calibration_within_10pp"][0] and ok["learns_hidden_drivers"][0]


def test_wrong_direction_is_caught():
    d = model_report.driver_check(_evaluation(ALL, {**RIGHT, "competitor_present": 1.0}))
    assert d["directions_ok"] == len(model_report.RULE_FEATURES) - 1


def test_discount_uses_deep_vs_modest_comparison():
    confounded = {**RIGHT, "discount_pct": 1.0}   # overall "any discount" looks positive
    deep_hurts = {"modest_1_15": 0.26, "deep_25_plus": -0.22, "n_modest": 165, "n_deep": 14}
    d = model_report.driver_check(_evaluation(ALL, confounded, deep_hurts))
    assert next(x for x in d["drivers"] if x["driver"] == "discount_points_over_15")["direction_ok"]


def test_report_renders():
    text = model_report.markdown(_evaluation(ALL, RIGHT), job="job-1", package_arn="arn:x", cost_note="")
    assert "Model vs. Salesforce stage probability" in text and "| beats baseline | ✓ |" in text

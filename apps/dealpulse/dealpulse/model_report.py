"""Turn a training run's evaluation.json into the MVP-04 checks and a readable report.

Compares the model with Salesforce's stage-probability baseline and with the generator's hidden
rule (data/generator/hidden_rule.json), which only evaluation may read.
"""
from __future__ import annotations

import re

# Hidden-rule driver → (model features that express it, expected direction of effect).
RULE_FEATURES = {
    "exec_engaged": (["exec_meeting_last_30d", "economic_buyer_identified"], +1),
    "champion": (["champion_identified"], +1),
    "competitor": (["competitor_present"], -1),
    "discount_points_over_15": (["discount_pct"], -1),
    "close_pushes": (["close_pushes"], -1),
    "activity_level_minus_1": (["activities_last_30d", "activity_trend_30d"], +1),
    "severe_cases": (["open_severe_cases"], -1),
    "expansion": (["is_expansion"], +1),
    "enterprise": (["segment_enterprise"], -1),
}
TIMING_FEATURES = {"stage_index", "days_to_close", "days_in_stage", "deal_age_days"}


def driver_check(evaluation: dict) -> dict:
    effects = {e["feature"]: e for e in evaluation["feature_effects"]}
    rule_feature_set = {f for feats, _ in RULE_FEATURES.values() for f in feats}
    top6 = [e["feature"] for e in evaluation["feature_effects"][:6]]
    drivers = []
    for driver, (feats, expected) in RULE_FEATURES.items():
        best = min((effects[f] for f in feats if f in effects), key=lambda e: e["rank"])
        direction, note = best["direction"], ""
        de = evaluation.get("discount_effect")
        if driver == "discount_points_over_15" and de:
            # The rule only penalises discounts above 15%: compare deep (25%+) with modest (1–15%) discounts.
            direction = -1.0 if de["deep_25_plus"] < de["modest_1_15"] else 1.0
            note = (f"25%+ discounts: mean SHAP {de['deep_25_plus']:+.3f} (n={de['n_deep']}) vs "
                    f"1–15%: {de['modest_1_15']:+.3f} (n={de['n_modest']})")
        drivers.append({
            "driver": driver, "feature": best["feature"], "rank": best["rank"],
            "expected_direction": expected, "direction": direction,
            "direction_ok": direction == expected, "note": note,
        })
    non_timing = [e["feature"] for e in evaluation["feature_effects"] if e["feature"] not in TIMING_FEATURES][:6]
    return {
        "top6": top6,
        "rule_drivers_in_top6": sum(f in rule_feature_set for f in top6),
        "rule_drivers_in_top6_excluding_timing": sum(f in rule_feature_set for f in non_timing),
        "drivers": drivers,
        "directions_ok": sum(d["direction_ok"] for d in drivers),
        "drivers_in_top10": sum(d["rank"] <= 10 for d in drivers),
    }


def _calibration_note(r: dict) -> str:
    """Explain a miscalibrated bin, including whether the gap is within sampling noise (2 standard errors)."""
    gap = abs(r["mean_predicted"] - r["observed_rate"])
    two_se = 2 * (r["observed_rate"] * (1 - r["observed_rate"]) / r["n"]) ** 0.5
    noise = "within sampling noise" if gap <= two_se else "larger than sampling noise"
    return (f"{r['bin']}: predicted {r['mean_predicted']:.2f}, observed {r['observed_rate']:.2f} "
            f"(n={r['n']}; gap {gap:.2f} vs 2 standard errors {two_se:.2f}: {noise})")


def checks(evaluation: dict) -> dict[str, tuple[bool, str]]:
    m, b = evaluation["model"], evaluation["baseline_stage_probability"]
    calib_bad = [r for r in evaluation["calibration"] if r["n"] >= 50 and abs(r["mean_predicted"] - r["observed_rate"]) > 0.10]
    d = driver_check(evaluation)
    return {
        "beats_baseline": (m["auc"] > b["auc"] and m["brier"] < b["brier"],
                           f"AUC {m['auc']:.3f} vs {b['auc']:.3f}; Brier {m['brier']:.3f} vs {b['brier']:.3f}"),
        "calibration_within_10pp": (not calib_bad, "all bins with ≥50 rows within 10 points" if not calib_bad else
                                    "; ".join(_calibration_note(r) for r in calib_bad)),
        "learns_hidden_drivers": (
            d["directions_ok"] == len(d["drivers"]) and d["drivers_in_top10"] >= 4 and d["rule_drivers_in_top6_excluding_timing"] >= 4,
            f"{d['directions_ok']}/{len(d['drivers'])} push the right way; {d['drivers_in_top10']} in the top 10; "
            f"{d['rule_drivers_in_top6_excluding_timing']} of the top 6 non-timing features "
            f"(strict original test, for information: {d['rule_drivers_in_top6']} of the overall top 6)"),
    }


def _mask_account(arn: str) -> str:
    """Evidence files are committed: keep the AWS account ID out of them."""
    return re.sub(r":\d{12}:", ":<account-id>:", arn)


def markdown(evaluation: dict, *, job: str, package_arn: str | None, cost_note: str) -> str:
    m, b = evaluation["model"], evaluation["baseline_stage_probability"]
    d = driver_check(evaluation)
    c = checks(evaluation)
    lines = [
        "# MVP-04 evidence — win-probability model evaluation", "",
        f"Training job `{job}` · {evaluation['algorithm']} · best iteration {evaluation['best_iteration']}"
        + (f" · model package `{_mask_account(package_arn)}`" if package_arn else ""), "",
        f"Split by close quarter: train {', '.join(evaluation['quarters']['train'])} ({evaluation['rows']['train']:,} rows, "
        f"{evaluation['deals']['train']:,} deals); validation {evaluation['quarters']['validation'][0]} ({evaluation['rows']['validation']:,} rows); "
        f"**held-out test {evaluation['quarters']['test'][0]}** ({evaluation['rows']['test']:,} rows, {evaluation['deals']['test']:,} deals, "
        f"win rate {100 * evaluation['test_win_rate']:.1f}%). {cost_note}", "",
        "## Model vs. Salesforce stage probability (held-out quarter)", "",
        "| Metric | Model | Stage-probability baseline | Better |", "|---|---|---|---|",
        f"| AUC (ranking; higher is better) | **{m['auc']:.3f}** | {b['auc']:.3f} | {'✓' if m['auc'] > b['auc'] else '✗'} |",
        f"| Brier score (probability error; lower is better) | **{m['brier']:.3f}** | {b['brier']:.3f} | {'✓' if m['brier'] < b['brier'] else '✗'} |",
        "", "## Calibration (held-out quarter)", "",
        "| Predicted band | Rows | Mean predicted | Observed win rate | Baseline rows |", "|---|---|---|---|---|",
    ]
    for r, br in zip(evaluation["calibration"], evaluation["baseline_calibration"]):
        mp = f"{r['mean_predicted']:.2f}" if r["mean_predicted"] is not None else "—"
        ob = f"{r['observed_rate']:.2f}" if r["observed_rate"] is not None else "—"
        lines.append(f"| {r['bin']} | {r['n']} | {mp} | {ob} | {br['n']} |")
    lines += ["", "## What drives the score (mean |SHAP| on the held-out quarter)", "",
              "| Rank | Feature | Mean \\|SHAP\\| | Direction |", "|---|---|---|---|"]
    for e in evaluation["feature_effects"][:12]:
        arrow = {1.0: "↑ raises", -1.0: "↓ lowers", None: "—"}[e["direction"]]
        lines.append(f"| {e['rank']} | `{e['feature']}` | {e['mean_abs_shap']:.3f} | {arrow} |")
    lines += ["", "## Hidden-rule drivers (does the model learn the right reasons?)", "",
              "| Hidden driver | Model feature | Rank | Expected | Learned |", "|---|---|---|---|---|"]
    for x in d["drivers"]:
        exp = "↑" if x["expected_direction"] > 0 else "↓"
        got = {1.0: "↑", -1.0: "↓", None: "—"}[x["direction"]]
        lines.append(f"| {x['driver']} | `{x['feature']}` | {x['rank']} | {exp} | {got} {'✓' if x['direction_ok'] else '✗'}"
                     + (f" ({x['note']})" if x.get('note') else "") + " |")
    lines += ["", f"{d['drivers_in_top10']} of {len(d['drivers'])} hidden-rule drivers rank in the top 10; "
              f"{d['directions_ok']} of {len(d['drivers'])} push in the expected direction. "
              f"Top 6 overall: {', '.join(d['top6'])} ({d['rule_drivers_in_top6']} are hidden-rule drivers). "
              f"Excluding stage and timing features, {d['rule_drivers_in_top6_excluding_timing']} of the next top 6 are hidden-rule drivers.", "",
              "## Acceptance checks", "", "| Check | Result | Detail |", "|---|---|---|"]
    for name, (ok, detail) in c.items():
        lines.append(f"| {name.replace('_', ' ')} | {'✓' if ok else '✗'} | {detail} |")
    return "\n".join(lines) + "\n"

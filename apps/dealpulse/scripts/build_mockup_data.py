#!/usr/bin/env python3
"""Build sample data for the clickable UI mockup (MVP-10 design reference).

    python scripts/build_mockup_data.py features SCORES_IN.json   # step 1: feature rows for open deals
    python scripts/build_mockup_data.py assemble SCORES_OUT.json  # step 2: write artifacts/dealpulse-mockups/sample-data.js

Step 1 builds each open deal's features as of the snapshot date with dealpulse.features (the same
code as training). The rows are scored with the trained model (ml/inference.py, in a Linux
container), then step 2 combines scores, plain-language drivers, deal records and notes into one
JavaScript file the mockup loads. Everything is synthetic; nothing calls AWS.
"""
from __future__ import annotations

import json
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dealpulse import features as F  # noqa: E402
from dealpulse.datagen.vocab import SNAPSHOT_DATE, STAGE_PROBABILITY  # noqa: E402

DATA = ROOT / "data" / "out"
MOCKUPS = ROOT / "artifacts" / "dealpulse-mockups"
ARCH = ROOT / "dealpulse" / "ui" / "architecture"
GAP_POINTS = 25  # flag Commit/Best Case deals the model scores this far below the stage probability

# Plain-language driver phrases. {v} is the feature's value for the deal.
PHRASES = {
    "exec_meeting_last_30d": ("Executive met in the last 30 days", "No executive meeting in the last 30 days"),
    "economic_buyer_identified": ("Economic buyer identified", "No economic buyer identified"),
    "champion_identified": ("Champion identified", "No champion identified"),
    "competitor_present": ("Competitor in the deal", "No competitor named"),
    "close_pushes": ("Close date moved {v:.0f} time(s)", "Close date has never moved"),
    "discount_pct": ("Discount at {v:.0f}%", "No discount recorded"),
    "activities_last_30d": ("{v:.0f} activities in the last 30 days", "{v:.0f} activities in the last 30 days"),
    "activity_trend_30d": ("Activity trend {v:+.0f} vs. previous 30 days", "Activity trend {v:+.0f} vs. previous 30 days"),
    "days_since_last_activity": ("Last activity {v:.0f} days ago", "Last activity {v:.0f} days ago"),
    "open_severe_cases": ("{v:.0f} open Sev-1/Sev-2 case(s) on the account", "No open severe support cases"),
    "contact_roles": ("{v:.0f} contacts engaged", "{v:.0f} contacts engaged"),
    "is_expansion": ("Expansion of an existing customer", "New business"),
    "days_to_close": ("Close date in {v:.0f} days", "Close date in {v:.0f} days"),
    "days_in_stage": ("{v:.0f} days in the current stage", "{v:.0f} days in the current stage"),
    "deal_age_days": ("Deal open {v:.0f} days", "Deal open {v:.0f} days"),
    "stage_index": ("Stage", "Stage"),
    "log_amount": ("Deal size", "Deal size"),
}
# Shown as "what you can act on"; stage, timing and category features still count in the score.
ACTIONABLE = {"exec_meeting_last_30d", "economic_buyer_identified", "champion_identified", "competitor_present",
              "close_pushes", "discount_pct", "activities_last_30d", "activity_trend_30d", "days_since_last_activity",
              "open_severe_cases", "contact_roles"}


def plain_text(lines: list[str]) -> str:
    """Markdown → readable plain text: no ** markers; table rows become "cell: cell"."""
    out = []
    for line in lines:
        line = line.strip()
        if not line or set(line) <= set("|-: "):
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells[0] in ("Discount", "Product", "Category"):  # header rows
                continue
            line = cells[0] + ": " + "; ".join(c for c in cells[1:] if c) + "."
        out.append(line.replace("**", "").lstrip("- "))
    return " ".join(out)


def load(name: str) -> list[dict]:
    return [json.loads(line) for line in (DATA / "crm-snapshot" / f"{name}.jsonl").read_text().splitlines()]


def objects() -> dict[str, list[dict]]:
    return {p.stem: load(p.stem) for p in (DATA / "crm-snapshot").glob("*.jsonl")}


def step_features(out_path: Path) -> None:
    objs = objects()
    index = F.build_index(objs)
    rows = []
    for opp in objs["Opportunity"]:
        if not opp["IsClosed"]:
            feats = F.features_as_of(index[opp["Id"]], SNAPSHOT_DATE)
            rows.append({"id": opp["Id"], "values": [feats[c] for c in F.FEATURE_COLUMNS]})
    out_path.write_text(json.dumps({"features": F.FEATURE_COLUMNS, "rows": rows}))
    print(f"✓ {len(rows)} open deals → {out_path}")


def phrase(feature: str, value: float, contribution: float) -> str:
    up, down = PHRASES.get(feature, (feature, feature))
    positive_value = value > 0 if feature not in ("days_since_last_activity",) else True
    template = up if positive_value else down
    return template.format(v=value)


def step_assemble(scores_path: Path) -> None:
    objs = objects()
    scored = json.loads(scores_path.read_text())
    users = {u["Id"]: u for u in objs["User"]}
    accounts = {a["Id"]: a for a in objs["Account"]}
    contacts = {c["Id"]: c for c in objs["Contact"]}
    traps = json.loads((DATA / "eval" / "traps.json").read_text())
    scenario_of = {v: k for k, v in traps["scenarios"].items()}
    notes_by_opp: dict[str, list[dict]] = {}
    for obj in ("Task", "Event"):
        for r in objs[obj]:
            if r.get("Description"):
                c = contacts[r["WhoId"]]
                notes_by_opp.setdefault(r["WhatId"], []).append({
                    "id": r["Id"], "date": r["ActivityDate"], "type": r["Type"], "author": r.get("Author_Role__c"),
                    "contact": f"{c['FirstName']} {c['LastName']}", "contactTitle": c["Title"], "text": r["Description"],
                })
    deals = []
    for item in scored["deals"]:
        opp = next(o for o in objs["Opportunity"] if o["Id"] == item["id"])
        values = dict(zip(scored["features"], item["values"]))
        contribs = item["contributions"]
        drivers = sorted(
            ({"feature": f, "value": values[f], "effect": c, "text": phrase(f, values[f], c), "actionable": f in ACTIONABLE}
             for f, c in contribs.items() if abs(c) >= 0.05 and f in PHRASES and f not in ("stage_index", "log_amount")),
            key=lambda d: -abs(d["effect"]))
        stage_p = STAGE_PROBABILITY[opp["StageName"]]
        model_p = round(100 * item["probability"])
        risk = next((d for d in drivers if d["actionable"] and d["effect"] < 0), None)
        owner = users[opp["OwnerId"]]
        deals.append({
            "id": opp["Id"], "name": opp["Name"], "account": accounts[opp["AccountId"]]["Name"],
            "accountId": opp["AccountId"], "industry": accounts[opp["AccountId"]]["Industry"],
            "segment": accounts[opp["AccountId"]]["Segment__c"], "owner": owner["Name"], "ownerId": owner["Id"],
            "team": owner["Team__c"], "amount": opp["Amount"], "stage": opp["StageName"], "closeDate": opp["CloseDate"],
            "forecast": opp["ForecastCategoryName"], "stageProbability": stage_p, "modelProbability": model_p,
            "flag": opp["ForecastCategoryName"] in ("Commit", "Best Case") and model_p <= stage_p - GAP_POINTS,
            "topRisk": risk["text"] if risk else None, "type": opp["Type"], "product": opp["Product_Line__c"],
            "discount": opp["Discount_Pct__c"], "competitor": opp["Competitor__c"], "nextStep": opp["NextStep"],
            "drivers": drivers[:8], "baseValue": item["base_value"],
            "notes": sorted(notes_by_opp.get(opp["Id"], []), key=lambda n: n["date"], reverse=True),
            "scenario": scenario_of.get(opp["Id"]),
        })
    deals.sort(key=lambda d: (not d["flag"], d["modelProbability"] - d["stageProbability"]))
    personas = [{"id": u["Id"], "name": u["Name"], "title": u["Title"], "team": u["Team__c"], "manager": u["IsManager__c"]}
                for u in objs["User"]]
    evaluation = json.loads(next((ROOT / "reports" / "model").glob("*.json")).read_text()) \
        if (ROOT / "reports" / "model").exists() and any((ROOT / "reports" / "model").glob("*.json")) else None
    knowledge = {}
    for kind in ("playbook", "policy"):
        for path in sorted((DATA / "knowledge" / kind).glob("*.md")):
            lines = path.read_text().splitlines()
            knowledge[f"{'PB' if kind == 'playbook' else 'PO'}-{path.stem[:2]}"] = {
                "title": lines[0].lstrip("# ").strip(), "kind": kind, "text": plain_text(lines[3:])[:900],
            }
    payload = {
        "snapshotDate": SNAPSHOT_DATE.isoformat(), "vendor": "Altura Analytics", "personas": personas, "deals": deals,
        "knowledge": knowledge, "gapPoints": GAP_POINTS,
        "model": None if not evaluation else {k: evaluation[k] for k in (
            "job", "package", "algorithm", "best_iteration", "quarters", "rows", "deals", "test_win_rate", "model",
            "baseline_stage_probability", "calibration", "baseline_calibration", "feature_effects") if k in evaluation},
        "counts": Counter(d["forecast"] for d in deals),
    }
    MOCKUPS.mkdir(parents=True, exist_ok=True)
    (MOCKUPS / "sample-data.js").write_text(
        "// Generated by scripts/build_mockup_data.py from the synthetic CRM (make data) and the trained model.\n"
        "// Fictional companies and people. Do not edit by hand.\n"
        f"window.DEALPULSE_DATA = {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))};\n")
    for name in ("architecture.js", "architecture.css"):  # the Architecture page, copied so the mockup is self-contained
        shutil.copyfile(ARCH / name, MOCKUPS / name)
    # Sample briefs: one JSON source for both the mockup (as JS) and the Streamlit app's offline mode.
    briefs = json.loads((ROOT / "data/fixtures/sample_briefs.json").read_text())
    (MOCKUPS / "sample-briefs.js").write_text(
        "// Generated from data/fixtures/sample_briefs.json by scripts/build_mockup_data.py. Do not edit by hand.\n"
        f"// {briefs['notice']}\n"
        f"window.DEALPULSE_BRIEFS = {json.dumps(briefs['briefs'], ensure_ascii=False, indent=1)};\n"
        f"window.DEALPULSE_TRACE = {json.dumps(briefs['trace'], ensure_ascii=False)};\n")
    # Offline data for the Streamlit app (DEALPULSE_DATA=offline): same payload, committed so it runs without AWS.
    (ROOT / "data/fixtures/offline.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
    flagged = sum(d["flag"] for d in deals)
    print(f"✓ {len(deals)} deals ({flagged} flagged), {len(personas)} personas, {len(knowledge)} knowledge sections → {MOCKUPS / 'sample-data.js'}")


if __name__ == "__main__":
    {"features": step_features, "assemble": step_assemble}[sys.argv[1]](Path(sys.argv[2]))

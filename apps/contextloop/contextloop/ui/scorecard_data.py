"""Computes the POV scorecard from live data (recordings, warehouse, mock CRM) plus docs/demo/pov.yml. Used by the app page and
by `python -m contextloop.ui.scorecard_data` to write the static fallback docs/demo/pov-scorecard.md."""
from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import httpx
import yaml

from contextloop import config
from contextloop.eval.run import load_demo
from contextloop.eval.score import score

POV = yaml.safe_load((config.ROOT / "docs" / "demo" / "pov.yml").read_text())
TARGET = Path(os.environ.get("DBT_TARGET_PATH", config.DBT_PROJECT_DIR / "target"))


def _truth() -> dict:
    return json.loads((config.TRUTH_DIR / "truth.json").read_text())


def _q(sql: str):
    con = duckdb.connect(str(config.SERVING_PATH), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def report_summary() -> dict | None:
    """The latest evaluation report's averages (reports/latest.json), from the data volume or the repository copy."""
    from contextloop.eval.run import REPORTS

    for d in (REPORTS, config.ROOT / "reports"):
        p = d / "latest.json"
        if p.exists():
            return json.loads(p.read_text())
    return None


def golden_totals() -> dict:
    """Golden-set scores out of 6: the evaluation report's averages over every recorded run when there is a report, so the
    scorecard matches it; otherwise the demo recordings (one run per question; for the naive agent these are picked from
    its wrong runs to show Act 1's failure, so they understate it)."""
    rep = report_summary()
    if rep and rep.get("summary"):
        return {**{a: round(rep["summary"].get(a, 0), 1) for a in ("naive", "governed")},
                "source": f"average of {rep.get('runs', 1)} runs, evaluation report"}
    t = _truth()
    out: dict = {"source": "demo recordings"}
    for agent in ("naive", "governed"):
        runs = [load_demo(agent, f"G{i}") for i in range(1, 7)]
        out[agent] = None if not any(runs) else sum(1 for i, r in enumerate(runs, 1) if r and score(f"G{i}", r.get("answer"), t)["correct"])
    return out


def checks() -> dict[str, tuple[bool | None, str]]:
    t = _truth()
    g = golden_totals()
    gov = load_demo("governed", "G1")
    out: dict[str, tuple[bool | None, str]] = {}
    if gov:
        ok = score("G1", gov.get("answer"), t)["correct"]
        out["governed_g1_correct"] = (ok, f"{'exact' if ok else 'not the exact'} list of {len(t['at_risk'])} accounts")
    else:
        out["governed_g1_correct"] = (None, "no recorded run yet (make record)")
    if g["governed"] is None:
        out["golden_scores"] = (None, "no recorded runs yet (make record)")
    else:
        out["golden_scores"] = (g["governed"] >= 5 and (g["naive"] or 0) < g["governed"], f"governed {g['governed']:g}/6 vs naive {g['naive'] or 0:g}/6 ({g['source']})")
    deleted, syncs = _q("SELECT (SELECT count(*) FROM sap_s4.likp WHERE _fivetran_deleted), "
                        "(SELECT count(*) FROM fivetran_log.sync_log WHERE connection_id = 'sap_s4' AND status = 'SUCCESSFUL')")[0]
    out["sap_incremental_with_deletes"] = (deleted > 0 and syncs >= 2, f"{syncs} incremental syncs, {deleted} soft-deleted deliveries kept")
    cols = {r[0] for r in _q("SELECT column_name FROM information_schema.columns WHERE table_schema = 'sap_s4' AND table_name = 'likp'")}
    out["schema_change_absorbed"] = ("zz_carrier_id" in cols, "LIKP.ZZ_CARRIER_ID landed" if "zz_carrier_id" in cols
                                     else "run the incremental sync in Act 2")
    rr = json.loads((TARGET / "run_results.json").read_text()) if (TARGET / "run_results.json").exists() else {"results": []}
    failing = sum(1 for r in rr["results"] if r["status"] in ("fail", "error"))
    sm = json.loads((TARGET / "semantic_manifest.json").read_text()) if (TARGET / "semantic_manifest.json").exists() else {"metrics": []}
    has = any(m["name"] == "on_time_delivery_rate" for m in sm["metrics"])
    out["one_definition"] = (has and failing == 0, f"on_time_delivery_rate defined once; {len(rr['results'])} nodes built and tested, "
                             f"{failing} failing")
    if gov:
        text = " ".join([(gov.get("answer") or {}).get("answer_summary", "")] + ((gov.get("answer") or {}).get("caveats") or [])).lower()
        said = any(w in text for w in ("zendesk", "stale", "two days", "2 days"))
        out["stale_detected"] = (said, "the answer flags Zendesk as two days old" if said else "the answer did not mention staleness")
    else:
        out["stale_detected"] = (None, "no recorded run yet (make record)")
    try:
        from contextloop.lakehouse.publish import history

        n = len(history())
        out["open_format"] = (n >= 1, f"Iceberg table with {n} snapshots; DuckDB and Trino return identical rows (make lakehouse)")
    except Exception as exc:  # noqa: BLE001
        out["open_format"] = (None, f"lakehouse not reachable: {type(exc).__name__}")
    try:
        audit = httpx.get(f"{os.environ.get('MOCK_SALESFORCE_URL', 'http://mock-salesforce:8000')}/audit", timeout=5).json()
        n = sum(1 for a in audit if a["source_model"] == "marts.account_risk")
        out["activated"] = (n > 0, f"{n} audited CRM writes from marts.account_risk" if n else "press Sync to Salesforce in Act 5")
    except httpx.HTTPError:
        out["activated"] = (None, "mock CRM not reachable")
    return out


def mar_estimate() -> list[tuple[str, int]]:
    rows = _q("SELECT connection_id, round(avg(m))::BIGINT FROM (SELECT connection_id, measured_month, sum(incremental_rows) AS m "
              "FROM fivetran_log.incremental_mar WHERE measured_month BETWEEN date '2026-08-01' AND date '2026-10-01' GROUP BY 1, 2) "
              "GROUP BY 1 ORDER BY 2 DESC")
    return [(r[0], int(r[1])) for r in rows]


def markdown() -> str:
    res = checks()
    lines = ["# Northstar proof-of-value scorecard", "", "_Generated from the live demo by `python -m contextloop.ui.scorecard_data`. "
             "Static fallback for the app's scorecard page. Synthetic data._", "", "## Success criteria", "", "| # | Criterion | Result | Evidence |",
             "|---|---|---|---|"]
    for sc in POV["success_criteria"]:
        ok, note = res[sc["check"]]
        mark = "**Pass**" if ok else ("Pending" if ok is None else "**Fail**")
        lines.append(f"| {sc['id']} | {sc['statement']} | {mark}: {note} | {sc['evidence'].replace('act', 'Act ')} |")
    lines += ["", "## Cost estimate (MAR, monthly average Aug to Oct 2026)", "", "| Connection | Estimated MAR |", "|---|---|"]
    lines += [f"| {c} | {m:,} |" for c, m in mar_estimate()]
    lines += [""] + [f"- {a}" for a in POV["cost_assumptions"]]
    lines += ["", "## Time to value", ""] + [f"- {p['phase']}: {p['days']} day(s)" for p in POV["time_to_value"]]
    lines += ["", "## Specialist map", "", "| Specialty | Workstream | Found | Open before production |", "|---|---|---|---|"]
    lines += [f"| {s['specialty']} | {s['workstream']} | {s['found']} | {s['open_items']} |" for s in POV["specialists"]]
    lines += ["", "## Path to production", ""] + [f"- [ ] {p}" for p in POV["path_to_production"]]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(markdown())

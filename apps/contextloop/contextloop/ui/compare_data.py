"""The numbers behind the "without vs with the stack" view: the same model, the same questions, scored against the hidden truth.

Pure functions over recordings, the truth and the account_risk mart rows, so the page and the tests read the same figures.
"""
from __future__ import annotations

import re

from contextloop.datagen.truth import normalize
from contextloop.eval.score import score

AGENTS = ("naive", "governed")
LABEL = {"naive": "Without the stack", "governed": "With Fivetran + dbt"}
MODEL_REF = re.compile(r"\b(stg|int|fct|dim)_\w+")  # a dbt model in a lineage path
RIGHT, WRONG, MISSED, LEFT_OUT = "Right", "Wrongly flagged", "Missed", "Correctly left out"

# What each planted trap does to an agent on raw tables, and which layer of the stack removes it.
LAYERS = [
    ("T1", "Cancelled deliveries", "Counts cancelled deliveries as real ones", "Fivetran keeps deletes as flags; dbt staging filters them",
     "Fivetran + dbt"),
    ("T2", "Wrong delivery date", "Uses SAP's planned ship date, so late deliveries look on time",
     "dbt joins the carrier's actual delivery time", "dbt"),
    ("T3", "Two currencies", "Adds EUR and USD together", "dbt converts with SAP's monthly exchange rates", "dbt"),
    ("T4", "Duplicate account", "Counts one customer twice", "dbt resolves SAP and Salesforce identities", "dbt"),
    ("T5", "Tier changed mid-quarter", "Reads every historical version of the tier",
     "Fivetran history mode; dbt uses the tier at delivery time", "Fivetran + dbt"),
    ("T6", "Stale data", "Can't tell that Zendesk is two days behind", "Fivetran sync log, read by the freshness MCP tool",
     "Fivetran + MCP"),
]


def _names(truth: dict) -> dict[str, str]:
    """Normalized name (Salesforce or SAP spelling) to the canonical account name."""
    out = {}
    for r in truth["at_risk"]:
        out[normalize(r["name"])] = r["name"]
        out[normalize(r["sap_name"])] = r["name"]
    return out


def headline_accounts(answers: dict[str, dict | None], truth: dict, risk_rows: list[dict]) -> list[dict]:
    """One row per account that is truly at risk or that either agent flagged: its true 90-day on-time rate (the trusted
    model), the rate the naive agent stated, and each agent's verdict. Worst true rate first."""
    canon = _names(truth)
    true_rate = {normalize(r["account_name"]): r["on_time_rate_90d"] for r in risk_rows}
    want = set(truth["golden"]["G1"])
    named: dict[str, dict[str, dict]] = {}
    for agent in AGENTS:
        for a in (answers.get(agent) or {}).get("at_risk_accounts") or []:
            name = canon.get(normalize(a["account_name"]), a["account_name"])
            named.setdefault(name, {})[agent] = a
    rows = []
    for name in want | set(named):
        said = named.get(name, {})
        row = {"account": name, "true_rate": true_rate.get(normalize(name)),
               "claimed_rate": (said.get("naive") or {}).get("on_time_rate"), "truly_at_risk": name in want}
        for agent in AGENTS:
            flagged = agent in said
            row[agent] = (RIGHT if name in want else WRONG) if flagged else (MISSED if name in want else LEFT_OUT)
        rows.append(row)
    return sorted(rows, key=lambda r: (r["true_rate"] is None, r["true_rate"] or 0, r["account"]))


def question_results(traces: dict[str, dict[str, dict | None]], truth: dict, golden: list[dict]) -> list[dict]:
    """Right or wrong per golden question for each agent."""
    out = []
    for q in golden:
        row = {"id": q["id"], "question": q["question"]}
        for agent in AGENTS:
            tr = traces[agent].get(q["id"])
            row[agent] = None if not tr else score(q["id"], tr.get("answer"), truth)["correct"]
        out.append(row)
    return out


def traps_hit(naive_traces: dict[str, dict | None]) -> list[str]:
    """The planted traps behind the naive agent's mistakes, across every recorded question."""
    hit = {f["trap"] for tr in naive_traces.values() if tr for f in tr.get("explanation") or []}
    return sorted(t for t in hit if t.startswith("T"))


def kpis(agent: str, traces: dict[str, dict | None], truth: dict, golden: list[dict], accounts: list[dict],
         governed_metrics: set[str], stale_truth: set[str]) -> dict:
    """The headline figures for one agent's column. Citations are judged, not just counted: a definition counts only if it is
    a governed metric, a lineage path only if it runs through tested dbt models, and a freshness check only if it flags the
    sources that really are behind (`stale_truth`, lower-case system names such as 'zendesk')."""
    results = question_results({agent: traces, **{a: {} for a in AGENTS if a != agent}}, truth, golden)
    g1 = (traces.get("G1") or {}).get("answer") or {}
    fresh = g1.get("freshness") or []
    stale = [f["source"].split(" (")[0] for f in fresh if f.get("within_window") is False]
    defs = [m["name"] for m in g1.get("metrics_used") or []]
    lineage = g1.get("lineage") or []
    flagged = truth_names(stale)
    return {
        "correct": sum(1 for r in results if r[agent]),
        "questions": len(golden),
        "accounts_right": sum(1 for a in accounts if a[agent] == RIGHT),
        "accounts_wrong": sum(1 for a in accounts if a[agent] == WRONG),
        "accounts_missed": sum(1 for a in accounts if a[agent] == MISSED),
        "accounts_expected": len(truth["golden"]["G1"]),
        "definitions": len(defs),
        "definitions_governed": sum(1 for d in defs if d in governed_metrics),
        "lineage": len(lineage),
        "lineage_governed": sum(1 for ln in lineage if MODEL_REF.search(ln)),
        "freshness_checked": sum(1 for f in fresh if f.get("within_window") is not None),
        "freshness_sources": len(fresh),
        "stale_sources": stale,
        "stale_truth": sorted(stale_truth),
        "freshness_right": flagged == stale_truth,
    }


def truth_names(sources: list[str]) -> set[str]:
    """'zendesk (simulated landing)' or 'zendesk.ticket' -> 'zendesk'."""
    return {re.split(r"[ .(_]", s.strip().lower(), maxsplit=1)[0] for s in sources}


def rate_mismatches(accounts: list[dict], tolerance: float = 0.005) -> int:
    """Accounts where the naive agent's stated on-time rate differs from the trusted model's by more than half a point."""
    return sum(1 for a in accounts if a.get("claimed_rate") is not None and a.get("true_rate") is not None
               and abs(a["claimed_rate"] - a["true_rate"]) > tolerance)


def rates_sentence(accounts: list[dict]) -> str:
    n = rate_mismatches(accounts)
    if n:
        return f"and {n} of its on-time rates are off."
    return "even though its on-time rates are right: the error is in which accounts count, not the arithmetic."

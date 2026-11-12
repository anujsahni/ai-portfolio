"""The mistake explainer for Act 1: compares the naive agent's SQL and answer with the planted traps and the hidden truth,
and writes plain-English findings, each tied to the SQL line responsible where there is one."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from contextloop.datagen.truth import normalize


@dataclass
class Finding:
    trap: str
    title: str
    detail: str
    sql_line: str | None = None
    step: int | None = None


def _sqls(trace: dict) -> list[tuple[int, str]]:
    return [(i + 1, s["input"].get("sql", "")) for i, s in enumerate(trace.get("steps", [])) if s["tool"] == "run_sql"]


def _line(sql: str, pattern: str) -> str | None:
    for ln in sql.splitlines():
        if re.search(pattern, ln, re.I):
            return ln.strip()
    return None


def _first(sqls, uses: str, lacks: str | None = None):
    for step, sql in sqls:
        if re.search(uses, sql, re.I) and (lacks is None or not re.search(lacks, sql, re.I)):
            return step, sql
    return None


def explain(trace: dict, truth: dict, traps: dict) -> list[dict]:
    sqls = _sqls(trace)
    everything = "\n".join(s for _, s in sqls)
    out: list[Finding] = []
    answer = trace.get("answer") or {}

    hit = _first(sqls, r"\b(likp|vbak|lips)\b", r"_fivetran_deleted")
    if hit:
        n = len(traps["T1"]["deliveries"])
        out.append(Finding("T1", "Counted cancelled deliveries",
                           f"The SAP tables keep {n} cancelled deliveries as soft-deleted rows (_fivetran_deleted = true). "
                           "This query never filters them out, so cancelled deliveries count as late.",
                           _line(hit[1], r"\b(likp|vbak|lips)\b"), hit[0]))
    if re.search(r"\bwadat(_ist)?\b|\blfdat\b", everything, re.I) and not re.search(r"delivered", everything, re.I):
        hit = _first(sqls, r"\bwadat(_ist)?\b|\blfdat\b")
        out.append(Finding("T2", "Used a ship date as the delivery date",
                           "WADAT and WADAT_IST are goods-issue (ship) dates and LFDAT is the planned date. The actual delivery "
                           "time is the carrier's delivered event in carrier_pg.shipment_event, which this analysis never used, "
                           f"so {traps['T2']['count']} late deliveries look on time.",
                           _line(hit[1], r"wadat|lfdat"), hit[0]))
    hit = _first(sqls, r"\bnetwr\b", r"tcurr|ukurs")
    if hit and re.search(r"sum\s*\(\s*\w*\.?netwr", hit[1], re.I):
        out.append(Finding("T3", "Added euros and dollars together",
                           f"About {traps['T3']['eur_order_share']:.0%} of documents are in EUR. Summing NETWR without converting "
                           "with TCURR mixes currencies.", _line(hit[1], r"netwr"), hit[0]))
    names = [normalize(a["account_name"]) for a in answer.get("at_risk_accounts") or []]
    halbrook = normalize(traps["T4"]["customer"]["name"])
    if any(r["kunnr"] == traps["T4"]["customer"]["kunnr"] for r in truth["at_risk"]) and halbrook not in names and \
            truth["golden"]["G1"]:
        out.append(Finding("T4", "Missed a customer split across two CRM accounts",
                           "Halbrook Fluid Systems has a look-alike duplicate account (\"… GmbH\") with no SAP number. Two of its "
                           "open shipping tickets sit on the duplicate, so the customer looked healthy."))
    hit = _first(sqls, r"salesforce\.account\b", r"_fivetran_active|_fivetran_end|_fivetran_start")
    if hit:
        demoted = [a["name"] for a in traps["T5"]["accounts"] if a["to"] == "Standard"]
        out.append(Finding("T5", "Read every history row of the account tier",
                           "salesforce.account keeps one row per version of each account (history mode). Without filtering to "
                           f"_fivetran_active, accounts that changed tier appear twice, and {', '.join(demoted)} still looks "
                           "Strategic.", _line(hit[1], r"salesforce\.account"), hit[0]))
    if traps["T6"]["enabled"] and not re.search(r"_fivetran_synced|fivetran_log", everything, re.I):
        stated = " ".join([answer.get("answer_summary", "")] + (answer.get("caveats") or [])).lower()
        if not re.search(r"stale|two days|2 days|out of date|not current|behind", stated):
            out.append(Finding("T6", "Did not notice stale support data",
                               "Zendesk's last successful sync was two days ago; the answer treats ticket counts as current."))

    if trace.get("question_id") == "G1":
        want = {normalize(r["name"]) for r in truth["at_risk"]} | {normalize(r["sap_name"]) for r in truth["at_risk"]}
        got = set(names)
        extra = [a["account_name"] for a in answer.get("at_risk_accounts") or [] if normalize(a["account_name"]) not in want]
        missed = [r["name"] for r in truth["at_risk"] if normalize(r["name"]) not in got and normalize(r["sap_name"]) not in got]
        if extra or missed:
            out.append(Finding("—", "The list itself",
                               f"Named {len(extra)} account(s) that are not at risk"
                               f"{(': ' + ', '.join(extra[:6])) if extra else ''}; missed {len(missed)} that are"
                               f"{(': ' + ', '.join(missed[:9])) if missed else ''}."))
    return [asdict(f) for f in out]

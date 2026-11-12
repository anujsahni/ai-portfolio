"""The hidden truth: computes every business answer from the source-shaped tables, in plain Python.

This code shares nothing with the dbt models (no SQL), so it can check them. It implements the definitions in
docs/demo/narrative.md. `compute(..., ignore={"T1", ...})` deliberately breaks one rule at a time; tests use it to prove that
each trap changes at least one golden answer.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import date, datetime, timedelta

from contextloop.config import AS_OF
from contextloop.datagen.sources import SAP_KEYS
from contextloop.datagen.world import SHIPPING_TAGS, SHIPPING_WORDS, WINDOW_START

OPEN_STATUSES = {"new", "open", "pending", "hold"}
LEGAL = {"gmbh", "ag", "inc", "llc", "ltd", "corp", "bv", "sa", "srl", "ab"}
RENEWAL_DAYS = 120
RISK_THRESHOLD = 0.85
TRAPS = ("T1", "T2", "T3", "T4", "T5", "T6")


def d8(s: str) -> date | None:
    return None if not s or s == "00000000" else date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def dts(s: str) -> datetime | None:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ") if s else None


def cents(x: float) -> float:
    """Rounds to cents, halves away from zero (how amounts are booked; Python's round() would round halves to even)."""
    r = abs(x) * 100.0
    return math.copysign(math.floor(r + 0.5), x) / 100.0


def normalize(name: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    return " ".join(w for w in s.split() if w not in LEGAL)


def apply_feed(table: str, rows: list[dict]) -> dict[tuple, dict]:
    """Replays a change feed: the latest image per key, with `_deleted` set when the last change was a delete."""
    state: dict[tuple, dict] = {}
    for r in rows:
        key = tuple(r[k] for k in SAP_KEYS[table])
        state[key] = r | {"_deleted": r["ODQ_CHANGEMODE"] == "D"}
    return state


def is_shipping(subject: str, tags: set[str]) -> bool:
    return bool(tags & SHIPPING_TAGS) or any(w in subject.lower() for w in SHIPPING_WORDS)


def next_step(renewal: date | None, tickets: int) -> str:
    if renewal:
        return "Executive call before the renewal, with a delivery recovery plan"
    if tickets >= 3:
        return "Escalate the open tickets with logistics and give the customer a named contact"
    return "Share the late-delivery list with the customer and agree new delivery dates"


def compute(sap: dict, saas: dict, carrier: dict, stale_zendesk: bool, ignore: frozenset[str] = frozenset()) -> dict:
    kna1 = {k[1]: r for k, r in apply_feed("KNA1", sap["KNA1"][1]).items()}
    vbak = {k[1]: r for k, r in apply_feed("VBAK", sap["VBAK"][1]).items()}
    likp = {k[1]: r for k, r in apply_feed("LIKP", sap["LIKP"][1]).items()}
    lips = apply_feed("LIPS", sap["LIPS"][1])
    vbrk = {k[1]: r for k, r in apply_feed("VBRK", sap["VBRK"][1]).items()}
    tcurr = apply_feed("TCURR", sap["TCURR"][1])
    rate = {}
    for r in tcurr.values():
        first = d8(str(99999999 - int(r["GDATU"])))
        rate[first.strftime("%Y-%m")] = float(r["UKURS"])

    # --- identity resolution (T4) and tier history (T5)
    versions = saas["salesforce/account_history"][1]
    current = {v["id"]: v for v in versions if v["valid_to"].startswith("9999")}
    by_norm = {normalize(v["name"]): v["sap_customer_number_c"] for v in current.values() if v["sap_customer_number_c"]}
    sf_to_kunnr: dict[str, str] = {}
    for v in current.values():
        if v["sap_customer_number_c"]:
            sf_to_kunnr[v["id"]] = v["sap_customer_number_c"]
        elif "T4" not in ignore and normalize(v["name"]) in by_norm:
            sf_to_kunnr[v["id"]] = by_norm[normalize(v["name"])]
    eod = lambda d: datetime.combine(d, datetime.max.time()).replace(microsecond=0)  # noqa: E731

    def tier_on(sf_id: str, d: date) -> str | None:
        t = eod(d)
        for v in versions:
            if v["id"] == sf_id and dts(v["valid_from"]) <= t <= dts(v["valid_to"]):
                return v["tier_c"]
        return None

    mapped_sf = {v["sap_customer_number_c"]: v["id"] for v in current.values() if v["sap_customer_number_c"]}
    if "T5" in ignore:  # any history row says Strategic
        strategic = {k for k, sf in mapped_sf.items() if any(v["id"] == sf and v["tier_c"] == "Strategic" for v in versions)}
    else:
        strategic = {k for k, sf in mapped_sf.items() if tier_on(sf, AS_OF) == "Strategic"}
    if "T4" in ignore:  # count Salesforce accounts, not customers: the look-alike duplicate counts too
        strategic_count = len(strategic) + sum(1 for v in current.values() if not v["sap_customer_number_c"] and v["tier_c"] == "Strategic")
    else:
        strategic_count = len(strategic)

    # --- deliveries and on time (T1, T2)
    delivered: dict[str, datetime] = {}
    ship_of = {s["shipment_id"]: s["delivery_number"] for s in carrier["shipment"][1]}
    for e in carrier["shipment_event"][1]:
        if e["event_type"] == "delivered":
            delivered[ship_of[e["shipment_id"]]] = dts(e["event_at"])
    order_of: dict[str, str] = {}
    for (_, vbeln, _), r in sorted(lips.items()):
        if "T1" in ignore or not r["_deleted"]:
            order_of.setdefault(vbeln, r["VGBEL"])
    per = defaultdict(lambda: {"n": 0, "on_time": 0, "late": 0})
    by_tier = defaultdict(lambda: {"n": 0, "on_time": 0})
    for vbeln, d in likp.items():
        if d["_deleted"] and "T1" not in ignore:
            continue
        order = vbak.get(order_of.get(vbeln, ""))
        if not order:
            continue
        due = d8(order["VDATU"])
        if not (WINDOW_START <= due <= AS_OF):
            continue
        if "T2" in ignore:
            shipped = d8(d["WADAT_IST"])
            ok = shipped is not None and shipped <= due
        else:
            at = delivered.get(vbeln)
            ok = at is not None and at.date() <= due
        k = d["KUNNR"]
        per[k]["n"] += 1
        per[k]["on_time"] += ok
        per[k]["late"] += not ok
        if k in mapped_sf:
            t = tier_on(mapped_sf[k], due)
            by_tier[t]["n"] += 1
            by_tier[t]["on_time"] += ok

    # --- tickets
    org_sf = {o["id"]: o["external_id"] for o in saas["zendesk/organization"][1]}
    tags = defaultdict(set)
    for t in saas["zendesk/ticket_tag"][1]:
        tags[t["ticket_id"]].add(t["tag"])
    open_ship = defaultdict(int)
    for t in saas["zendesk/ticket"][1]:
        if t["status"] in OPEN_STATUSES and is_shipping(t["subject"], tags[t["id"]]):
            k = sf_to_kunnr.get(org_sf.get(t["organization_id"], ""))
            if k:
                open_ship[k] += 1

    # --- renewals
    renewal: dict[str, date] = {}
    horizon = AS_OF + timedelta(days=RENEWAL_DAYS)
    for o in saas["salesforce/opportunity"][1]:
        if o["type"] != "Renewal" or o["is_closed"] == "true":
            continue
        close = date.fromisoformat(o["close_date"])
        k = sf_to_kunnr.get(o["account_id"])
        if k and AS_OF <= close <= horizon:
            renewal[k] = min(renewal.get(k, close), close)

    # --- at risk
    rows = []
    for k in sorted(strategic):
        p = per.get(k, {"n": 0, "on_time": 0, "late": 0})
        r_ = p["on_time"] / p["n"] if p["n"] else None
        if r_ is not None and r_ < RISK_THRESHOLD and (open_ship[k] >= 2 or k in renewal):
            rows.append({"kunnr": k, "name": current[mapped_sf[k]]["name"], "sap_name": kna1[k]["NAME1"], "sf_account_id": mapped_sf[k],
                         "on_time_rate": round(r_, 4),
                         "deliveries_90d": p["n"], "late_deliveries_90d": p["late"], "open_shipping_tickets": open_ship[k],
                         "renewal_close_date": renewal[k].isoformat() if k in renewal else None,
                         "next_step": next_step(renewal.get(k), open_ship[k])})
    rows.sort(key=lambda x: x["on_time_rate"])

    # --- revenue (T3)
    rev = defaultdict(float)
    for r in vbrk.values():
        if r["_deleted"]:
            continue
        fk = d8(r["FKDAT"])
        amt = float(r["NETWR"]) * (1 if r["WAERK"] == "USD" or "T3" in ignore else rate[fk.strftime("%Y-%m")])
        amt = cents(-amt if r["FKART"] == "G2" else amt)  # each document in cents, as booked
        region = "North America" if kna1[r["KUNAG"]]["LAND1"] in ("US", "CA", "MX") else "EMEA"
        rev[(region, f"{fk.year}-Q{(fk.month - 1) // 3 + 1}")] += amt

    s_n = sum(per[k]["n"] for k in strategic)
    s_ok = sum(per[k]["on_time"] for k in strategic)
    stale = stale_zendesk and "T6" not in ignore
    golden = {
        "G1": [r["name"] for r in rows],
        "G2": round(100 * s_ok / s_n, 1) if s_n else None,
        "G3": round(rev[("EMEA", "2026-Q3")]),
        "G4": strategic_count,
        "G5": {"current": not stale, "zendesk_lag_days": 2 if stale else 0},
        "G6": sum(open_ship[k] for k in strategic),
    }
    return {
        "as_of": AS_OF.isoformat(), "window": [WINDOW_START.isoformat(), AS_OF.isoformat()],
        "at_risk": rows, "golden": golden,
        "strategic_accounts": sorted(current[mapped_sf[k]]["name"] for k in strategic),
        "on_time_by_customer": {k: {"name": kna1[k]["NAME1"], **v, "rate": round(v["on_time"] / v["n"], 4)}
                                for k, v in sorted(per.items()) if v["n"]},
        "on_time_by_tier_at_delivery": {t: round(v["on_time"] / v["n"], 4) for t, v in sorted(by_tier.items(), key=lambda x: str(x[0])) if v["n"]},
        "net_revenue_usd": {f"{reg}|{q}": round(v, 2) for (reg, q), v in sorted(rev.items())},
        "open_shipping_tickets": dict(sorted(open_ship.items())),
        "renewals_due_120d": {k: v.isoformat() for k, v in sorted(renewal.items())},
    }

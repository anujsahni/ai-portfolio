"""Reverse ETL (Act 5): push the governed at-risk list into the CRM, the way Fivetran Activations would.

  * The source of truth is the dbt mart `marts.account_risk` (never an agent's free text).
  * The sync compares the mart with the CRM's current values and applies only the differences; it reports what it would
    change (dry run) and what it changed. Running it twice changes nothing the second time.
  * The recommended next step is taken from the governed agent's structured answer when a recording or live run has one,
    marked "AI-drafted"; otherwise from the playbook rule in the mart, marked "Playbook rule (dbt)".
  * Slack: posts one summary message when SLACK_WEBHOOK_URL is set; otherwise only a preview is built (no network call).
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from contextloop.datagen.truth import normalize
from contextloop.warehouse import serving

CRM_URL = os.environ.get("MOCK_SALESFORCE_URL", "http://mock-salesforce:8000")
SOURCE_MODEL = "marts.account_risk"
COMPARED = ["Delivery_Risk__c", "Delivery_Risk_Drivers__c", "Next_Step__c", "Next_Step_Source__c"]


@dataclass
class Change:
    account_id: str
    account_name: str
    kind: str  # update | unchanged | clear
    before: dict
    after: dict

    @property
    def changed_fields(self) -> list[str]:
        return [f for f in COMPARED if self.before.get(f) != self.after.get(f)]


@dataclass
class Plan:
    changes: list[Change] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        c = {"update": 0, "clear": 0, "unchanged": 0}
        for ch in self.changes:
            c[ch.kind] += 1
        return c


def governed_rows() -> list[dict]:
    with serving() as con:
        cur = con.execute("SELECT customer_id, account_name, salesforce_account_id, on_time_rate_90d, late_deliveries_90d, "
                          "deliveries_90d, open_shipping_tickets, renewal_close_date, next_step FROM marts.account_risk "
                          "WHERE is_at_risk ORDER BY on_time_rate_90d")
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def drivers(r: dict) -> str:
    parts = [f"On-time {r['on_time_rate_90d']:.0%} over 90 days ({r['late_deliveries_90d']} of {r['deliveries_90d']} late)"]
    if r["open_shipping_tickets"]:
        parts.append(f"{r['open_shipping_tickets']} open shipping tickets")
    if r["renewal_close_date"]:
        parts.append(f"renewal closes {r['renewal_close_date']:%d %b %Y}")
    return "; ".join(parts)


def ai_next_steps(agent_answer: dict | None) -> dict[str, str]:
    if not agent_answer:
        return {}
    return {normalize(a["account_name"]): a["next_step"] for a in agent_answer.get("at_risk_accounts") or [] if a.get("next_step")}


def plan(client: httpx.Client, agent_answer: dict | None = None) -> Plan:
    rows = governed_rows()
    ai = ai_next_steps(agent_answer)
    crm = {a["Id"]: a for a in client.get(f"{CRM_URL}/accounts").raise_for_status().json()}
    p, wanted = Plan(), set()
    for r in rows:
        acct = crm.get(r["salesforce_account_id"])
        if not acct:
            continue
        wanted.add(acct["Id"])
        step = ai.get(normalize(r["account_name"]))
        after = {"Delivery_Risk__c": "At risk: late shipments", "Delivery_Risk_Drivers__c": drivers(r),
                 "Next_Step__c": step or r["next_step"], "Next_Step_Source__c": "AI-drafted" if step else "Playbook rule (dbt)"}
        before = {f: acct.get(f) for f in COMPARED}
        p.changes.append(Change(acct["Id"], acct["Name"], "unchanged" if before == after else "update", before, after))
    for acct in crm.values():  # previously flagged accounts that are no longer at risk get cleared
        if acct["Id"] not in wanted and acct.get("Delivery_Risk__c"):
            p.changes.append(Change(acct["Id"], acct["Name"], "clear", {f: acct.get(f) for f in COMPARED}, dict.fromkeys(COMPARED)))
    return p


def apply(client: httpx.Client, p: Plan) -> dict:
    sync_id = f"sync-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    written = 0
    for ch in p.changes:
        if ch.kind == "unchanged":
            continue
        body = ch.after | {"Risk_Updated_At__c": now if ch.kind == "update" else None}
        client.patch(f"{CRM_URL}/accounts/{ch.account_id}", json=body,
                     headers={"X-Source-Model": SOURCE_MODEL, "X-Sync-Id": sync_id}).raise_for_status()
        written += 1
    return {"sync_id": sync_id, "written": written, **p.counts}


def slack_message(rows: list[dict] | None = None) -> dict:
    rows = rows if rows is not None else governed_rows()
    lines = [f"*{len(rows)} strategic accounts at risk from late shipments* (Northstar, synthetic demo data)"]
    for r in rows:
        lines.append(f"• *{r['account_name']}*: {drivers(r)}. Next step: {r['next_step']} "
                     f"(<{CRM_URL}/accounts/{r['salesforce_account_id']}|mock CRM record>)")
    lines.append("Source: dbt model marts.account_risk · synced by ContextLoop reverse ETL")
    return {"text": "\n".join(lines)}


def post_slack(message: dict) -> dict:
    url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not url.startswith("https://"):
        return {"posted": False, "reason": "SLACK_WEBHOOK_URL is not set; showing a preview only"}
    r = httpx.post(url, json=message, timeout=10)
    return {"posted": r.status_code == 200, "status": r.status_code}

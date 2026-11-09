"""Deal features as of a date: the single source of truth for training (MVP-04) and the app (MVP-05).

Every feature is rebuilt from records dated on or before `as_of` (OpportunityHistory,
OpportunityFieldHistory, contact roles, activities, cases). The opportunity's *current* stage,
close date, probability and outcome are never read, so a training row can't "see" how the deal
ended. Deliberately excluded: owner/rep, rep win rate, Probability, ForecastCategoryName, free text.
"""
from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date, timedelta

from dealpulse.datagen.vocab import EXECUTIVE_LEVELS, INDUSTRIES, LEAD_SOURCES, OPEN_STAGES, PRODUCTS, SEGMENTS

SEVERE = {"Critical", "High"}

FEATURE_COLUMNS = (
    ["log_amount", "is_expansion"]
    + [f"product_{p.split()[0].lower()}" for p in PRODUCTS]
    + [f"segment_{s.split('-')[0].lower()}" for s in SEGMENTS]
    + [f"industry_{i.split()[0].lower()}" for i in INDUSTRIES]
    + [f"lead_{s.split()[0].lower()}" for s in LEAD_SOURCES]
    + [
        "stage_index", "days_in_stage", "deal_age_days", "days_to_close", "close_pushes",
        "discount_pct", "competitor_present",
        "contact_roles", "economic_buyer_identified", "champion_identified", "exec_meeting_last_30d",
        "days_since_last_activity", "activities_last_30d", "activity_trend_30d",
        "open_severe_cases",
    ]
)


def _d(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


@dataclass
class DealRecords:
    """Everything known about one opportunity, sorted by date for fast point-in-time lookups."""
    opportunity: dict
    account: dict
    history: list[dict] = field(default_factory=list)           # OpportunityHistory, by CreatedDate
    field_history: list[dict] = field(default_factory=list)     # OpportunityFieldHistory
    contact_roles: list[dict] = field(default_factory=list)
    activities: list[tuple[date, bool]] = field(default_factory=list)  # (date, is executive meeting)
    cases: list[dict] = field(default_factory=list)              # the account's cases

    def __post_init__(self) -> None:
        self.history.sort(key=lambda r: r["CreatedDate"])
        self.activities.sort()
        self._history_dates = [_d(r["CreatedDate"]) for r in self.history]
        self._activity_dates = [a[0] for a in self.activities]

    @property
    def created(self) -> date:
        return _d(self.opportunity["CreatedDate"])

    def history_as_of(self, as_of: date) -> list[dict]:
        return self.history[: bisect_right(self._history_dates, as_of)]


def build_index(objects: dict[str, list[dict]]) -> dict[str, DealRecords]:
    """Group the CRM snapshot by opportunity ID."""
    accounts = {a["Id"]: a for a in objects["Account"]}
    seniority = {c["Id"]: c["Seniority__c"] for c in objects["Contact"]}
    cases_by_account: dict[str, list[dict]] = {}
    for case in objects.get("Case", []):
        cases_by_account.setdefault(case["AccountId"], []).append(case)
    deals = {
        o["Id"]: DealRecords(o, accounts[o["AccountId"]], cases=cases_by_account.get(o["AccountId"], []))
        for o in objects["Opportunity"]
    }
    for row in objects.get("OpportunityHistory", []):
        deals[row["OpportunityId"]].history.append(row)
    for row in objects.get("OpportunityFieldHistory", []):
        deals[row["OpportunityId"]].field_history.append(row)
    for row in objects.get("OpportunityContactRole", []):
        deals[row["OpportunityId"]].contact_roles.append(row)
    for obj in ("Task", "Event"):
        for row in objects.get(obj, []):
            is_exec = obj == "Event" and seniority.get(row["WhoId"]) in EXECUTIVE_LEVELS
            deals[row["WhatId"]].activities.append((_d(row["ActivityDate"]), is_exec))
    for deal in deals.values():
        deal.__post_init__()
    return deals


def features_as_of(deal: DealRecords, as_of: date) -> dict[str, float]:
    """Feature vector for one deal as it looked on `as_of`. Raises if the deal didn't exist yet."""
    history = deal.history_as_of(as_of)
    if not history:
        raise ValueError(f"{deal.opportunity['Id']} has no history on or before {as_of}")
    opp, account = deal.opportunity, deal.account
    current = history[-1]
    stage = current["StageName"]
    if stage not in OPEN_STAGES:
        raise ValueError(f"{opp['Id']} was already closed on {as_of}")

    first = len(history) - 1  # first row of the current run of this stage
    while first > 0 and history[first - 1]["StageName"] == stage:
        first -= 1
    stage_since = _d(history[first]["CreatedDate"])
    pushes = sum(1 for prev, row in zip(history, history[1:]) if row["CloseDate"] > prev["CloseDate"])

    fields = {}
    for row in deal.field_history:
        if _d(row["CreatedDate"]) <= as_of:
            fields[row["Field"]] = row["NewValue"]

    roles = [r for r in deal.contact_roles if _d(r["CreatedDate"]) <= as_of]
    upto = bisect_right(deal._activity_dates, as_of)
    past = deal.activities[:upto]
    last_30 = [a for a in past if a[0] > as_of - timedelta(days=30)]
    prev_30 = [a for a in past if as_of - timedelta(days=60) < a[0] <= as_of - timedelta(days=30)]
    open_severe = sum(
        1 for c in deal.cases
        if c["Priority"] in SEVERE and _d(c["CreatedDate"]) <= as_of
        and (c["ClosedDate"] is None or _d(c["ClosedDate"]) > as_of)
    )

    row = {
        "log_amount": math.log10(max(1, opp["Amount"])),
        "is_expansion": float(opp["Type"] == "Expansion"),
        "stage_index": float(OPEN_STAGES.index(stage)),
        "days_in_stage": float((as_of - stage_since).days),
        "deal_age_days": float((as_of - deal.created).days),
        "days_to_close": float((_d(current["CloseDate"]) - as_of).days),
        "close_pushes": float(pushes),
        "discount_pct": float(fields.get("Discount_Pct__c") or 0),
        "competitor_present": float(bool(fields.get("Competitor__c"))),
        "contact_roles": float(len(roles)),
        "economic_buyer_identified": float(any(r["Role"] == "Economic Buyer" for r in roles)),
        "champion_identified": float(any(r["Role"] == "Champion" for r in roles)),
        "exec_meeting_last_30d": float(any(is_exec for _, is_exec in last_30)),
        "days_since_last_activity": float((as_of - past[-1][0]).days if past else (as_of - deal.created).days),
        "activities_last_30d": float(len(last_30)),
        "activity_trend_30d": float(len(last_30) - len(prev_30)),
        "open_severe_cases": float(open_severe),
    }
    for p in PRODUCTS:
        row[f"product_{p.split()[0].lower()}"] = float(opp["Product_Line__c"] == p)
    for s in SEGMENTS:
        row[f"segment_{s.split('-')[0].lower()}"] = float(account["Segment__c"] == s)
    for i in INDUSTRIES:
        row[f"industry_{i.split()[0].lower()}"] = float(account["Industry"] == i)
    for s in LEAD_SOURCES:
        row[f"lead_{s.split()[0].lower()}"] = float(opp["LeadSource"] == s)
    return {name: row[name] for name in FEATURE_COLUMNS}


def stage_probability_as_of(deal: DealRecords, as_of: date) -> float:
    """Salesforce's default probability for the stage on that date: the baseline the model must beat."""
    from dealpulse.datagen.vocab import STAGE_PROBABILITY
    return STAGE_PROBABILITY[deal.history_as_of(as_of)[-1]["StageName"]] / 100


def snapshot_dates(deal: DealRecords, every_days: int = 18) -> list[date]:
    """Dates to snapshot a closed deal: every `every_days` from day 7 until the day before it closed."""
    closed_on = _d(deal.history[-1]["CreatedDate"])
    dates, when = [], deal.created + timedelta(days=7)
    while when < closed_on:
        dates.append(when)
        when += timedelta(days=every_days)
    return dates

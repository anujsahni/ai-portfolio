"""Draft itinerary schema and the deterministic reviewer (MVP-06).

The reviewer is plain code, not a model: it's predictable, free, and unit-tested.
It checks a model draft against what the server knows (trip dates, budget, evidence
labels, simulated conditions) and returns issues for at most one revision.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

CATEGORY_IDS = ["stays", "food-coffee", "activities", "local-transit"]
BUDGET_TOLERANCE = 1.0

# Phrases that claim an action the app can't take. Advice such as "book directly" is fine.
BOOKING_CLAIM = re.compile(
    r"\b(i|we)\s*('ve|\s+have|\s+just|\s+already)?\s+(booked|reserved|purchased|bought|secured|confirmed)\b"
    r"|\b(is|are|has been|have been)\s+(all\s+|fully\s+|now\s+)?(booked|reserved|confirmed)\s+for\s+you\b"
    r"|\b(your|the)\s+(booking|reservations?|tickets?|table|room|trip|itinerary|plan)\s+(is|are|has been|have been)\s+"
    r"(all\s+|fully\s+|now\s+)?(confirmed|booked|reserved|purchased|secured)\b"
    r"|\b(booked|reserved|purchased) for you\b|\bfully confirmed\b",
    re.I,
)

ALCOHOL = re.compile(r"\b(wine|wines|winery|wineries|tasting rooms?|wine tastings?|brewery|breweries|beer|cocktails?|bar crawl)\b", re.I)
NO_DRINK_DRIVING = re.compile(
    r"designated driver|(don'?t|do not|never|avoid|not)\s+drink(ing)?\s+and\s+driv|drinking and driving|no drink[- ]driving", re.I
)
DRINK_DRIVING_CAVEAT = "If you drink alcohol, use a designated driver, a tour, or a rideshare. Never drink and drive."

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "days": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "YYYY-MM-DD, one entry per trip date in order"},
                    "title": {"type": "string"},
                    "activities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "time": {"type": "string"},
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "area": {"type": "string"},
                                "categoryId": {"type": "string", "enum": CATEGORY_IDS},
                                "estimatedCostUsd": {"type": "number", "description": "for the whole party"},
                                "citations": {"type": "array", "items": {"type": "string"}, "description": "evidence labels like S1"},
                            },
                            "required": ["time", "title", "description", "categoryId", "estimatedCostUsd", "citations"],
                        },
                    },
                },
                "required": ["date", "title", "activities"],
            },
        },
        "budget": {
            "type": "object",
            "properties": {
                "lineItems": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "categoryId": {"type": "string", "enum": CATEGORY_IDS},
                            "amountUsd": {"type": "number"},
                            "note": {"type": "string"},
                            "citations": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["categoryId", "amountUsd", "note"],
                    },
                },
                "totalUsd": {"type": "number"},
                "overBudget": {"type": "boolean"},
                "substitutions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["lineItems", "totalUsd", "overBudget"],
        },
        "whyThisFits": {"type": "string"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
        "unansweredRequests": {"type": "array", "items": {"type": "string"}},
        "clarifyingQuestion": {"type": "string"},
    },
    "required": ["headline", "days", "budget", "whyThisFits", "assumptions", "uncertainties"],
}


@dataclass
class Issue:
    code: str
    message: str


@dataclass
class ReviewResult:
    passed: bool
    issues: list[Issue] = field(default_factory=list)
    checks: dict = field(default_factory=dict)
    computed_total: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    def feedback(self) -> str:
        return "\n".join(f"- {i.message}" for i in self.issues)


def trip_dates(start: date, end: date) -> list[str]:
    return [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]


def all_text(draft: dict) -> str:
    parts = [draft.get("headline", ""), draft.get("whyThisFits", "")]
    for d in draft.get("days", []):
        parts.append(d.get("title", ""))
        for a in d.get("activities", []):
            parts += [a.get("title", ""), a.get("description", "")]
    parts += draft.get("assumptions", []) + draft.get("uncertainties", [])
    return "\n".join(str(p) for p in parts)


def review_draft(
    draft: dict,
    *,
    dates: list[str],
    budget_limit: float,
    labels: dict,          # label -> RetrievedChunk-like (needs .content_type)
    indoor_dates: set[str] = frozenset(),
) -> ReviewResult:
    issues: list[Issue] = []

    def add(code: str, msg: str) -> None:
        issues.append(Issue(code, msg))

    # Dates
    got = [d.get("date") for d in draft.get("days", [])]
    dates_ok = got == dates
    if not dates_ok:
        add("dates", f"Days must be exactly {dates} in order (got {got}).")

    # Citations and activities
    invalid: set[str] = set()
    uncited: list[str] = []
    weather_conflicts: list[str] = []
    itemized: dict[str, float] = {}
    for d in draft.get("days", []):
        if not d.get("activities"):
            add("empty_day", f"{d.get('date')} has no activities.")
        for a in d.get("activities", []):
            cites = [str(c).strip("[] ") for c in a.get("citations", [])]
            valid = [c for c in cites if c in labels]
            invalid |= {c for c in cites if c not in labels}
            if not valid:
                uncited.append(a.get("title", "?"))
            cost = a.get("estimatedCostUsd", 0)
            if not isinstance(cost, (int, float)) or cost < 0:
                add("cost", f"'{a.get('title')}' needs a non-negative estimated cost.")
                cost = 0
            itemized[a.get("categoryId", "?")] = itemized.get(a.get("categoryId", "?"), 0) + float(cost)
            if d.get("date") in indoor_dates and valid and all(labels[c].content_type == "outdoor-guide" for c in valid):
                weather_conflicts.append(f"{a.get('title')} on {d.get('date')}")
    if invalid:
        add("invalid_citation", f"Use only the evidence labels provided; these don't exist: {', '.join(sorted(invalid))}.")
    if uncited:
        add("unsupported", f"Every activity needs at least one valid evidence label; missing for: {', '.join(uncited)}.")
    if weather_conflicts:
        add("weather", f"Simulated conditions recommend indoor plans, but these are outdoor-only: {', '.join(weather_conflicts)}. Swap or move them.")

    # Budget arithmetic
    b = draft.get("budget", {})
    lines = {}
    for li in b.get("lineItems", []):
        lines[li.get("categoryId")] = lines.get(li.get("categoryId"), 0) + float(li.get("amountUsd", 0) or 0)
        invalid_li = [str(c).strip("[] ") for c in li.get("citations", []) if str(c).strip("[] ") not in labels]
        if invalid_li:
            add("invalid_citation", f"Budget line '{li.get('categoryId')}' cites unknown labels: {', '.join(invalid_li)}.")
    computed = round(sum(lines.values()), 2)
    stated = float(b.get("totalUsd", 0) or 0)
    arithmetic_ok = abs(computed - stated) <= BUDGET_TOLERANCE
    if not arithmetic_ok:
        add("budget_arithmetic", f"totalUsd is {stated:g} but the line items add up to {computed:g}.")
    missing_cats = [c for c in CATEGORY_IDS if c not in lines]
    if missing_cats:
        add("budget_categories", f"Include a budget line for: {', '.join(missing_cats)}.")
    for cat, amount in itemized.items():
        if amount > lines.get(cat, 0) + BUDGET_TOLERANCE:
            add("budget_itemization", f"Activities in '{cat}' add up to {amount:g}, more than its budget line ({lines.get(cat, 0):g}).")
    over = computed > budget_limit + BUDGET_TOLERANCE
    if over and not b.get("overBudget"):
        add("budget_status", f"The plan totals {computed:g}, over the {budget_limit:g} budget, but isn't flagged as over budget.")
    if over and not b.get("substitutions"):
        add("budget_substitutions", "The plan is over budget; suggest lower-cost substitutions.")

    # Actions the app can't take
    booking = bool(BOOKING_CLAIM.search(all_text(draft)))
    if booking:
        add("booking_claim", "Don't say anything was booked, reserved, or purchased; the app can't do that.")

    # Safety: any plan involving alcohol must say not to drink and drive.
    text = all_text(draft)
    drink_driving_ok = not ALCOHOL.search(text) or bool(NO_DRINK_DRIVING.search(text))
    if not drink_driving_ok:
        add("drink_driving", "The plan includes alcohol (e.g. wine tasting). Add explicit guidance: use a designated driver, "
            "tour, or rideshare, and never drink and drive.")

    checks = {
        "datesMatch": dates_ok,
        "drinkDrivingGuidance": drink_driving_ok,
        "citationsValid": not invalid and not uncited,
        "budgetArithmetic": arithmetic_ok,
        "budgetFlaggedCorrectly": not (over and not b.get("overBudget")),
        "weatherRespected": not weather_conflicts,
        "noBookingClaims": not booking,
    }
    return ReviewResult(passed=not issues, issues=issues, checks=checks, computed_total=computed)

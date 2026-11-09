"""What the pages show, without Streamlit: data access, access rules, filters, KPIs and answers.

The data comes from a provider. Today there is one, OfflineData (DEALPULSE_DATA=offline, the default):
saved synthetic deals with real scores from the trained model, and hand-written sample briefs.
Live providers replace it page by page: scoring (MVP-05), retrieval (MVP-07), briefs (MVP-08).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "data" / "fixtures"
FEATURED_DEAL = "006DP0000000007"  # Northbeam Logistics Group: Commit, model 17%
SAMPLE_BRIEF_DEALS = ["006DP0000000007", "006DP0000000001", "006DP0000000003"]
TIMING_FEATURES = {"stage_index", "days_to_close", "days_in_stage", "deal_age_days"}


@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    title: str
    team: str
    manager: bool

    @property
    def label(self) -> str:
        return f"{self.name} · {self.team}"


@dataclass
class OfflineData:
    """Saved data for running the UI without AWS."""
    snapshot_date: str
    personas: list[Persona]
    deals: list[dict]
    knowledge: dict[str, dict]
    model: dict | None
    gap_points: int
    briefs: dict[str, dict] = field(default_factory=dict)
    trace: list[list[str]] = field(default_factory=list)
    mode: str = "offline"

    def deal(self, deal_id: str) -> dict | None:
        return next((d for d in self.deals if d["id"] == deal_id), None)

    def persona(self, persona_id: str | None) -> Persona:
        return next((p for p in self.personas if p.id == persona_id), self.default_persona())

    def default_persona(self) -> Persona:
        return next((p for p in self.personas if p.name == "Priya Raman"), self.personas[0])

    def note(self, note_id: str) -> dict | None:
        for d in self.deals:
            for n in d["notes"]:
                if n["id"] == note_id:
                    return {**n, "dealId": d["id"]}
        return None


@lru_cache(maxsize=1)
def load() -> OfflineData:
    mode = os.environ.get("DEALPULSE_DATA", "offline")
    if mode != "offline":
        raise RuntimeError(f"DEALPULSE_DATA={mode} isn't available yet; live data arrives with MVP-05/07/08. Use offline.")
    raw = json.loads((FIXTURES / "offline.json").read_text())
    briefs = json.loads((FIXTURES / "sample_briefs.json").read_text())
    return OfflineData(
        snapshot_date=raw["snapshotDate"],
        personas=[Persona(p["id"], p["name"], p["title"], p["team"], p["manager"]) for p in raw["personas"]],
        deals=raw["deals"], knowledge=raw["knowledge"], model=raw.get("model"), gap_points=raw["gapPoints"],
        briefs=briefs["briefs"], trace=briefs["trace"],
    )


# ------------------------------------------------------------ access rules (checked before any data is shown)
def can_see(persona: Persona, deal: dict) -> bool:
    """Managers see their team's deals; account executives see only their own."""
    return deal["team"] == persona.team if persona.manager else deal["ownerId"] == persona.id


def visible_deals(data: OfflineData, persona: Persona) -> list[dict]:
    return [d for d in data.deals if can_see(persona, d)]


# ------------------------------------------------------------ pipeline
def filter_deals(deals: list[dict], forecast: str = "All", flagged_only: bool = False, owner: str = "All") -> list[dict]:
    return [d for d in deals if (forecast == "All" or d["forecast"] == forecast)
            and (not flagged_only or d["flag"]) and (owner == "All" or d["owner"] == owner)]


def kpis(deals: list[dict]) -> dict:
    flagged = [d for d in deals if d["flag"]]
    return {
        "deals": len(deals),
        "commit": sum(d["forecast"] == "Commit" for d in deals),
        "pipeline": sum(d["amount"] for d in deals),
        "stage_weighted": sum(d["amount"] * d["stageProbability"] / 100 for d in deals),
        "model_weighted": sum(d["amount"] * d["modelProbability"] / 100 for d in deals),
        "flagged": len(flagged),
        "flagged_amount": sum(d["amount"] for d in flagged),
    }


def money(n: float) -> str:
    return f"${n / 1e6:.2f}M" if n >= 1e6 else f"${round(n / 1000):,}k"


def short_stage(stage: str) -> str:
    return stage.replace("/Price Quote", "").replace("/Review", "")


# ------------------------------------------------------------ deal brief
def drivers(deal: dict, actionable_only: bool, limit: int = 6) -> list[dict]:
    return [d for d in deal["drivers"] if d["actionable"] or not actionable_only][:limit]


def citation_uses(brief: dict) -> dict[str, list[str]]:
    """Which parts of the brief cite each record, e.g. {'00TDP…57': ['Risk 1', 'Answer 1']}."""
    uses: dict[str, list[str]] = {}
    for key, label in (("risks", "Risk"), ("strengths", "Strength"), ("nextSteps", "Next step"), ("qa", "Answer")):
        for i, item in enumerate(brief.get(key) or [], start=1):
            for cite in item.get("citations", []):
                uses.setdefault(cite, []).append(f"{label} {i}")
    return uses


def is_shared(citation: str) -> bool:
    return citation.startswith(("PB-", "PO-"))


def trace_lines(data: OfflineData, persona: Persona, deal: dict) -> list[tuple[str, str]]:
    fill = {"{persona}": persona.name, "{owner}": deal["owner"], "{notes}": str(len(deal["notes"])),
            "{model}": str(deal["modelProbability"]), "{stage}": str(deal["stageProbability"])}
    out = []
    for title, detail in data.trace:
        for k, v in fill.items():
            detail = detail.replace(k, v)
        out.append((title, detail))
    return out


EMPLOYEE_JUDGEMENT = re.compile(r"\b(rank|fire|firing|worst|weak|performance review)\b", re.I)
PEOPLE = re.compile(r"\b(rep|reps|executive|executives|salesperson|marcus|elena|sam|grace|tom[aá]s|aisha)\b", re.I)
PROMPT_ATTACK = re.compile(r"ignore (all )?(prior|previous) instructions|system:", re.I)


@dataclass(frozen=True)
class Answer:
    kind: str          # "blocked" | "answer" | "unavailable"
    text: str
    citations: tuple[str, ...] = ()


def answer(brief: dict | None, question: str) -> Answer:
    """Offline answers: mirrors the guardrail's two blocks, else a sample answer, else an honest 'not here yet'."""
    q = question.strip()
    if not q:
        return Answer("unavailable", "")
    if EMPLOYEE_JUDGEMENT.search(q) and PEOPLE.search(q):
        return Answer("blocked", "Blocked by Guardrails. DealPulse can't judge or rank individual employees. Ask about a deal instead.")
    if PROMPT_ATTACK.search(q):
        return Answer("blocked", "Blocked by Guardrails. This looks like an instruction aimed at the assistant. Rephrase the question about the deal.")
    qa = (brief or {}).get("qa", [])
    words = [w for w in re.findall(r"\w+", q.lower()) if len(w) > 4]
    match = next((x for x in qa if x["q"].lower() == q.lower()), None) or \
        next((x for x in qa if any(w in x["q"].lower() for w in words)), None)
    if match:
        return Answer("answer", match["a"], tuple(match["citations"]))
    hint = f" Try: “{qa[0]['q']}”" if qa else ""
    return Answer("unavailable", "In the live app Claude answers from this deal's notes and the shared playbook only, "
                  f"with citations (MVP-08). Offline mode has sample answers only.{hint}")


def crm_text(brief: dict) -> str:
    return f"Next Step: {brief['crmUpdate']['nextStep']}\n\nDescription: {brief['crmUpdate']['description']}"


# ------------------------------------------------------------ model card
FEATURE_LABELS = {
    "stage_index": "Stage", "days_to_close": "Days to close date", "days_in_stage": "Days in current stage",
    "deal_age_days": "Deal age", "close_pushes": "Close-date slips", "log_amount": "Deal size",
    "competitor_present": "Competitor in deal", "exec_meeting_last_30d": "Executive meeting (30 days)",
    "champion_identified": "Champion identified", "activities_last_30d": "Activities (30 days)",
    "days_since_last_activity": "Days since last activity", "activity_trend_30d": "Activity trend",
    "contact_roles": "Contacts engaged", "economic_buyer_identified": "Economic buyer identified",
    "discount_pct": "Discount %", "is_expansion": "Expansion deal", "segment_enterprise": "Enterprise segment",
    "open_severe_cases": "Open severe cases",
}


def feature_label(feature: str) -> str:
    if feature in FEATURE_LABELS:
        return FEATURE_LABELS[feature]
    for prefix, label in (("lead_", "Lead source: "), ("industry_", "Industry: "), ("product_", "Product: "), ("segment_", "Segment: ")):
        if feature.startswith(prefix):
            return label + feature[len(prefix):].replace("_", " ")
    return feature.replace("_", " ")

"""Offline tests for the planner graph, the conditions tool, and the reviewer (MVP-06)."""
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from weekendwise.config import Settings
from weekendwise.planner import Planner
from weekendwise.retrieval import OK, RetrievalResult, RetrievedChunk
from weekendwise.review import review_draft
from weekendwise.tools import REJECTED_INVALID_ARGS, REJECTED_UNSEEDED_DATE, ConditionsTool

SETTINGS = Settings(
    project_id="demo", generation_location="global", embedding_location="us-central1",
    generation_model_id="gen", embedding_model_id="emb", embedding_dimension=3,
)
RAINY_SAT = "2027-05-15"
FIXTURES = {
    f"san-francisco__{RAINY_SAT}": {"cityId": "san-francisco", "city": "San Francisco", "demoDate": RAINY_SAT,
                                    "condition": "rain", "tempHighF": 61, "indoorRecommended": True,
                                    "summary": "Sample rain.", "simulated": True, "icon": "☁"},
}


def chunk(i, content_type="attraction-note"):
    return RetrievedChunk(f"C{i}--c01", f"SRC-{i}", "san-francisco", f"Guide {i}", "s", content_type, "2026-10-15", f"text {i}", 0.2 + i / 100)


class FakeRetriever:
    def __init__(self, chunks):
        self.chunks, self.queries = chunks, []

    def retrieve(self, query, city_id, top_k=None):
        self.queries.append(query)
        r = RetrievalResult(status=OK if self.chunks else "insufficient_evidence", query=query, city_id=city_id)
        r.chunks = list(self.chunks)
        return r


class FakeVertex:
    def __init__(self, *drafts):
        self.drafts, self.calls, self.prompts = list(drafts), 0, []

    def generate_text(self, prompt, **kw):
        self.calls += 1
        self.prompts.append(prompt)
        d = self.drafts.pop(0) if self.drafts else self.last
        self.last = d
        return SimpleNamespace(text=d if isinstance(d, str) else json.dumps(d))


def good_draft(dates=("2027-05-14", "2027-05-15", "2027-05-16"), cite="S1", total=None, over=False, extra=""):
    days = [{"date": d, "title": "Day", "activities": [
        {"time": "10:00", "title": f"Museum {d}{extra}", "description": "Art.", "area": "SoMa", "categoryId": "activities",
         "estimatedCostUsd": 20, "citations": [cite]}]} for d in dates]
    lines = [{"categoryId": "stays", "amountUsd": 200, "note": "2 nights"},
             {"categoryId": "food-coffee", "amountUsd": 100, "note": "meals"},
             {"categoryId": "activities", "amountUsd": 60, "note": "admissions"},
             {"categoryId": "local-transit", "amountUsd": 40, "note": "transit"}]
    return {"headline": "A weekend", "days": days,
            "budget": {"lineItems": lines, "totalUsd": 400 if total is None else total, "overBudget": over, "substitutions": []},
            "whyThisFits": "Fits.", "assumptions": [], "uncertainties": []}


def request(**over):
    r = {"destination": "San Francisco", "cityId": "san-francisco", "startDate": "2027-05-14", "endDate": "2027-05-16",
         "travelers": 2, "budget": 600, "interestIds": ["coffee", "art-design"], "constraints": [], "notes": ""}
    r.update(over)
    return r


def planner(drafts, chunks=None, settings=SETTINGS, clock=None):
    retr = FakeRetriever([chunk(1), chunk(2), chunk(3, "outdoor-guide")] if chunks is None else chunks)
    vtx = FakeVertex(*drafts)
    kw = {"clock": clock} if clock else {}
    p = Planner(settings, retr, vtx, ConditionsTool(FIXTURES, settings.supported_city_ids), **kw)
    return p, retr, vtx


# ---------------------------------------------------------------- graph

def test_ordinary_request_completes_without_tool():
    p, retr, vtx = planner([good_draft()])
    out = p.plan(request())
    assert out["status"] == "complete" and out["toolCalls"] == [] and out["usage"]["toolCalls"] == 0
    assert out["review"]["outcome"] == "approved" and vtx.calls == 1
    assert out["budget"]["total"] == 400 and out["budget"]["status"] == "on-track"
    assert out["citations"][0]["chunkId"] == "C1--c01"
    assert all(a["citations"] == ["C1--c01"] for d in out["days"] for a in d["activities"])


def test_rainy_request_calls_tool_once_for_the_named_day():
    p, retr, vtx = planner([good_draft()])
    out = p.plan(request(constraints=["Show an indoor alternative for Saturday if it rains"]))
    assert out["usage"]["toolCalls"] == 1 and len(out["toolCalls"]) == 1
    assert out["toolCalls"][0]["args"] == {"city": "San Francisco", "demo_date": RAINY_SAT}
    assert retr.queries[0] == "Show an indoor alternative for Saturday if it rains"  # traveler's words first
    assert retr.queries[1].startswith("indoor options")
    sat = next(d for d in out["days"] if d["date"] == RAINY_SAT)
    assert sat["conditions"]["simulated"] is True
    assert any("simulated" in c for c in out["caveats"])


def test_unseeded_date_fails_closed_but_plan_continues():
    p, _, _ = planner([good_draft(dates=("2030-01-05", "2030-01-06"))])
    out = p.plan(request(startDate="2030-01-05", endDate="2030-01-06", notes="What if the weather is bad?"))
    assert out["toolCalls"][0]["status"] == REJECTED_UNSEEDED_DATE
    assert out["status"] == "complete" and any("couldn't be checked" in c for c in out["caveats"])


def test_invalid_request_makes_no_calls():
    p, retr, vtx = planner([good_draft()])
    out = p.plan(request(cityId="tokyo", destination="Tokyo", travelers=0, endDate="2027-05-25"))
    assert out["status"] == "invalid_request" and len(out["errors"]) >= 2
    assert vtx.calls == 0 and retr.queries == [] and out["usage"]["toolCalls"] == 0


def test_no_evidence_asks_a_clarifying_question():
    p, _, vtx = planner([good_draft()], chunks=[])
    out = p.plan(request())
    assert out["status"] == "needs_clarification" and "?" in out["question"] and vtx.calls == 0


def test_reviewer_triggers_exactly_one_revision():
    bad = good_draft(cite="S9", total=999)  # fabricated label + wrong arithmetic
    p, _, vtx = planner([bad, good_draft()])
    out = p.plan(request())
    assert vtx.calls == 2 and out["review"]["outcome"] == "approved_after_revision" and out["review"]["revisionCount"] == 1
    assert "REVIEWER FEEDBACK" in vtx.prompts[1] and "S9" in vtx.prompts[1]


def test_still_bad_after_revision_ships_with_warnings_and_drops_unsupported_items():
    bad = good_draft(cite="S9")
    p, _, vtx = planner([bad, bad])
    out = p.plan(request())
    assert vtx.calls == 2 and out["review"]["outcome"] == "approved_with_warnings"
    assert all(d["activities"] == [] for d in out["days"])  # nothing unsupported is shown as fact
    assert any("no supporting guide" in u for u in out["uncertainties"])


def test_model_call_cap_prevents_revision():
    p, _, vtx = planner([good_draft(cite="S9"), good_draft()], settings=replace(SETTINGS, planner_max_model_calls=1))
    out = p.plan(request())
    assert vtx.calls == 1 and out["review"]["revisionCount"] == 0


def test_deadline_prevents_revision():
    now = [0.0]
    p, _, vtx = planner([good_draft(cite="S9"), good_draft()], clock=lambda: now[0])
    original = vtx.generate_text

    def slow_call(prompt, **kw):  # the first model call uses up the whole time budget
        now[0] += SETTINGS.planner_deadline_seconds + 1
        return original(prompt, **kw)

    vtx.generate_text = slow_call
    out = p.plan(request())
    assert vtx.calls == 1 and out["review"]["revisionCount"] == 0


def test_invalid_json_gets_one_repair_attempt():
    p, _, vtx = planner(["not json", good_draft()])
    out = p.plan(request())
    assert out["status"] == "complete" and vtx.calls == 2


def test_server_recomputes_total_and_flags_over_budget():
    d = good_draft(total=400)
    p, _, _ = planner([d, d])
    out = p.plan(request(budget=300))
    assert out["budget"]["total"] == 400 and out["budget"]["status"] == "over-budget"
    assert any("over the 300 budget" in i for i in out["review"]["issues"])


def test_trace_is_user_safe_summaries_only():
    p, _, _ = planner([good_draft()])
    out = p.plan(request(constraints=["indoor plan if it rains Saturday"]))
    labels = [t["label"] for t in out["trace"]]
    assert labels[:3] == ["Read your trip details", "Checked simulated local conditions", "Searched city guides (3 passages)"]
    assert all(set(t) == {"step", "label", "status"} for t in out["trace"])


# ---------------------------------------------------------------- reviewer

def labels(*types):
    return {f"S{i}": SimpleNamespace(content_type=t) for i, t in enumerate(types, start=1)}


DATES = ["2027-05-14", "2027-05-15", "2027-05-16"]


def test_reviewer_passes_a_good_draft():
    r = review_draft(good_draft(), dates=DATES, budget_limit=600, labels=labels("attraction-note"))
    assert r.passed and all(r.checks.values())


def test_reviewer_flags_outdoor_activity_on_indoor_day():
    r = review_draft(good_draft(), dates=DATES, budget_limit=600, labels=labels("outdoor-guide"), indoor_dates={RAINY_SAT})
    assert not r.passed and r.checks["weatherRespected"] is False


@pytest.mark.parametrize("phrase,flagged", [
    ("I have booked a table for you", True), ("Your reservation is confirmed", True),
    ("I booked a table for six tonight", True), ("Your trip is fully confirmed.", True),
    ("We reserved two seats", True), ("Your table is booked", True),
    ("Book directly with the winery", False), ("Reservations are usually needed", False),
    ("Tickets should be booked in advance", False), ("Confirm hours before you go", False),
    ("Check that tastings are reserved ahead", False), ("Many tables are booked on weekends", False),
])
def test_reviewer_flags_booking_claims_but_not_advice(phrase, flagged):
    d = good_draft()
    d["days"][0]["activities"][0]["description"] = phrase
    r = review_draft(d, dates=DATES, budget_limit=600, labels=labels("attraction-note"))
    assert (r.checks["noBookingClaims"] is False) == flagged


@pytest.mark.parametrize("description,ok", [
    ("Visit two wineries for a tasting.", False),
    ("Visit two wineries; use a designated driver.", True),
    ("Wine tasting downtown. Never drink and drive.", True),
    ("Coffee and a museum.", True),
])
def test_reviewer_requires_drink_driving_guidance_for_alcohol(description, ok):
    d = good_draft()
    d["days"][0]["activities"][0]["description"] = description
    r = review_draft(d, dates=DATES, budget_limit=600, labels=labels("attraction-note"))
    assert r.checks["drinkDrivingGuidance"] is ok


def test_alcohol_plans_always_get_the_safety_caveat():
    d = good_draft()
    d["days"][0]["activities"][0]["description"] = "Wine tasting. Use a designated driver."
    p, _, _ = planner([d])
    out = p.plan(request())
    assert any("Never drink and drive" in c for c in out["caveats"])


def test_reviewer_checks_itemization_and_missing_categories():
    d = good_draft()
    d["days"][0]["activities"][0]["estimatedCostUsd"] = 500  # activities line is only 60
    d["budget"]["lineItems"] = d["budget"]["lineItems"][:3]
    d["budget"]["totalUsd"] = 360
    r = review_draft(d, dates=DATES, budget_limit=600, labels=labels("attraction-note"))
    codes = {i.code for i in r.issues}
    assert {"budget_itemization", "budget_categories"} <= codes


# ---------------------------------------------------------------- tool

def test_tool_returns_fixture_only_for_allowlisted_pairs():
    tool = ConditionsTool(FIXTURES, SETTINGS.supported_city_ids)
    ok = tool("San Francisco", RAINY_SAT)
    assert ok.status == "ok" and ok.conditions["simulated"] is True
    assert tool("San Francisco", "2027-05-20").status == REJECTED_UNSEEDED_DATE
    assert tool("Tokyo", RAINY_SAT).status == REJECTED_INVALID_ARGS
    assert tool("San Francisco", "next Saturday").status == REJECTED_INVALID_ARGS
    assert tool(None, RAINY_SAT).status == REJECTED_INVALID_ARGS
    assert tool("San Francisco; DROP TABLE", RAINY_SAT).status == REJECTED_INVALID_ARGS


def test_bundled_fixtures_cover_every_city():
    tool = ConditionsTool(supported_city_ids=SETTINGS.supported_city_ids)
    for city in SETTINGS.supported_city_ids:
        assert tool.seeded_dates(city), city


def test_no_interests_asks_what_you_like_without_any_calls():
    p, retr, vtx = planner([good_draft()])
    out = p.plan(request(interestIds=[], notes="Plan something fun."))
    assert out["status"] == "needs_clarification" and "interests" in out["question"]
    assert vtx.calls == 0 and retr.queries == [] and out["usage"]["toolCalls"] == 0


def test_plan_stream_yields_steps_then_the_same_result():
    p, _, _ = planner([good_draft()])
    events = list(p.plan_stream(request()))
    assert [k for k, _ in events] == ["step"] * 4 + ["result"]
    assert [d["node"] for k, d in events if k == "step"] == ["normalize", "retrieve", "draft", "review"]
    assert events[-1][1]["status"] == "complete"


def test_search_cap_keeps_travelers_words_and_budget_and_drops_transit_first():
    p, retr, _ = planner([good_draft()])
    p.plan(request(interestIds=["coffee", "art-design", "outdoors"], notes="We like art"))
    q = retr.queries
    assert len(q) == 5 and q[0] == "We like art"
    assert any(x.startswith("budget estimates") for x in q)
    assert not any(x.startswith("getting around") for x in q)  # dropped before any interest
    assert sum(x.startswith(("Coffee", "Art", "Outdoors")) for x in q) == 3

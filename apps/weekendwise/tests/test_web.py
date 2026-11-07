"""Offline tests for the web server (MVP-03 health, MVP-07 wiring, MVP-09 logging). No cloud calls."""
import json
import logging

import pytest
from starlette.testclient import TestClient

from weekendwise.errors import ModelTimeoutError
from weekendwise.observability import JsonFormatter, TimedRetriever, event, request_id_var
from weekendwise.web.server import Limits, create_app

from test_planner import good_draft, planner, request


class FakeRuntime:
    def __init__(self, plan_obj=None, ready=(True, "ok"), boom=None):
        self.plan_obj, self._ready, self.boom = plan_obj, ready, boom

    def planner(self):
        if self.boom:
            raise self.boom
        return self.plan_obj

    def ready(self):
        return self._ready


class RaisingPlanner:
    def __init__(self, exc):
        self.exc = exc

    def plan_stream(self, body):
        yield "step", {"step": "normalize", "label": "Read your trip details", "status": "done", "node": "normalize"}
        raise self.exc


def client(runtime, limits=None):
    return TestClient(create_app(runtime, limits or Limits(3, 50, 1000)))


def events(resp):
    out = []
    for block in resp.text.split("\n\n"):
        name, data = None, None
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:])
        if name:
            out.append((name, data))
    return out


def test_pages_static_and_security_headers():
    c = client(FakeRuntime())
    for path in ("/", "/plan", "/itinerary", "/sources", "/architecture", "/unknown-page"):
        r = c.get(path)
        assert r.status_code == 200 and "weekendwise" in r.text.lower()
    r = c.get("/static/app.js")
    assert r.status_code == 200 and "fetch(\"/api/plan\"" in r.text
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert c.get("/static/favicon.svg").status_code == 200
    assert c.get("/api/nope").status_code == 404


def test_no_inline_scripts_or_handlers_in_html():
    html = client(FakeRuntime()).get("/").text
    assert "onclick=" not in html and "onsubmit=" not in html and "oninput=" not in html
    assert "<script>" not in html  # only external scripts, allowed by the CSP


def test_health_and_readiness():
    c = client(FakeRuntime(ready=(False, "PermissionDenied")))
    assert c.get("/healthz").json()["status"] == "ok"
    assert c.get("/health").json()["status"] == "ok"
    r = c.get("/readyz")
    assert r.status_code == 503 and r.json()["detail"] == "PermissionDenied"
    assert client(FakeRuntime()).get("/readyz").status_code == 200


def test_config_lists_all_four_cities_and_six_samples():
    cfg = client(FakeRuntime()).get("/api/config").json()
    assert [c["id"] for c in cfg["cities"]][0] == "san-francisco"
    assert {c["id"] for c in cfg["cities"]} == {"san-francisco", "portland", "santa-cruz", "napa-valley"}
    assert len(cfg["interests"]) == 6 and len(cfg["samples"]) == 6 and len(cfg["budgetCategories"]) == 4
    assert cfg["limits"]["maxTripDays"] == 3


def test_plan_streams_steps_then_result():
    p, _, vtx = planner([good_draft()])
    r = client(FakeRuntime(p)).post("/api/plan", json=request())
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["x-request-id"]
    evs = events(r)
    steps = [d["node"] for n, d in evs if n == "step"]
    assert steps == ["normalize", "retrieve", "draft", "review"]
    assert evs[-1][0] == "result" and evs[-1][1]["status"] == "complete" and vtx.calls == 1


def test_invalid_request_is_returned_without_model_calls():
    p, _, vtx = planner([good_draft()])
    evs = events(client(FakeRuntime(p)).post("/api/plan", json=request(cityId="paris", destination="Paris")))
    assert evs[-1][1]["status"] == "invalid_request" and vtx.calls == 0


def test_model_failure_becomes_a_friendly_error_without_stack_trace():
    r = client(FakeRuntime(RaisingPlanner(ModelTimeoutError("The model took too long to answer.")))).post("/api/plan", json=request())
    name, data = events(r)[-1]
    assert name == "error" and data["message"] == "The model took too long to answer."
    r = client(FakeRuntime(RaisingPlanner(RuntimeError("secret internals /path/to/file.py")))).post("/api/plan", json=request())
    name, data = events(r)[-1]
    assert name == "error" and "secret" not in r.text and "Traceback" not in r.text


def test_bad_bodies_are_rejected():
    c = client(FakeRuntime())
    assert c.post("/api/plan", content=b"not json", headers={"content-type": "application/json"}).status_code == 400
    assert c.post("/api/plan", content=b"[1,2]").status_code == 400
    assert c.post("/api/plan", content=b"{" + b" " * 9000 + b"}").status_code == 413
    assert c.get("/api/plan").status_code == 405


def test_planner_setup_failure_is_503_and_releases_the_slot():
    limits = Limits(1, 50, 1000)
    c = client(FakeRuntime(boom=RuntimeError("no credentials")), limits)
    for _ in range(3):  # would be "busy" if the slot leaked
        r = c.post("/api/plan", json=request())
        assert r.status_code == 503 and r.json()["code"] == "unavailable"


def test_rate_and_daily_limits():
    p, _, _ = planner([good_draft()] * 5)
    c = client(FakeRuntime(p), Limits(3, 2, 1000))
    assert c.post("/api/plan", json=request()).status_code == 200
    assert c.post("/api/plan", json=request()).status_code == 200
    r = c.post("/api/plan", json=request())
    assert r.status_code == 429 and r.json()["code"] == "rate_limited"
    c2 = client(FakeRuntime(p), Limits(3, 50, 1))
    assert c2.post("/api/plan", json=request()).status_code == 200
    assert c2.post("/api/plan", json=request()).json()["code"] == "daily_limit"


def test_concurrency_limit():
    limits = Limits(1, 50, 1000)
    assert limits.admit("a") is None
    assert limits.admit("b") == "busy"
    limits.release()
    assert limits.admit("b") is None


# ---------------------------------------------------------------- logging (MVP-09)

def test_json_logs_carry_request_id_and_no_prompt_text(capsys):
    record = logging.LogRecord("weekendwise", logging.INFO, __file__, 1, "model call", None, None)
    record.fields = {"stage": "draft", "latencyMs": 12}
    token = request_id_var.set("abc123")
    try:
        line = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert line["requestId"] == "abc123" and line["severity"] == "INFO" and line["stage"] == "draft"


def test_plan_logs_never_include_user_notes(capsys):
    p, _, _ = planner([good_draft()])
    secret = "MY-PRIVATE-NOTE-12345"
    client(FakeRuntime(p)).post("/api/plan", json=request(notes=secret, constraints=[secret]), headers={"x-request-id": "req-1"})
    out = capsys.readouterr().out
    lines = [json.loads(l) for l in out.splitlines() if l.startswith("{")]
    assert any(l["message"] == "plan finished" and l["requestId"] == "req-1" and l["status"] == "complete" for l in lines)
    assert secret not in out


def test_timed_retriever_logs_counts_not_query(capsys):
    from test_planner import FakeRetriever, chunk
    TimedRetriever(FakeRetriever([chunk(1)])).retrieve("a very private query", "san-francisco")
    out = capsys.readouterr().out
    assert '"resultCount": 1' in out and "private query" not in out

"""CL-09, CL-10, CL-11: a fair test between the agents, guardrails, the loop, the MCP bridge, scoring and recordings."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from contextloop import config
from contextloop.agent import config as cfg

IN_STACK = os.environ.get("PGHOST") == "postgres"
HAVE_WH = config.SERVING_PATH.exists()


def truth():
    return json.loads((config.TRUTH_DIR / "truth.json").read_text())


# ---- fair test ---------------------------------------------------------------------------------------------------------

@pytest.mark.skipif(not HAVE_WH, reason="needs the warehouse")
def test_prompts_share_everything_but_context_and_tools():
    from contextloop.agent import governed, naive

    n, g = naive.system_prompt(), governed.system_prompt()
    assert n.startswith(cfg.BASE_SYSTEM) and g.startswith(cfg.BASE_SYSTEM)
    assert "run_sql" in n and "run_sql" not in g
    assert [t["name"] for t in naive.tools()] == ["run_sql"]


def test_both_agents_use_one_runner_configuration():
    import inspect

    from contextloop.agent import governed, naive

    for mod in (naive, governed):
        src = inspect.getsource(mod.answer)
        assert "runner.run(" in src
    s = cfg.shared_settings()
    assert s["model"] in cfg.SUPPORTED_MODELS and s["effort"] == "high" and s["max_tool_calls"] == 15


def test_model_defaults_to_opus_and_rejects_unknown_models(monkeypatch):
    import importlib

    monkeypatch.delenv("CONTEXTLOOP_MODEL", raising=False)
    assert importlib.reload(cfg).MODEL == "claude-opus-5-5"
    monkeypatch.setenv("CONTEXTLOOP_MODEL", "grok-4.7")
    with pytest.raises(ValueError):
        importlib.reload(cfg)
    monkeypatch.delenv("CONTEXTLOOP_MODEL")
    importlib.reload(cfg)


@pytest.mark.parametrize("model,fallback", [("claude-opus-5-5", True), ("claude-sonnet-5-5", True), ("claude-haiku-5-5", False)])
def test_refusal_fallback_only_where_supported(monkeypatch, model, fallback):
    from contextloop.agent import runner

    monkeypatch.setattr(cfg, "MODEL", model)
    p = runner.request_params("sys", [], [])
    assert p["model"] == model and ("fallbacks" in p) is fallback and ("betas" in p) is fallback
    assert p["thinking"] == {"type": "adaptive"} and p["output_config"] == {"effort": cfg.EFFORT}


def test_cost_uses_the_model_price_card(monkeypatch):
    from contextloop.agent import runner

    usage = {"input_tokens": 1_000_000, "output_tokens": 100_000, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    monkeypatch.setattr(cfg, "MODEL", "claude-opus-5-5")
    assert runner.request_cost(usage) == pytest.approx(4.0 + 2.0)
    monkeypatch.setattr(cfg, "MODEL", "claude-haiku-5-5")
    assert runner.request_cost(usage) == pytest.approx(0.50 + 0.25)  # over 100K tokens: the long-prompt rate card
    small = usage | {"input_tokens": 50_000, "output_tokens": 5_000}
    assert runner.request_cost(small) == pytest.approx(0.005 + 0.0025)


# ---- naive guardrails --------------------------------------------------------------------------------------------------

@pytest.mark.skipif(not HAVE_WH, reason="needs the warehouse")
@pytest.mark.parametrize("sql", ["DROP TABLE sap_s4.vbak", "INSERT INTO sap_s4.kna_1 (kunnr) VALUES ('x')", "DELETE FROM zendesk.ticket"])
def test_naive_agent_cannot_write(sql):
    from contextloop.agent import naive

    assert "error" in naive.run_sql(sql)


@pytest.mark.skipif(not HAVE_WH, reason="needs the warehouse")
def test_naive_agent_sees_only_raw_schemas():
    from contextloop.agent import naive

    assert "error" in naive.run_sql("SELECT * FROM marts.account_risk")
    assert "error" in naive.run_sql("SELECT * FROM fivetran_log.sync_log")
    assert naive.run_sql("SELECT count(*) FROM sap_s4.vbak")["rows"][0][0] > 0


# ---- the loop, with a scripted client (no API call) --------------------------------------------------------------------

class FakeClient:
    """Plays back scripted assistant turns, recording what the loop sends."""

    def __init__(self, turns):
        self.turns, self.sent = list(turns), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kw):
        self.sent.append(kw)
        content = self.turns.pop(0)
        stop = "tool_use" if any(b.type == "tool_use" for b in content) else "end_turn"
        return SimpleNamespace(content=content, stop_reason=stop, model=kw["model"],
                               usage=SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=0, cache_creation_input_tokens=0))


def tool(name, inp, i):
    return SimpleNamespace(type="tool_use", name=name, input=inp, id=f"tu{i}")


ANSWER = {"answer_summary": "x", "at_risk_accounts": [], "value": 25, "unit": "count", "is_current": None, "data_age_days": None,
          "metrics_used": [], "lineage": [], "freshness": [], "assumptions": [], "caveats": []}


def test_loop_enforces_the_tool_budget_and_records_the_answer():
    from contextloop.agent import runner

    turns = [[tool("run_sql", {"sql": f"select {i}"}, i)] for i in range(cfg.MAX_TOOL_CALLS + 2)]
    turns.append([tool("submit_answer", ANSWER, 99)])
    calls = []
    tr = runner.run("naive", "G4", "q", "sys", [{"name": "run_sql"}], lambda n, a: calls.append(a) or {"rows": []},
                    client=FakeClient(turns))
    assert len(calls) == cfg.MAX_TOOL_CALLS
    assert tr.answer == ANSWER and tr.usage["requests"] == len(turns)
    assert sum(1 for s in tr.steps if s.is_error) == 2  # the two calls over budget were refused


def test_loop_uses_shared_model_settings_and_fallbacks():
    from contextloop.agent import runner

    client = FakeClient([[tool("submit_answer", ANSWER, 1)]])
    runner.run("governed", "G4", "q", "sys", [], lambda n, a: {}, client=client)
    kw = client.sent[0]
    assert kw["model"] == cfg.MODEL and kw["output_config"] == {"effort": cfg.EFFORT} and kw["thinking"] == {"type": "adaptive"}
    if cfg.MODEL in cfg.FALLBACK_MODELS:
        assert kw["fallbacks"] == "default" and cfg.FALLBACK_BETA in kw["betas"]
    assert kw["tools"][-1]["name"] == "submit_answer"


# ---- scoring -----------------------------------------------------------------------------------------------------------

def test_scoring_rules():
    from contextloop.eval.score import score

    t = truth()
    g = t["golden"]
    good = {"at_risk_accounts": [{"account_name": r["name"]} for r in t["at_risk"]]}
    assert score("G1", good, t)["correct"]
    assert not score("G1", {"at_risk_accounts": good["at_risk_accounts"][:-1]}, t)["correct"]
    assert score("G2", {"value": g["G2"] + 0.4}, t)["correct"] and not score("G2", {"value": g["G2"] + 0.6}, t)["correct"]
    assert score("G2", {"value": g["G2"] / 100}, t)["correct"]
    assert score("G3", {"value": g["G3"] * 1.009}, t)["correct"] and not score("G3", {"value": g["G3"] * 1.02}, t)["correct"]
    assert score("G4", {"value": g["G4"]}, t)["correct"] and not score("G4", {"value": g["G4"] + 1}, t)["correct"]
    assert score("G5", {"is_current": g["G5"]["current"]}, t)["correct"]
    assert not score("G6", None, t)["correct"]


def test_explainer_names_traps_from_naive_sql():
    from contextloop.agent.explain import explain

    t = truth()
    traps = json.loads((config.TRUTH_DIR / "traps.json").read_text())
    trace = {"question_id": "G1", "steps": [
        {"tool": "run_sql", "input": {"sql": "SELECT kunnr, count(*) FILTER (WHERE wadat_ist <= vdatu)\nFROM sap_s4.likp l JOIN sap_s4.vbak v"}},
        {"tool": "run_sql", "input": {"sql": "SELECT id, name, tier_c\nFROM salesforce.account WHERE tier_c = 'Strategic'"}}],
        "answer": {"answer_summary": "Three accounts", "caveats": [], "at_risk_accounts": [{"account_name": "Quenmere Paper Mills GmbH"}]}}
    found = {f["trap"] for f in explain(trace, t, traps)}
    assert {"T1", "T2", "T4", "T5", "T6"} <= found
    assert any(f["sql_line"] for f in explain(trace, t, traps))


# ---- MCP servers and bridge (inside the stack) -------------------------------------------------------------------------

@pytest.mark.skipif(not IN_STACK, reason="runs inside the Compose network")
def test_bridge_lists_tools_from_all_three_servers():
    from contextloop.agent.mcp_bridge import Bridge

    b = Bridge()
    names = {t["name"] for t in b.connect()}
    assert {"list_metrics", "query_metric", "check_freshness", "dbt_get_lineage_dev", "dbt_get_node_details_dev", "dbt_list"} == names
    assert {b.tool_origin(n) for n in names} == {"dbt-mcp", "mcp-metrics", "mcp-freshness"}


@pytest.mark.skipif(not IN_STACK, reason="runs inside the Compose network")
def test_query_metric_through_the_bridge_returns_the_truth():
    from contextloop.agent.mcp_bridge import Bridge

    b = Bridge()
    b.connect()
    r = b.call("query_metric", {"metrics": ["account_risk_flag"], "group_by": ["account"],
                                "where": "{{ Dimension('account__is_strategic') }} = true"})
    flagged = {row[0] for row in r["rows"] if row[1] == 1}
    assert flagged == {x["kunnr"] for x in truth()["at_risk"]}
    assert "compiled_sql" in r and "definitions" in r
    f = b.call("check_freshness", {})
    assert (not next(s for s in f["sources"] if s["source"] == "zendesk")["within_window"]) == config.T6_STALE_ZENDESK


# ---- recordings --------------------------------------------------------------------------------------------------------

def _recordings():
    from contextloop.eval.run import recordings_dir

    return sorted((recordings_dir() / "demo").glob("*/*.json")) if (recordings_dir() / "demo").exists() else []


@pytest.mark.skipif(not _recordings(), reason="no recordings yet (make record)")
def test_recorded_scores_still_match_the_current_truth():
    from contextloop.eval.score import score

    t = truth()
    for p in _recordings():
        rec = json.loads(p.read_text())
        assert score(rec["question_id"], rec["answer"], t)["correct"] == rec["score"]["correct"], p.name


@pytest.mark.skipif(not _recordings(), reason="no recordings yet (make record)")
def test_governed_numbers_come_from_query_metric():
    for p in _recordings():
        rec = json.loads(p.read_text())
        if rec["agent"] != "governed" or rec["question_id"] != "G1" or not rec.get("answer"):
            continue
        seen = {round(v, 4) for s in rec["steps"] if s["tool"] == "query_metric" for row in s["output"].get("rows", [])
                for v in row if isinstance(v, (int, float))}
        for a in rec["answer"]["at_risk_accounts"]:
            if a["on_time_rate"] is not None:
                # the agent may round (0.615 for 0.6154), but the value must match a query_metric result
                assert any(abs(a["on_time_rate"] - v) < 0.0005 for v in seen), a["account_name"]


def test_naive_sql_help_is_dialect_only():
    """The naive agent gets column types and dialect help (not traps): typed schema, AS hint, and columns on a binder error."""
    from contextloop.agent import naive

    prompt = naive.system_prompt()
    assert "netwr text" in prompt and "CAST them to DECIMAL" in prompt
    assert "AS before a column alias" in naive.RUN_SQL_TOOL["description"]
    out = naive.run_sql("SELECT max(updated_at) AS m FROM zendesk.ticket_tag")
    assert "error" in out and "ticket_id int" in out["columns_of_tables_used"]["zendesk.ticket_tag"]


def test_naive_sql_repairs_dialect_slips():
    from contextloop.agent import naive

    out = naive.run_sql("SELECT count(*) n, count(l.vbeln) matched FROM sap_s4.likp l")
    assert "error" not in out and out["columns"] == ["n", "matched"] and "AS before the alias matched" in out["auto_fixed"][0]
    out = naive.run_sql("SELECT count(*) AS n FROM sap_s4.likp WHERE vbeln <> 'x'\"")
    assert "error" not in out and "stray" in out["auto_fixed"][0]
    assert naive.run_sql("SELECT try_strptime('00000000', '%Y%m%d') AS d")["rows"] == [[None]]


def test_leaked_answer_fields_are_recovered():
    from contextloop.agent.runner import repair_answer

    leaked = {"answer_summary": 'Two accounts.</answer_summary>\n<parameter name="at_risk_accounts">[{"account_name": "A"}]'
                                '</parameter>\n<parameter name="value">3</parameter>', "at_risk_accounts": [], "value": None,
              "caveats": ["kept"]}
    fixed, repaired = repair_answer(leaked)
    assert repaired and fixed["answer_summary"] == "Two accounts." and fixed["at_risk_accounts"] == [{"account_name": "A"}]
    assert fixed["value"] == 3 and fixed["caveats"] == ["kept"]
    assert repair_answer({"answer_summary": "Fine."}) == ({"answer_summary": "Fine."}, False)


def test_pass_bar_is_the_gap_and_the_headline_list():
    """CL-09, CL-11: the restated bar (owner, 11 Nov 2026)."""
    from contextloop.eval.run import passes

    assert passes({"governed": 6, "naive": 2.7}, naive_g1_always_wrong=True)
    assert not passes({"governed": 6, "naive": 2.7}, naive_g1_always_wrong=False)  # the headline list must always be wrong
    assert not passes({"governed": 5, "naive": 2.7}, naive_g1_always_wrong=True)  # gap under 3 points
    assert not passes({"governed": 4.7, "naive": 1}, naive_g1_always_wrong=True)  # governed under 5

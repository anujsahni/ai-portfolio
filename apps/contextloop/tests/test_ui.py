"""CL-12, CL-13, CL-15, CL-17: every page renders its main path without errors (Streamlit's testing API), the architecture page is
complete, and the scorecard's numbers match the sync log."""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from contextloop import config

IN_STACK = os.environ.get("PGHOST") == "postgres"
ROOT = Path(__file__).resolve().parents[1]


def page(name: str) -> AppTest:
    at = AppTest.from_string(f"from contextloop.ui.pages import {name}\n{name}.render()", default_timeout=60)
    return at.run()


@pytest.mark.skipif(not IN_STACK, reason="runs inside the Compose network after `make demo`")
@pytest.mark.parametrize("name", ["home", "act1", "act2", "act3", "act4", "act5", "compare", "scorecard", "architecture"])
def test_page_renders_without_errors(name):
    at = page(name)
    assert not at.exception, at.exception


@pytest.mark.skipif(not IN_STACK, reason="runs inside the Compose network after `make demo`")
def test_act2_shows_every_connector_from_the_sync_log():
    at = page("act2")
    text = " ".join(m.value for m in at.markdown)
    for name in ("SAP S/4HANA", "Carrier tracking Postgres", "Salesforce", "Zendesk"):
        assert name in text


@pytest.mark.skipif(not IN_STACK, reason="runs inside the Compose network after `make demo`")
def test_act5_dry_run_lists_the_governed_accounts():
    from contextloop.activation import sync

    at = page("act5")
    names = set(at.dataframe[0].value["account"])
    assert names == {r["account_name"] for r in sync.governed_rows()}


def test_architecture_page_is_complete():
    js = (ROOT / "contextloop" / "ui" / "architecture" / "architecture.js").read_text()
    ids = re.findall(r'\{ id: "(\w+)", band:', js)
    assert len(ids) == 20
    for nid in ids:  # every node has a laptop and a customer version, each with six non-empty fields
        block = js.split(f'{{ id: "{nid}"', 1)[1].split("] },", 1)[0] + "]"
        for view in ("laptop", "customer"):
            fields = re.search(view + r': \[(.*?)\]', block, re.S).group(1)
            values = re.findall(r'"((?:[^"\\]|\\.)*)"', fields)
            assert len(values) == 6 and all(v.strip() for v in values), (nid, view)
    assert js.count("{ title: \"Act") == 6  # five acts plus the request flow


@pytest.mark.skipif(not config.SERVING_PATH.exists(), reason="needs the warehouse")
def test_scorecard_mar_matches_the_sync_log():
    import duckdb

    from contextloop.ui import scorecard_data

    con = duckdb.connect(str(config.SERVING_PATH), read_only=True)
    expected = dict(con.execute("SELECT connection_id, round(avg(m))::BIGINT FROM (SELECT connection_id, measured_month, "
                                "sum(incremental_rows) m FROM fivetran_log.incremental_mar WHERE measured_month BETWEEN "
                                "date '2026-08-01' AND date '2026-10-01' GROUP BY 1, 2) GROUP BY 1").fetchall())
    con.close()
    assert dict(scorecard_data.mar_estimate()) == expected


def test_scorecard_covers_six_specialties_and_labels_costs_as_estimates():
    from contextloop.ui import scorecard_data

    pov = scorecard_data.POV
    specialties = {s["specialty"] for s in pov["specialists"]}
    assert specialties == {"SAP", "Database and application replication", "Lakehouse and open table formats", "Transformation",
                           "AI and context engineering", "Activation"}
    assert any("ESTIMATED" in a for a in pov["cost_assumptions"])
    assert all(sc["evidence"] in {"act1", "act2", "act3", "act4", "act5"} for sc in pov["success_criteria"])
    assert (ROOT / "docs" / "demo" / "pov-scorecard.md").exists()


def test_scorecard_scores_match_the_evaluation_report():
    from contextloop.ui import scorecard_data

    rep = scorecard_data.report_summary()
    if not rep:
        pytest.skip("no evaluation report yet (make eval)")
    g = scorecard_data.golden_totals()
    assert g["naive"] == round(rep["summary"]["naive"], 1) and g["governed"] == round(rep["summary"]["governed"], 1)
    assert f"{g['naive']:g}/6" in scorecard_data.checks()["golden_scores"][1]


@pytest.mark.skipif(not (config.TRUTH_DIR / "truth.json").exists() or not config.SERVING_PATH.exists(),
                    reason="needs the hidden truth and the warehouse")
def test_compare_view_agrees_with_the_scorer():
    """CL-17: every figure on the without-vs-with page comes from the scorer and the account_risk mart."""
    import json

    import duckdb

    from contextloop.eval.run import load_demo
    from contextloop.eval.score import score
    from contextloop.ui import compare_data

    truth = json.loads((config.TRUTH_DIR / "truth.json").read_text())
    golden = json.loads((config.TRUTH_DIR / "golden.json").read_text())
    traces = {a: {q["id"]: load_demo(a, q["id"]) for q in golden} for a in compare_data.AGENTS}
    if not all(traces["governed"].values()):
        pytest.skip("no recordings yet (make record)")
    con = duckdb.connect(str(config.SERVING_PATH), read_only=True)
    risk = con.execute("SELECT account_name, on_time_rate_90d FROM marts.account_risk").df().to_dict("records")
    con.close()
    rows = compare_data.headline_accounts({a: traces[a]["G1"]["answer"] for a in compare_data.AGENTS}, truth, risk)
    for agent in compare_data.AGENTS:
        sc = score("G1", traces[agent]["G1"]["answer"], truth)
        assert {r["account"] for r in rows if r[agent] == compare_data.WRONG} == set(sc["extra"])
        assert {r["account"] for r in rows if r[agent] == compare_data.MISSED} == set(sc["missed"])
        k = compare_data.kpis(agent, traces[agent], truth, golden, rows, {"on_time_delivery_rate", "late_deliveries",
                              "open_shipping_tickets", "renewals_due_120d", "account_risk_flag", "deliveries_90d"}, {"zendesk"})
        assert k["freshness_right"] is (agent == "governed")  # only the governed agent flags Zendesk as behind
        assert (k["definitions_governed"] == k["definitions"] > 0) is (agent == "governed")
        assert k["correct"] == sum(score(q["id"], traces[agent][q["id"]]["answer"], truth)["correct"] for q in golden)
    assert {r["account"] for r in rows if r["truly_at_risk"]} == set(truth["golden"]["G1"])
    assert all(r["true_rate"] is not None for r in rows)
    assert {t for t, *_ in compare_data.LAYERS} == {"T1", "T2", "T3", "T4", "T5", "T6"}


def test_answer_bullets_split_sentences_and_list_accounts_worst_first():
    from unittest.mock import patch

    from contextloop.ui import common

    with patch.object(common, "st"):
        md = common.answer_bullets({"answer_summary": "Two accounts are at risk. Revenue was $5.8M.", "at_risk_accounts": [
            {"account_name": "B", "on_time_rate": 0.8, "next_step": "Call."}, {"account_name": "A", "on_time_rate": 0.6}]})
    lines = md.splitlines()
    assert lines[0] == "- Two accounts are at risk." and lines[1] == "- Revenue was \\$5.8M."
    assert md.index("**A**") < md.index("**B**") and "*Next step:* Call." in md


def test_pitch_script_drives_the_real_architecture_page():
    """CL-18: every cue in the pitch video's script points at a node, act or request-flow step that exists, beat ids are unique
    (they name the voice-over takes), and the scores it quotes match the evaluation report."""
    import json

    js = (ROOT / "contextloop" / "ui" / "architecture" / "architecture.js").read_text()
    nodes = set(re.findall(r'\{ id: "(\w+)", band:', js))
    steps = js.split("const STEPS = [", 1)[1].split("];", 1)[0].count("{ title:")
    flow = js.split("const FLOW = [", 1)[1].split("];\n", 1)[0].count('[["')
    for hook in ("flowStep", "setView", "showCard", "setStep"):
        assert f"{hook}" in js.split("window.__arch =", 1)[1], hook

    script = json.loads((ROOT / "contextloop" / "ui" / "pitch" / "script.json").read_text())
    beats = [b for sc in script["scenes"] for b in sc["beats"]]
    ids = [b["id"] for b in beats]
    assert len(ids) == len(set(ids))
    html = (ROOT / "contextloop" / "ui" / "pitch" / "pitch.html").read_text()
    assert set(re.findall(r'data-(?:at|out)="([\w-]+)"', html)) <= set(ids)
    for b in beats:
        assert b["text"].strip()
        for c in b.get("cues", []):
            assert 0 <= c["at"] < 1
            assert c.get("card") is None or c["card"] in nodes, c
            assert "step" not in c or 0 <= c["step"] < steps, c
            assert "flow" not in c or 0 <= c["flow"] < flow, c
    assert [c["flow"] for b in beats for c in b.get("cues", []) if "flow" in c] == list(range(flow))  # every flow step, in order

    summary = json.loads((ROOT / "reports" / "latest.json").read_text())["summary"]
    text = " ".join(b["text"] for b in beats)
    assert f"averages {summary['naive']:.1f} out of 6" in text
    assert summary["governed"] == 6 and "six out of six" in text

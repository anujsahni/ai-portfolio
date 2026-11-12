from contextloop.ui.step_describe import describe, describe_error, describe_sql


def test_group_by_names_tables_and_columns():
    d = describe_sql("SELECT tier_c, count(*) FROM salesforce.account WHERE NOT is_deleted GROUP BY tier_c")
    assert d == "Counts and summarises Salesforce accounts, grouped by tier_c; excludes deleted rows"


def test_positional_group_by_uses_result_columns():
    d = describe_sql("SELECT land_1, count(*) FROM sap_s4.kna_1 GROUP BY 1", ["land_1", "n"])
    assert "grouped by land_1" in d


def test_sample_join_and_dates():
    d = describe_sql("SELECT date_diff('day', l.lfdat, s.created_at) FROM carrier_pg.shipment s "
                     "JOIN sap_s4.likp l ON l.vbeln = s.delivery_number LIMIT 15")
    assert d.startswith("Looks at a sample of 15 rows joining carrier shipments and SAP deliveries")
    assert "compares dates" in d


def test_errors_are_explained():
    assert "15 query budget" in describe_error({"error": "Tool budget of 15 calls used up. Submit your answer now."})
    assert "syntax" in describe_error({"error": "ParserException: Parser Error: syntax error at or near"})
    assert describe_error({"rows": []}) is None


def test_mcp_tools():
    assert describe({"tool": "query_metric", "input": {"metrics": ["net_revenue"], "group_by": ["account"]}}) == \
        "Queries governed metric(s) net_revenue by account"
    assert describe({"tool": "check_freshness", "input": {}}).startswith("Checks when each source last synced")


def test_steps_group_into_stages_of_the_agents_reasoning():
    """The step list tells a story: the raw-SQL agent's queries fall into the stages it had to work out for itself, and the
    governed agent's calls into reading definitions, checking freshness, computing and lineage."""
    import json
    from pathlib import Path

    from contextloop.ui.step_stages import TRAP_STAGE, STAGES, stages, step_numbers

    rec = Path(__file__).resolve().parents[1] / "recordings" / "demo"
    naive = json.loads((rec / "naive" / "G1.json").read_text())
    got = [g["key"] for g in stages(naive)]
    assert got[:3] == ["explore", "connect", "late"] and {"compute", "fresh"} <= set(got)
    assert sum(len(g["steps"]) for g in stages(naive)) == len(naive["steps"])  # every step is in exactly one stage
    governed = json.loads((rec / "governed" / "G1.json").read_text())
    assert [g["key"] for g in stages(governed)] == ["definitions", "fresh", "compute", "lineage"]
    assert set(TRAP_STAGE.values()) <= set(STAGES)
    assert step_numbers([(1, {}), (2, {}), (3, {}), (9, {}), (11, {}), (12, {})]) == "1–3, 9, 11–12"

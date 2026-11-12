"""CL-06: the dbt marts match the hidden truth, each trap's handling is guarded by a test, and contracts are enforced."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import duckdb
import pytest

from contextloop import config

pytestmark = pytest.mark.skipif(not config.SERVING_PATH.exists(), reason="run `make sync` and `make build` first")
TARGET = Path(os.environ.get("DBT_TARGET_PATH", config.DBT_PROJECT_DIR / "target"))


@pytest.fixture(scope="module")
def truth():
    return json.loads((config.TRUTH_DIR / "truth.json").read_text())


@pytest.fixture(scope="module")
def wh():
    con = duckdb.connect(str(config.SERVING_PATH), read_only=True)
    yield con
    con.close()


def test_at_risk_list_matches_truth(wh, truth):
    sql = {r[0] for r in wh.execute("SELECT customer_id FROM marts.account_risk WHERE is_at_risk").fetchall()}
    assert sql == {r["kunnr"] for r in truth["at_risk"]}
    for r in truth["at_risk"]:
        row = wh.execute("SELECT on_time_rate_90d, deliveries_90d, open_shipping_tickets, renewal_close_date, next_step "
                         "FROM marts.account_risk WHERE customer_id = ?", [r["kunnr"]]).fetchone()
        assert row[0] == r["on_time_rate"] and row[1] == r["deliveries_90d"] and row[2] == r["open_shipping_tickets"]
        assert (row[3].isoformat() if row[3] else None) == r["renewal_close_date"]
        assert row[4] == r["next_step"]


def test_on_time_rate_per_account_matches_truth(wh, truth):
    sql = dict(wh.execute("SELECT customer_id, on_time_rate_90d FROM marts.account_risk WHERE deliveries_90d > 0").fetchall())
    assert sql == {k: v["rate"] for k, v in truth["on_time_by_customer"].items()}


def test_net_revenue_by_region_and_quarter_matches_truth(wh, truth):
    rows = wh.execute("SELECT region, billing_quarter, sum(amount_usd) FROM marts.fct_revenue GROUP BY 1, 2").fetchall()
    sql = {f"{r}|{q}": float(v) for r, q, v in rows}
    assert sql.keys() == truth["net_revenue_usd"].keys()
    for k, v in truth["net_revenue_usd"].items():
        assert abs(sql[k] - v) < 0.01, k


def test_golden_numbers_from_the_marts(wh, truth):
    g = truth["golden"]
    assert wh.execute("SELECT count(*) FROM marts.dim_account WHERE is_strategic").fetchone()[0] == g["G4"]
    ok, n = wh.execute("SELECT count(*) FILTER (WHERE d.is_on_time), count(*) FROM marts.fct_delivery d "
                       "JOIN marts.dim_account a USING (customer_id) WHERE a.is_strategic AND d.is_in_90d_window").fetchone()
    assert round(100 * ok / n, 1) == g["G2"]
    assert round(float(wh.execute("SELECT sum(amount_usd) FROM marts.fct_revenue WHERE region='EMEA' AND billing_quarter='2026-Q3'")
                       .fetchone()[0])) == g["G3"]
    assert wh.execute("SELECT count(*) FROM marts.fct_ticket t JOIN marts.dim_account a USING (customer_id) "
                      "WHERE a.is_strategic AND t.is_open AND t.is_shipping_related").fetchone()[0] == g["G6"]


def test_tier_at_delivery_uses_history(wh, truth):
    rows = wh.execute("SELECT tier_at_delivery, avg(is_on_time::int) FROM marts.fct_delivery WHERE is_in_90d_window GROUP BY 1").fetchall()
    assert {t: round(v, 4) for t, v in rows} == truth["on_time_by_tier_at_delivery"]


def test_freshness_flags_zendesk_when_t6_is_on():
    if not config.T6_STALE_ZENDESK:
        pytest.skip("T6 flag is off")
    results = json.loads((TARGET / "sources.json").read_text())["results"]
    status = {r["unique_id"].split(".")[2]: r["status"] for r in results}
    assert status["zendesk"] == "error"
    assert status["sap_s4"] == "pass"


def test_lineage_reaches_every_mart_from_all_four_sources():
    manifest = json.loads((TARGET / "manifest.json").read_text())
    parents = manifest["parent_map"]

    def sources_of(node, seen=None):
        seen = seen or set()
        for p in parents.get(node, []):
            if p not in seen:
                seen.add(p)
                sources_of(p, seen)
        return {s.split(".")[2] for s in seen if s.startswith("source.")}

    assert sources_of("model.contextloop.account_risk") == {"sap_s4", "carrier_pg", "salesforce", "zendesk"}
    assert (TARGET / "catalog.json").exists()


# ---- builds against a throwaway copy of the warehouse ------------------------------------------------------------------

def _dbt_on_copy(tmp_path: Path, *args: str, project: Path | None = None) -> tuple[int, list[str]]:
    db = tmp_path / "wh.db"
    shutil.copyfile(config.SERVING_PATH, db)
    target = tmp_path / "target"
    proj = project or config.DBT_PROJECT_DIR
    env = os.environ | {"WAREHOUSE_PATH": str(db), "DBT_TARGET_PATH": str(target), "DBT_LOG_PATH": str(tmp_path / "logs"),
                        "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"}
    proc = subprocess.run(["dbt", "--no-use-colors", *args, "--project-dir", str(proj), "--profiles-dir", str(proj)],
                          env=env, capture_output=True, text=True, cwd=proj)
    results = json.loads((target / "run_results.json").read_text())["results"] if (target / "run_results.json").exists() else []
    failed = [r["unique_id"] for r in results if r["status"] in ("fail", "error")]
    return proc.returncode, failed


@pytest.mark.parametrize("trap,expected", [("T1", "no_deleted_rows"), ("T4", "assert_every_ticket_has_a_customer")])
def test_breaking_a_trap_fails_a_named_test(tmp_path, trap, expected):
    code, failed = _dbt_on_copy(tmp_path, "build", "--vars", json.dumps({"break_trap": trap}))
    assert code != 0
    assert any(expected in f for f in failed), failed


def test_contract_rejects_a_changed_column_type(tmp_path):
    proj = tmp_path / "proj"
    shutil.copytree(config.DBT_PROJECT_DIR, proj, ignore=shutil.ignore_patterns("target", "logs"))
    sql = proj / "models" / "marts" / "account_risk.sql"
    changed = re.sub(r"deliveries_90d::integer(\s+)as deliveries_90d", r"deliveries_90d::varchar\1as deliveries_90d", sql.read_text(), count=1)
    assert changed != sql.read_text()
    sql.write_text(changed)
    code, failed = _dbt_on_copy(tmp_path, "run", "--select", "account_risk", project=proj)
    assert code != 0 and any("account_risk" in f for f in failed)

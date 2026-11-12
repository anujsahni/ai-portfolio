"""CL-04 and CL-05: the Connector SDK connectors, the SaaS landings and the sync log. Runs inside the image after `make data`."""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pytest

from contextloop import config

SDK = Path("/opt/fivetran/bin/fivetran")
pytestmark = pytest.mark.skipif(not (SDK.exists() and (config.SAP_DIR / "batch=1").exists()),
                                reason="needs the contextloop image and `make data`")
ROOT = Path(__file__).resolve().parents[1]


def _debug(project: Path, configuration: dict) -> subprocess.CompletedProcess:
    cfg = project / "cfg.json"
    cfg.write_text(json.dumps(configuration))
    env = os.environ | {"PATH": f"/opt/fivetran/bin:{os.environ['PATH']}", "DO_NOT_TRACK": "1"}
    return subprocess.run([str(SDK), "debug", str(project), "--configuration", str(cfg), "--non-interactive"],
                          cwd=project, env=env, capture_output=True, text=True, timeout=600)


def _project(tmp: Path, name: str) -> Path:
    p = tmp / name
    p.mkdir()
    for f in ("connector.py", "requirements.txt"):
        shutil.copy2(ROOT / "connectors" / name.split("-")[0] / f, p / f)
    return p


def _snapshot(db: Path) -> dict[str, list]:
    con = duckdb.connect(str(db), read_only=True)
    try:
        out = {}
        for (t,) in con.execute("SELECT table_name FROM duckdb_tables() WHERE schema_name='tester' ORDER BY 1").fetchall():
            cols = [c for (c,) in con.execute(f"SELECT column_name FROM information_schema.columns WHERE table_schema='tester' "
                                              f"AND table_name='{t}' AND column_name <> '_fivetran_synced' ORDER BY ordinal_position").fetchall()]
            out[t] = con.execute(f"SELECT {', '.join(cols)} FROM tester.{t} ORDER BY ALL").fetchall()
        return out
    finally:
        con.close()


def test_sap_interrupted_sync_resumes_to_the_same_state(tmp_path):
    src = {"source_dir": str(config.SAP_DIR)}
    clean = _project(tmp_path, "sap_s4")
    assert _debug(clean, src).returncode == 0
    broken = _project(tmp_path, "sap_s4-broken")
    first = _debug(broken, src | {"simulate_failure_after_checkpoints": "6"})
    assert first.returncode != 0 and "Simulated failure" in first.stdout + first.stderr
    state = json.loads((broken / "files" / "state.json").read_text())
    assert state["cursors"], "progress before the failure was checkpointed"
    assert _debug(broken, src).returncode == 0
    assert _snapshot(clean / "files" / "warehouse.db") == _snapshot(broken / "files" / "warehouse.db")


def test_sap_second_run_with_no_new_data_changes_nothing(tmp_path):
    p = _project(tmp_path, "sap_s4")
    _debug(p, {"source_dir": str(config.SAP_DIR)})
    second = _debug(p, {"source_dir": str(config.SAP_DIR)})
    assert second.returncode == 0
    assert "Upserts         | 0" in second.stdout + second.stderr


def test_connector_code_has_docstrings_and_no_secrets():
    for name in ("sap_s4", "carrier_pg"):
        tree = ast.parse((ROOT / "connectors" / name / "connector.py").read_text())
        assert ast.get_docstring(tree)
        for fn in (n for n in tree.body if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")):
            assert ast.get_docstring(fn), f"{name}.{fn.name} lacks a docstring"
        cfg = json.loads((ROOT / "connectors" / name / "configuration.json").read_text())
        assert not any("demo" in str(v) or "secret" in str(v).lower() and "never" not in str(v) for v in cfg.values())


@pytest.fixture(scope="module")
def wh():
    if not config.SERVING_PATH.exists():
        pytest.skip("run `make sync` first")
    con = duckdb.connect(str(config.SERVING_PATH), read_only=True)
    yield con
    con.close()


def test_all_four_sources_land_with_fivetran_columns(wh):
    for schema in ("sap_s4", "carrier_pg", "salesforce", "zendesk"):
        tables = [t for (t,) in wh.execute("SELECT table_name FROM duckdb_tables() WHERE schema_name=?", [schema]).fetchall()]
        assert tables, schema
        for t in tables:
            cols = {c for (c,) in wh.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=? AND table_name=?",
                                             [schema, t]).fetchall()}
            assert {"_fivetran_synced", "_fivetran_deleted"} <= cols, f"{schema}.{t}"


def test_deleted_rows_are_flagged_not_removed(wh):
    traps = json.loads((config.TRUTH_DIR / "traps.json").read_text())
    deleted = {v for (v,) in wh.execute("SELECT vbeln FROM sap_s4.likp WHERE _fivetran_deleted").fetchall()}
    assert deleted == set(traps["T1"]["deliveries"])


def test_history_mode_on_salesforce_account(wh):
    active = wh.execute("SELECT id, count(*) FILTER (WHERE _fivetran_active) FROM salesforce.account GROUP BY 1").fetchall()
    assert all(n == 1 for _, n in active)
    traps = json.loads((config.TRUTH_DIR / "traps.json").read_text())
    for a in traps["T5"]["accounts"]:
        rows = wh.execute("SELECT tier_c, _fivetran_active, _fivetran_start, _fivetran_end FROM salesforce.account WHERE id=? "
                          "ORDER BY _fivetran_start", [a["sf_account_id"]]).fetchall()
        assert [r[0] for r in rows] == [a["from"], a["to"]]
        assert rows[0][3] < rows[1][2] and not rows[0][1] and rows[1][1]


def test_sync_log_and_mar(wh):
    per = dict(wh.execute("SELECT connection_id, count(*) FROM fivetran_log.sync_log GROUP BY 1").fetchall())
    assert set(per) == {"sap_s4", "carrier_pg", "salesforce", "zendesk"}
    mar = wh.execute("SELECT count(DISTINCT connection_id), min(incremental_rows) FROM fivetran_log.incremental_mar").fetchone()
    assert mar[0] == 4 and mar[1] > 0


def test_t6_flag_holds_zendesk_two_days_behind(tmp_path):
    from contextloop.datagen.world import STALE_CUTOFF
    from contextloop.landing import saas

    now = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
    for stale in (True, False):
        con = duckdb.connect(str(tmp_path / f"z{stale}.db"))
        _, synced = saas.land_zendesk(con, now, stale, STALE_CUTOFF)
        latest = con.execute("SELECT max(updated_at), max(_fivetran_synced) FROM zendesk.ticket").fetchone()
        if stale:
            assert (now - synced).days == 2
            assert latest[0] <= STALE_CUTOFF.replace(tzinfo=timezone.utc)
        else:
            assert synced == now and latest[0] > STALE_CUTOFF.replace(tzinfo=timezone.utc)
        con.close()


def test_postgres_change_lands_only_that_row(tmp_path):
    import psycopg

    cfg = {"host": os.environ["PGHOST"], "port": "5432", "database": "carrier", "user": "carrier", "password": os.environ["PGPASSWORD"]}
    p = _project(tmp_path, "carrier_pg")
    assert _debug(p, cfg).returncode == 0
    with psycopg.connect(config.pg_dsn(), autocommit=True) as conn:
        sid = conn.execute("SELECT max(shipment_id) FROM tracking.shipment").fetchone()[0]
        conn.execute("UPDATE tracking.shipment SET tracking_number = tracking_number, updated_at = now() WHERE shipment_id = %s", [sid])
    second = _debug(p, cfg)
    assert "SYNC_RECORD table=shipment inserted=0 updated=1 deleted=0" in second.stdout + second.stderr
    assert "SYNC_RECORD table=shipment_event inserted=0 updated=0 deleted=0" in second.stdout + second.stderr

"""Runs a Connector SDK connector with Fivetran's own local runner (`fivetran debug`) and publishes what it landed.

`fivetran debug` writes to the connector project's own `files/warehouse.db` and keeps its cursor in `files/state.json`. Each
connector's project lives on the warehouse volume (`/warehouse/connectors/<name>/`), so state survives between syncs. After a
successful run, its tables are copied into the shared warehouse under the connector's schema (`sap_s4`, `carrier_pg`).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from contextloop.config import ROOT, WAREHOUSE_PATH

SDK_BIN = Path("/opt/fivetran/bin")
RECORD = re.compile(r"SYNC_RECORD table=(\w+) inserted=(\d+) updated=(\d+) deleted=(\d+)")
# Tables keep Fivetran's naming, which separates letters from digits (KNA1 -> kna_1, NAME1 -> name_1).


@dataclass
class SyncResult:
    connection: str
    schema: str
    started: datetime
    finished: datetime
    status: str
    tables: dict[str, dict[str, int]] = field(default_factory=dict)
    message: str = ""
    output: str = ""

    @property
    def totals(self) -> dict[str, int]:
        return {k: sum(t[k] for t in self.tables.values()) for k in ("inserted", "updated", "deleted")}


def project_dir(name: str) -> Path:
    return WAREHOUSE_PATH.parent / "connectors" / name


def run_connector(name: str, schema: str, configuration: dict, warehouse: Path | None = None) -> SyncResult:
    proj = project_dir(name)
    proj.mkdir(parents=True, exist_ok=True)
    for f in ("connector.py", "requirements.txt"):
        shutil.copy2(ROOT / "connectors" / name / f, proj / f)
    cfg_path = proj / "runtime-configuration.json"  # on the volume only; never committed (may hold a password)
    cfg_path.write_text(json.dumps(configuration))
    env = os.environ | {"PATH": f"{SDK_BIN}:{os.environ.get('PATH', '')}", "DO_NOT_TRACK": "1"}
    started = datetime.now(timezone.utc)
    proc = subprocess.run([str(SDK_BIN / "fivetran"), "debug", str(proj), "--configuration", str(cfg_path), "--non-interactive"],
                          cwd=proj, env=env, capture_output=True, text=True, timeout=900)
    finished = datetime.now(timezone.utc)
    out = proc.stdout + proc.stderr
    tables = {m[0].lower(): {"inserted": int(m[1]), "updated": int(m[2]), "deleted": int(m[3])} for m in RECORD.findall(out)}
    ok = proc.returncode == 0 and "SYNC SUCCEEDED" in out
    result = SyncResult(name, schema, started, finished, "SUCCESSFUL" if ok else "FAILURE", tables,
                        "" if ok else _error_line(out), out)
    if ok:
        publish(proj / "files" / "warehouse.db", schema, warehouse or WAREHOUSE_PATH)
    return result


def _error_line(out: str) -> str:
    for line in reversed(out.splitlines()):
        if "Error" in line or "error" in line:
            return line.strip()[:300]
    return "sync failed"


def publish(source_db: Path, schema: str, warehouse: Path) -> None:
    """Copies the connector's landed tables into the shared warehouse, replacing the previous copy."""
    con = duckdb.connect(str(warehouse))
    try:
        con.execute(f"ATTACH '{source_db}' AS src (READ_ONLY)")
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        tables = [r[0] for r in con.execute(
            "SELECT table_name FROM duckdb_tables() WHERE database_name = 'src' AND schema_name = 'tester'").fetchall()]
        con.execute("BEGIN")
        for t in tables:
            con.execute(f"CREATE OR REPLACE TABLE {schema}.{t} AS SELECT * FROM src.tester.{t}")
        stale = [r[0] for r in con.execute("SELECT table_name FROM duckdb_tables() WHERE database_name = current_database() "
                                           "AND schema_name = ?", [schema]).fetchall() if r[0] not in tables]
        for t in stale:  # tables the connector no longer lands
            con.execute(f"DROP TABLE {schema}.{t}")
        con.execute("COMMIT")
        con.execute("DETACH src")
    finally:
        con.close()


def state(name: str) -> dict:
    p = project_dir(name) / "files" / "state.json"
    return json.loads(p.read_text()) if p.exists() else {}

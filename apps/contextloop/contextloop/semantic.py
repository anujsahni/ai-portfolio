"""Semantic layer helpers (CL-07): validate the MetricFlow configs and run metric queries with the `mf` CLI.

The metric definitions live in dbt/contextloop/models/semantic/semantic_models.yml; nothing here redefines a metric.
"""
from __future__ import annotations

import csv
import os
import subprocess
import tempfile
from pathlib import Path

from contextloop import config

MF_ENV = {"DBT_SEND_ANONYMOUS_USAGE_STATS": "false", "DO_NOT_TRACK": "1"}


def _mf(*args: str, warehouse: Path | None = None) -> subprocess.CompletedProcess:
    env = os.environ | MF_ENV
    if warehouse:
        env["WAREHOUSE_PATH"] = str(warehouse)
    return subprocess.run(["mf", *args], cwd=config.DBT_PROJECT_DIR, env=env, capture_output=True, text=True, timeout=300)


def validate() -> None:
    proc = _mf("validate-configs", "--skip-dw")
    ok = proc.returncode == 0 and "ERRORS: 0" in proc.stdout
    print("Semantic layer: mf validate-configs " + ("passed" if ok else "FAILED"))
    if not ok:
        print(proc.stdout[-3000:], proc.stderr[-2000:])
        raise SystemExit("✗ semantic layer validation failed")


def query(metrics: list[str] | None = None, group_by: list[str] | None = None, where: str | None = None,
          order: list[str] | None = None, saved_query: str | None = None, warehouse: Path | None = None) -> list[dict]:
    """Runs a MetricFlow query and returns rows as dicts (values as text, as MetricFlow writes them)."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "result.csv"
        args = ["query"]
        if saved_query:
            args += ["--saved-query", saved_query]
        if metrics:
            args += ["--metrics", ",".join(metrics)]
        if group_by:
            args += ["--group-by", ",".join(group_by)]
        if where:
            args += ["--where", where]
        if order:
            args += ["--order", ",".join(order)]
        args += ["--csv", str(out)]
        proc = _mf(*args, warehouse=warehouse)
        if proc.returncode != 0 or not out.exists():
            raise RuntimeError(f"mf query failed: {proc.stdout[-2000:]} {proc.stderr[-1000:]}")
        with out.open(newline="") as f:
            return list(csv.DictReader(f))


def explain(metrics: list[str], group_by: list[str] | None = None, where: str | None = None) -> str:
    """The SQL MetricFlow compiles for a query (shown in the app so the audience sees the governed SQL)."""
    args = ["query", "--metrics", ",".join(metrics), "--explain"]
    if group_by:
        args += ["--group-by", ",".join(group_by)]
    if where:
        args += ["--where", where]
    proc = _mf(*args)
    return proc.stdout

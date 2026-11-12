"""Metrics MCP server: governed metric queries over the dbt semantic layer (MetricFlow), on the private network.

Tools
  list_metrics   every metric with its business definition, plus the dimensions you can group or filter by
  query_metric   one or more metrics, grouped and filtered; MetricFlow compiles the governed SQL, which runs read-only
                 against the serving copy of the warehouse. The result includes the SQL, so every number is traceable.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

import duckdb

from contextloop.config import DBT_PROJECT_DIR, SERVING_PATH
from contextloop.mcp_servers.common import make_server

PORT = 8101
MAX_ROWS = 200
TARGET = Path(os.environ.get("DBT_TARGET_PATH", DBT_PROJECT_DIR / "target"))

server = make_server("contextloop-metrics", PORT, (
    "Governed Northstar metrics from the dbt semantic layer. Call list_metrics first to read the definitions and dimensions, "
    "then query_metric. Every number you report should come from a query_metric result."))


@lru_cache(maxsize=4)
def _manifest(mtime: float) -> dict:
    return json.loads((TARGET / "semantic_manifest.json").read_text())


def manifest() -> dict:
    path = TARGET / "semantic_manifest.json"
    return _manifest(path.stat().st_mtime)


def catalog() -> dict:
    """Metrics with definitions, and the dimensions available, from the compiled semantic manifest."""
    m = manifest()
    metrics = [{"name": x["name"], "label": x.get("label"), "type": x["type"],
                "definition": " ".join((x.get("description") or "").split())} for x in m["metrics"]]
    dims = []
    for sm in m["semantic_models"]:
        primary = next((e["name"] for e in sm["entities"] if e["type"] == "primary"), None)
        for d in sm.get("dimensions", []):
            name = f"{primary}__{d['name']}"
            if d["type"] == "time":
                name += " (time; add __day, __month or __quarter)"
            dims.append({"name": name, "description": " ".join((d.get("description") or "").split()) or None})
        dims += [{"name": e["name"], "description": f"entity: {sm['name']}"} for e in sm["entities"] if e["type"] == "primary"]
    seen, unique = set(), []
    for d in dims:
        if d["name"] not in seen:
            seen.add(d["name"])
            unique.append(d)
    return {"metrics": metrics, "dimensions": unique,
            "filter_syntax": "{{ Dimension('account__is_strategic') }} = true   |   {{ Dimension('account__region') }} = 'EMEA'   |   "
                             "{{ Dimension('billing_document__billing_quarter') }} = '2026-Q3'",
            "notes": ["Group by the entity `account` to get one row per customer, and `account__account_name` for its name.",
                      "`account__tier` is today's tier; `delivery__tier_at_delivery` is the tier in force on each delivery's date.",
                      "Delivery metrics already cover the 90 days ending on the as-of date (6 Nov 2026)."]}


def compile_sql(metrics: list[str], group_by: list[str], where: str | None, order_by: list[str], limit: int) -> str:
    args = ["mf", "query", "--metrics", ",".join(metrics), "--explain"]
    if group_by:
        args += ["--group-by", ",".join(group_by)]
    if where:
        args += ["--where", where]
    if order_by:
        args += ["--order", ",".join(order_by)]
    args += ["--limit", str(limit)]
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ | {"WAREHOUSE_PATH": str(Path(tmp) / "compile-only.db"), "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"}
        proc = subprocess.run(args, cwd=DBT_PROJECT_DIR, env=env, capture_output=True, text=True, timeout=120)
    out = proc.stdout.replace("\r", "\n")
    if proc.returncode != 0 or "SELECT" not in out:
        detail = "\n".join(ln for ln in out.splitlines() if ln.strip() and "⠋" not in ln and "⠙" not in ln)[-1500:]
        raise ValueError(f"MetricFlow could not compile this query: {detail}")
    lines = out.splitlines()
    header = next(i for i, ln in enumerate(lines) if "SQL (remove --explain" in ln)
    return "\n".join(lines[header + 1:]).strip()


def run_sql(sql: str) -> tuple[list[str], list[list]]:
    con = duckdb.connect()
    try:
        con.execute(f"ATTACH '{SERVING_PATH}' AS warehouse (READ_ONLY)")
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(MAX_ROWS)
    finally:
        con.close()

    def clean(v):
        if isinstance(v, float):
            return round(v, 6)
        if v is None or isinstance(v, (int, str, bool)):
            return v
        return str(v)
    return cols, [[clean(v) for v in r] for r in rows]


@server.tool()
def list_metrics() -> dict:
    """List every governed metric with its business definition, and every dimension you can group by or filter on."""
    return catalog()


@server.tool()
def query_metric(metrics: list[str], group_by: list[str] | None = None, where: str | None = None,
                 order_by: list[str] | None = None, limit: int = 100) -> dict:
    """Query governed metrics. `metrics`: names from list_metrics. `group_by`: dimensions or entities, e.g. ["account",
    "account__account_name"]. `where`: a MetricFlow filter, e.g. "{{ Dimension('account__is_strategic') }} = true".
    `order_by`: e.g. ["on_time_delivery_rate"] or ["-net_revenue"] for descending. Returns columns, rows and the compiled SQL."""
    known = {m["name"] for m in manifest()["metrics"]}
    unknown = [m for m in metrics if m not in known]
    if unknown:
        return {"error": f"Unknown metric(s): {unknown}. Call list_metrics for the names."}
    limit = max(1, min(int(limit or 100), MAX_ROWS))
    try:
        sql = compile_sql(metrics, group_by or [], where, order_by or [], limit)
        cols, rows = run_sql(sql)
    except (ValueError, duckdb.Error, subprocess.TimeoutExpired) as exc:
        return {"error": str(exc)}
    definitions = {m["name"]: m["definition"] for m in catalog()["metrics"] if m["name"] in metrics}
    return {"metrics": metrics, "group_by": group_by or [], "where": where, "columns": cols, "rows": rows,
            "row_count": len(rows), "definitions": definitions, "compiled_sql": re.sub(r"\n{2,}", "\n", sql)}


if __name__ == "__main__":
    server.run(transport="streamable-http")

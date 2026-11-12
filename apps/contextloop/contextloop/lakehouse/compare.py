"""`make lakehouse`: the same question (the at-risk list) against the same Iceberg table, through two engines.

  DuckDB  reads the Iceberg table through the REST catalog (iceberg extension) and the S3-compatible store (httpfs)
  Trino   reads it through its Iceberg connector, configured against the same catalog and store (docker/trino)
"""
from __future__ import annotations

import time
from decimal import Decimal

import duckdb
import httpx

from contextloop.config import ICEBERG_CATALOG_URI, LAKE_BUCKET, s3_settings
from contextloop.lakehouse.publish import location

QUESTION = ("SELECT customer_id, account_name, round(on_time_rate_90d, 4) AS on_time_rate_90d, open_shipping_tickets, renewal_close_date "
            "FROM {table} WHERE is_at_risk ORDER BY customer_id")
TRINO_URL = "http://trino:8080"


def duckdb_connection() -> duckdb.DuckDBPyConnection:
    s = s3_settings()
    con = duckdb.connect()
    con.execute("LOAD httpfs; LOAD iceberg;")
    endpoint = s["endpoint"].removeprefix("http://").removeprefix("https://")
    con.execute(f"""CREATE SECRET lake (TYPE s3, KEY_ID '{s['access_key']}', SECRET '{s['secret_key']}', REGION '{s['region']}',
                    ENDPOINT '{endpoint}', URL_STYLE 'path', USE_SSL false)""")
    con.execute(f"ATTACH '{LAKE_BUCKET}' AS lake (TYPE iceberg, ENDPOINT '{ICEBERG_CATALOG_URI}', AUTHORIZATION_TYPE 'none')")
    return con


def via_duckdb() -> list[tuple]:
    con = duckdb_connection()
    try:
        return [tuple(r) for r in con.execute(QUESTION.format(table='lake."northstar.marts".account_risk')).fetchall()]
    finally:
        con.close()


def via_trino(sql: str | None = None, timeout: float = 120) -> list[tuple]:
    sql = sql or QUESTION.format(table='iceberg."northstar.marts".account_risk')
    headers = {"X-Trino-User": "contextloop", "X-Trino-Source": "contextloop-compare"}
    rows: list[tuple] = []
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{TRINO_URL}/v1/statement", content=sql, headers=headers).json()
        deadline = time.monotonic() + timeout
        while True:
            if "error" in r:
                raise RuntimeError(r["error"].get("message"))
            rows += [tuple(x) for x in r.get("data", [])]
            if "nextUri" not in r:
                break
            if time.monotonic() > deadline:
                raise TimeoutError("Trino query timed out")
            r = client.get(r["nextUri"], headers=headers).json()
    return rows


def _norm(rows: list[tuple]) -> list[tuple]:
    def v(x):
        if isinstance(x, (float, Decimal)):
            return round(float(x), 4)
        return str(x) if x is not None and not isinstance(x, (int, str)) else x
    return [tuple(v(x) for x in r) for r in rows]


def run() -> int:
    loc = location()
    d = _norm(via_duckdb())
    t = _norm(via_trino())
    print(f"Iceberg table northstar.marts.account_risk · snapshot {loc['snapshot_id']}\n  {loc['location']}")
    print(f"DuckDB: {len(d)} at-risk accounts · Trino: {len(t)} at-risk accounts")
    for row in d:
        print("  ", row[1], f"{row[2]:.1%}")
    same = d == t
    print("✓ Both engines return identical results" if same else "✗ The engines disagree")
    return 0 if same else 1

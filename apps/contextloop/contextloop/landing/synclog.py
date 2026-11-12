"""The sync log (`fivetran_log` schema), modelled on the shape of Fivetran's Platform Connector.

  connection       one row per connection (what it is, where it lands, whether it is simulated)
  sync_log         one row per sync per connection: start, end, status, rows inserted/updated/deleted, per-table counts
  incremental_mar  an ESTIMATE of monthly active rows: distinct primary keys changed per table per calendar month,
                   measured from the source's change timestamps (not Fivetran's billing rules)
"""
from __future__ import annotations

import csv
import glob
import json
from collections import defaultdict
from datetime import datetime

import duckdb

from contextloop.config import SAAS_DIR, SAP_DIR
from contextloop.landing.sdk import SyncResult

CONNECTIONS = [
    ("sap_s4", "SAP S/4HANA (Connector SDK)", "connector_sdk", "sap_s4", False),
    ("carrier_pg", "Carrier tracking Postgres (Connector SDK)", "connector_sdk", "carrier_pg", False),
    ("salesforce", "Salesforce (simulated landing)", "salesforce", "salesforce", True),
    ("zendesk", "Zendesk (simulated landing)", "zendesk", "zendesk", True),
]

DDL = """
CREATE SCHEMA IF NOT EXISTS fivetran_log;
CREATE TABLE IF NOT EXISTS fivetran_log.connection (
    connection_id VARCHAR PRIMARY KEY, connection_name VARCHAR, connector_type VARCHAR, destination_schema VARCHAR,
    is_simulated BOOLEAN);
CREATE TABLE IF NOT EXISTS fivetran_log.sync_log (
    sync_id VARCHAR PRIMARY KEY, connection_id VARCHAR, sync_start TIMESTAMPTZ, sync_end TIMESTAMPTZ, status VARCHAR,
    message VARCHAR, rows_inserted BIGINT, rows_updated BIGINT, rows_deleted BIGINT, table_counts VARCHAR);
"""


def ensure(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(DDL)
    for row in CONNECTIONS:
        con.execute("INSERT OR REPLACE INTO fivetran_log.connection VALUES (?, ?, ?, ?, ?)", list(row))


def record(con: duckdb.DuckDBPyConnection, r: SyncResult) -> None:
    t = r.totals
    sync_id = f"{r.connection}-{r.started.strftime('%Y%m%dT%H%M%S%f')}"
    con.execute("INSERT INTO fivetran_log.sync_log VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [sync_id, r.connection, r.started, r.finished, r.status, r.message or None, t["inserted"], t["updated"], t["deleted"],
                 json.dumps(r.tables, sort_keys=True)])


def mar_estimate(con: duckdb.DuckDBPyConnection) -> None:
    """Rebuilds fivetran_log.incremental_mar from source change timestamps."""
    keys: dict[tuple[str, str, str], set] = defaultdict(set)
    sap_keys = {"KNA1": 2, "VBAK": 2, "VBAP": 3, "LIKP": 2, "LIPS": 3, "VBRK": 2, "VBRP": 3, "TCURR": 5}
    for path in sorted(glob.glob(str(SAP_DIR / "batch=*" / "*.csv"))):
        table = path.rsplit("/", 1)[1][:-4]
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            ia = header.index("AEDAT")
            for row in reader:
                keys[("sap_s4", table.lower(), f"{row[ia][:4]}-{row[ia][4:6]}")].add(tuple(row[: sap_keys[table]]))
    for t in ("shipment", "shipment_event"):
        for (k, upd) in con.execute(f"SELECT {'shipment_id' if t == 'shipment' else 'event_id'}, strftime(updated_at, '%Y-%m') "
                                    f"FROM carrier_pg.{t}").fetchall():
            keys[("carrier_pg", t, upd)].add(k)
    saas = {"salesforce/account_history": ("salesforce", "account", "id", "last_modified_date"),
            "salesforce/opportunity": ("salesforce", "opportunity", "id", "last_modified_date"),
            "zendesk/ticket": ("zendesk", "ticket", "id", "updated_at"),
            "zendesk/organization": ("zendesk", "organization", "id", "created_at")}
    for name, (conn, table, pk, col) in saas.items():
        with open(SAAS_DIR / f"{name}.csv", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                keys[(conn, table, row[col][:7])].add(row[pk])
    rows = [(c, t, f"{m}-01", len(v)) for (c, t, m), v in sorted(keys.items()) if m]
    con.execute("CREATE OR REPLACE TABLE fivetran_log.incremental_mar (connection_id VARCHAR, table_name VARCHAR, "
                "measured_month DATE, incremental_rows BIGINT)")
    con.executemany("INSERT INTO fivetran_log.incremental_mar VALUES (?, ?, ?, ?)", rows)


def last_success(con: duckdb.DuckDBPyConnection, connection: str) -> datetime | None:
    row = con.execute("SELECT max(sync_end) FROM fivetran_log.sync_log WHERE connection_id = ? AND status = 'SUCCESSFUL'",
                      [connection]).fetchone()
    return row[0] if row else None

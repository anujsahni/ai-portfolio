"""Simulated Fivetran landings for Salesforce and Zendesk (the demo has no real SaaS accounts).

The tables match the layout Fivetran's Salesforce and Zendesk connectors produce: lower-case names, custom fields with a `_c`
suffix, `_fivetran_synced` and `_fivetran_deleted` on every row, and history mode on `salesforce.account` (`_fivetran_start`,
`_fivetran_end`, `_fivetran_active`). Each sync is incremental in effect: only new or changed rows get a new
`_fivetran_synced`, and rows that disappear are soft-deleted.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pyarrow as pa

from contextloop.config import SAAS_DIR

# table -> (csv file, primary key, {column: SQL type}) ; unlisted columns are text
SPECS = {
    "salesforce.account": ("salesforce/account_history", ["id", "_fivetran_start"], {
        "is_deleted": "BOOLEAN", "created_date": "TIMESTAMPTZ", "last_modified_date": "TIMESTAMPTZ",
        "_fivetran_start": "TIMESTAMPTZ", "_fivetran_end": "TIMESTAMPTZ", "_fivetran_active": "BOOLEAN"}),
    "salesforce.opportunity": ("salesforce/opportunity", ["id"], {
        "close_date": "DATE", "amount": "DOUBLE", "is_closed": "BOOLEAN", "is_won": "BOOLEAN", "is_deleted": "BOOLEAN",
        "created_date": "TIMESTAMPTZ", "last_modified_date": "TIMESTAMPTZ"}),
    "salesforce.user": ("salesforce/user", ["id"], {"is_active": "BOOLEAN"}),
    "zendesk.organization": ("zendesk/organization", ["id"], {"id": "BIGINT", "created_at": "TIMESTAMPTZ"}),
    "zendesk.ticket": ("zendesk/ticket", ["id"], {
        "id": "BIGINT", "created_at": "TIMESTAMPTZ", "updated_at": "TIMESTAMPTZ", "organization_id": "BIGINT", "requester_id": "BIGINT"}),
    "zendesk.ticket_tag": ("zendesk/ticket_tag", ["ticket_id", "tag"], {"ticket_id": "BIGINT"}),
}


def read_rows(name: str) -> list[dict]:
    with open(SAAS_DIR / f"{name}.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if name == "salesforce/account_history":  # history mode columns
        for r in rows:
            r["_fivetran_start"] = r.pop("valid_from")
            r["_fivetran_end"] = r.pop("valid_to")
            r["_fivetran_active"] = "true" if r["_fivetran_end"].startswith("9999") else "false"
    return rows


def land(con: duckdb.DuckDBPyConnection, table: str, rows: list[dict], synced_at: datetime, detect_deletes: bool = True) -> dict[str, int]:
    """Upserts `rows` into `table` Fivetran-style and returns inserted/updated/deleted counts."""
    _, pk, types = SPECS[table]
    schema = table.split(".")[0]
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    cols = list(rows[0].keys()) if rows else []
    arrow = pa.table({c: [r[c] if r[c] != "" else None for r in rows] for c in cols})
    con.register("incoming_raw", arrow)
    select = ", ".join(f"CAST(\"{c}\" AS {types.get(c, 'VARCHAR')}) AS \"{c}\"" for c in cols)
    con.execute(f"CREATE OR REPLACE TEMP TABLE incoming AS SELECT {select} FROM incoming_raw")
    con.unregister("incoming_raw")
    key = " AND ".join(f't."{k}" IS NOT DISTINCT FROM i."{k}"' for k in pk)
    exists = con.execute("SELECT count(*) FROM duckdb_tables() WHERE schema_name = ? AND table_name = ?",
                         table.split(".")).fetchone()[0]
    ts = synced_at.isoformat()
    if not exists:
        con.execute(f"CREATE TABLE {table} AS SELECT *, '{ts}'::TIMESTAMPTZ AS _fivetran_synced, false AS _fivetran_deleted FROM incoming")
        return {"inserted": len(rows), "updated": 0, "deleted": 0}
    data_cols = ", ".join(f'"{c}"' for c in cols)
    changed = f"""SELECT i.* FROM incoming i JOIN {table} t ON {key}
                  WHERE t._fivetran_deleted OR ({', '.join(f't."{c}"' for c in cols)}) IS DISTINCT FROM ({', '.join(f'i."{c}"' for c in cols)})"""
    new = f"SELECT i.* FROM incoming i WHERE NOT EXISTS (SELECT 1 FROM {table} t WHERE {key})"
    n_upd = con.execute(f"SELECT count(*) FROM ({changed})").fetchone()[0]
    n_new = con.execute(f"SELECT count(*) FROM ({new})").fetchone()[0]
    n_del = 0
    con.execute(f"CREATE OR REPLACE TEMP TABLE upd AS {changed}")
    con.execute(f"DELETE FROM {table} t WHERE EXISTS (SELECT 1 FROM upd i WHERE {key})")
    con.execute(f"INSERT INTO {table} ({data_cols}, _fivetran_synced, _fivetran_deleted) "
                f"SELECT {data_cols}, '{ts}'::TIMESTAMPTZ, false FROM upd UNION ALL SELECT {data_cols}, '{ts}'::TIMESTAMPTZ, false FROM ({new})")
    if detect_deletes:
        gone = f"NOT t._fivetran_deleted AND NOT EXISTS (SELECT 1 FROM incoming i WHERE {key})"
        n_del = con.execute(f"SELECT count(*) FROM {table} t WHERE {gone}").fetchone()[0]
        con.execute(f"UPDATE {table} t SET _fivetran_deleted = true, _fivetran_synced = '{ts}'::TIMESTAMPTZ WHERE {gone}")
    return {"inserted": n_new, "updated": n_upd, "deleted": n_del}


def land_salesforce(con, now: datetime) -> dict[str, dict[str, int]]:
    return {t.split(".")[1]: land(con, t, read_rows(SPECS[t][0]), now) for t in SPECS if t.startswith("salesforce.")}


def land_zendesk(con, now: datetime, stale: bool, cutoff: datetime) -> tuple[dict[str, dict[str, int]], datetime]:
    """With the T6 flag on, Zendesk's last successful sync is two days old: rows changed after the cutoff are not landed yet."""
    synced = now - timedelta(days=2) if stale else now
    tickets = read_rows("zendesk/ticket")
    tags = read_rows("zendesk/ticket_tag")
    if stale:
        iso = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
        tickets = [t for t in tickets if t["updated_at"] <= iso]
        keep = {t["id"] for t in tickets}
        tags = [t for t in tags if t["ticket_id"] in keep]
    counts = {
        "organization": land(con, "zendesk.organization", read_rows("zendesk/organization"), synced),
        "ticket": land(con, "zendesk.ticket", tickets, synced, detect_deletes=not stale),
        "ticket_tag": land(con, "zendesk.ticket_tag", tags, synced, detect_deletes=not stale),
    }
    return counts, synced


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


__all__ = ["land", "land_salesforce", "land_zendesk", "utcnow", "Path"]

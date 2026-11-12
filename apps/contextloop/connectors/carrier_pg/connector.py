"""Carrier tracking connector for the ContextLoop demo, built with the Fivetran Connector SDK.

Reads the carrier tracking database (a real Postgres container) incrementally, using `updated_at` as the cursor, and lands
`shipment` and `shipment_event`. This is the database-source counterpart to the SAP connector: the actual delivery time that
an on-time metric needs lives only here.

The database password is not in configuration.json: the sync job supplies it at run time from the environment. In production,
Fivetran's PostgreSQL connector (log-based change data capture) does this job.
"""
from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

from fivetran_connector_sdk import Connector
from fivetran_connector_sdk import Logging as log
from fivetran_connector_sdk import Operations as op

TABLES = {
    "shipment": {
        "key": "shipment_id", "created": "created_at",
        "columns": {"shipment_id": "LONG", "delivery_number": "STRING", "carrier_code": "STRING", "tracking_number": "STRING",
                    "status": "STRING", "created_at": "UTC_DATETIME", "updated_at": "UTC_DATETIME"},
    },
    "shipment_event": {
        "key": "event_id", "created": "event_at",
        "columns": {"event_id": "LONG", "shipment_id": "LONG", "event_type": "STRING", "event_at": "UTC_DATETIME",
                    "location": "STRING", "updated_at": "UTC_DATETIME"},
    },
}
PAGE = 5000
EPOCH = "1970-01-01T00:00:00+00:00"


def schema(configuration: dict) -> list[dict]:
    """Declares both tracking tables with their primary keys and column types."""
    return [{"table": t, "primary_key": [spec["key"]], "columns": spec["columns"]} for t, spec in TABLES.items()]


def _iso(value) -> str:
    return value.isoformat()


def update(configuration: dict, state: dict):
    """Pages through rows changed after each table's (updated_at, key) cursor, oldest first."""
    dsn = (f"host={configuration['host']} port={configuration.get('port', '5432')} dbname={configuration['database']} "
           f"user={configuration['user']} password={configuration['password']}")
    cursors = dict(state.get("cursors", {}))
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        for table, spec in TABLES.items():
            key, created_col = spec["key"], spec["created"]
            start = cursors.get(table, {"updated_at": EPOCH, "key": 0})
            since = start["updated_at"]
            inserted = updated = 0
            while True:
                c = cursors.get(table, {"updated_at": EPOCH, "key": 0})
                rows = conn.execute(
                    f"SELECT * FROM tracking.{table} WHERE (updated_at, {key}) > (%s::timestamptz, %s) "
                    f"ORDER BY updated_at, {key} LIMIT {PAGE}", (c["updated_at"], c["key"])).fetchall()
                if not rows:
                    break
                for r in rows:
                    is_new = _iso(r[created_col]) > since
                    inserted += is_new
                    updated += not is_new
                    op.upsert(table=table, data={k: (_iso(v) if hasattr(v, "isoformat") else v) for k, v in r.items()})
                last = rows[-1]
                cursors[table] = {"updated_at": _iso(last["updated_at"]), "key": last[key]}
                op.checkpoint({"cursors": cursors})
            log.info(f"SYNC_RECORD table={table} inserted={inserted} updated={updated} deleted=0")


connector = Connector(update=update, schema=schema)

if __name__ == "__main__":
    import json

    with open("configuration.json", encoding="utf-8") as f:
        connector.debug(configuration=json.load(f))

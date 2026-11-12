"""Seeds the carrier tracking database in the Postgres container (the real database source read by the second connector)."""
from __future__ import annotations

import psycopg

from contextloop.config import pg_dsn

DDL = """
DROP SCHEMA IF EXISTS tracking CASCADE;
CREATE SCHEMA tracking;
CREATE TABLE tracking.shipment (
    shipment_id     BIGINT PRIMARY KEY,
    delivery_number TEXT NOT NULL,
    carrier_code    TEXT NOT NULL,
    tracking_number TEXT NOT NULL,
    status          TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL
);
CREATE TABLE tracking.shipment_event (
    event_id    BIGINT PRIMARY KEY,
    shipment_id BIGINT NOT NULL REFERENCES tracking.shipment (shipment_id),
    event_type  TEXT NOT NULL,
    event_at    TIMESTAMPTZ NOT NULL,
    location    TEXT,
    updated_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX ON tracking.shipment (updated_at);
CREATE INDEX ON tracking.shipment_event (updated_at);
COMMENT ON SCHEMA tracking IS 'Synthetic carrier tracking data for the ContextLoop demo';
"""


def seed(carrier: dict) -> None:
    with psycopg.connect(pg_dsn(), autocommit=False) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        conn.execute(DDL)
        for table in ("shipment", "shipment_event"):
            cols, rows = carrier[table]
            with conn.cursor().copy(f"COPY tracking.{table} ({', '.join(cols)}) FROM STDIN") as cp:
                for r in rows:
                    cp.write_row([r[c] or None for c in cols])
        conn.commit()
    print(f"Seeded Postgres: {len(carrier['shipment'][1])} shipments, {len(carrier['shipment_event'][1])} events")

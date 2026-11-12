"""`make sync`: run both Connector SDK connectors and the two simulated SaaS landings, then write the sync log.

Real Connector SDK code: sap_s4 (SAP change feed) and carrier_pg (Postgres container), each run by `fivetran debug`.
Simulated: salesforce and zendesk, landed in the exact layout Fivetran's connectors produce.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import duckdb

from contextloop import config
from contextloop.datagen.world import STALE_CUTOFF
from contextloop.landing import saas, sdk, synclog
from contextloop.warehouse import publish_serving


def _table(rows: list[tuple]) -> str:
    return "\n".join(f"  {c:<11} {t:<15} +{i:<7} ~{u:<7} -{d:<6} {s}" for c, t, i, u, d, s in rows)


def set_zendesk_scenario(stale: bool) -> int:
    """Switches the simulated Zendesk landing between 'two days behind' (trap T6) and 'current', for recording both versions of
    Act 4. Only the simulated Zendesk landing and its sync-log rows change; the real connectors are untouched."""
    from datetime import timedelta

    now = saas.utcnow()
    con = duckdb.connect(str(config.WAREHOUSE_PATH))
    try:
        synclog.ensure(con)
        con.execute("BEGIN")
        if stale:
            synced = now - timedelta(days=2)
            iso = STALE_CUTOFF.strftime("%Y-%m-%d %H:%M:%S")
            con.execute("DELETE FROM fivetran_log.sync_log WHERE connection_id = 'zendesk' AND sync_end > ?", [synced])
            con.execute("DELETE FROM zendesk.ticket_tag WHERE ticket_id IN "
                        f"(SELECT id FROM zendesk.ticket WHERE updated_at > TIMESTAMPTZ '{iso}+00')")
            con.execute(f"DELETE FROM zendesk.ticket WHERE updated_at > TIMESTAMPTZ '{iso}+00'")
            for t in ("organization", "ticket", "ticket_tag"):
                con.execute(f"UPDATE zendesk.{t} SET _fivetran_synced = ?", [synced])
            synclog.record(con, sdk.SyncResult("zendesk", "zendesk", synced - timedelta(minutes=3), synced, "SUCCESSFUL", {}))
            synclog.record(con, sdk.SyncResult("zendesk", "zendesk", now, now, "FAILURE", {},
                                               "Zendesk API rate limit exceeded (simulated scenario T6); retrying on the next schedule"))
        else:
            counts, _ = saas.land_zendesk(con, now, False, STALE_CUTOFF)
            synclog.record(con, sdk.SyncResult("zendesk", "zendesk", now, saas.utcnow(), "SUCCESSFUL", counts))
        con.execute("COMMIT")
        con.execute("CHECKPOINT")
    finally:
        con.close()
    publish_serving()
    print(f"Zendesk scenario: {'two days behind (T6 on)' if stale else 'current (T6 off)'}")
    return 0


def run() -> int:
    if not (config.SAP_DIR / "batch=1").exists():
        print("✗ No source data. Run `make data` first.")
        return 1
    config.WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    results: list[sdk.SyncResult] = []

    results.append(sdk.run_connector("sap_s4", "sap_s4", {"source_dir": str(config.SAP_DIR)}))
    results.append(sdk.run_connector("carrier_pg", "carrier_pg", {
        "host": os.environ.get("PGHOST", "localhost"), "port": os.environ.get("PGPORT", "5432"),
        "database": os.environ.get("PGDATABASE", "carrier"), "user": os.environ.get("PGUSER", "carrier"),
        "password": os.environ.get("PGPASSWORD", "")}))
    for r in results:
        if r.status != "SUCCESSFUL":
            print(r.output[-3000:])

    con = duckdb.connect(str(config.WAREHOUSE_PATH))
    try:
        synclog.ensure(con)
        con.execute("BEGIN")
        started = saas.utcnow()
        sf = saas.land_salesforce(con, started)
        results.append(sdk.SyncResult("salesforce", "salesforce", started, saas.utcnow(), "SUCCESSFUL", sf))
        stale = config.T6_STALE_ZENDESK
        started = saas.utcnow()
        zd, synced = saas.land_zendesk(con, started, stale, STALE_CUTOFF)
        if stale:
            # The last successful Zendesk sync is two days old; today's attempt fails (simulated).
            if synclog.last_success(con, "zendesk") is None or synclog.last_success(con, "zendesk") > synced:
                results.append(sdk.SyncResult("zendesk", "zendesk", synced - timedelta(minutes=3), synced, "SUCCESSFUL", zd))
            results.append(sdk.SyncResult("zendesk", "zendesk", started, saas.utcnow(), "FAILURE", {},
                                          "Zendesk API rate limit exceeded (simulated scenario T6); retrying on the next schedule"))
        else:
            results.append(sdk.SyncResult("zendesk", "zendesk", started, saas.utcnow(), "SUCCESSFUL", zd))
        for r in results:
            synclog.record(con, r)
        con.execute("COMMIT")
        synclog.mar_estimate(con)
        con.execute("CHECKPOINT")
    finally:
        con.close()
    publish_serving()

    rows = []
    for r in results:
        for t, c in sorted(r.tables.items()) or [("—", {"inserted": 0, "updated": 0, "deleted": 0})]:
            rows.append((r.connection, t, c["inserted"], c["updated"], c["deleted"], r.status if r.status != "SUCCESSFUL" else ""))
    print("Sync complete (+ inserted, ~ updated, - deleted):")
    print(_table(rows))
    failed_sdk = [r for r in results if r.connection in ("sap_s4", "carrier_pg") and r.status != "SUCCESSFUL"]
    if stale:
        print("Scenario T6 is on: Zendesk's last successful sync was two days ago.")
    print(f"Finished at {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC")
    return 1 if failed_sdk else 0

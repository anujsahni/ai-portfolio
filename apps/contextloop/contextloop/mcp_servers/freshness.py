"""Freshness MCP server: how recently each source synced, from the Fivetran-style sync log (fivetran_log schema).

Tool
  check_freshness   per source: last successful sync, its age, rows changed, the latest attempt (and its error, if any),
                    and whether it is inside the agreed freshness window (24 hours; dbt errors at 48 hours)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from contextloop.mcp_servers.common import make_server
from contextloop.warehouse import serving

PORT = 8102
WINDOW_HOURS = 24

server = make_server("contextloop-freshness", PORT, (
    "Data freshness for Northstar's four sources. Call check_freshness before answering, and say plainly when a source "
    "is outside its window and which parts of the answer depend on it."))


def freshness(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    with serving() as con:
        conns = con.execute("SELECT connection_id, connection_name, destination_schema, is_simulated "
                            "FROM fivetran_log.connection ORDER BY 1").fetchall()
        out = []
        for cid, name, schema, simulated in conns:
            ok = con.execute("SELECT sync_end, rows_inserted, rows_updated, rows_deleted, table_counts FROM fivetran_log.sync_log "
                             "WHERE connection_id = ? AND status = 'SUCCESSFUL' ORDER BY sync_end DESC LIMIT 1", [cid]).fetchone()
            last = con.execute("SELECT sync_end, status, message FROM fivetran_log.sync_log WHERE connection_id = ? "
                               "ORDER BY sync_end DESC LIMIT 1", [cid]).fetchone()
            age_h = round((now - ok[0]).total_seconds() / 3600, 1) if ok else None
            out.append({
                "source": cid, "name": name, "schema": schema, "simulated_landing": bool(simulated),
                "last_successful_sync": ok[0].isoformat() if ok else None, "age_hours": age_h,
                "age_days": round(age_h / 24, 1) if age_h is not None else None,
                "within_window": age_h is not None and age_h <= WINDOW_HOURS,
                "rows_changed_last_success": (ok[1] + ok[2] + ok[3]) if ok else 0,
                "latest_attempt": {"at": last[0].isoformat(), "status": last[1], "message": last[2]} if last else None,
            })
    stale = [s["source"] for s in out if not s["within_window"]]
    return {"checked_at": now.isoformat(timespec="seconds"), "window_hours": WINDOW_HOURS, "sources": out,
            "all_current": not stale, "stale_sources": stale}


@server.tool()
def check_freshness() -> dict:
    """Report, for SAP, the carrier database, Salesforce and Zendesk, when each last synced successfully, how old that is,
    whether it is inside the 24-hour freshness window, and the latest sync attempt with any error."""
    return json.loads(json.dumps(freshness(), default=str))


if __name__ == "__main__":
    server.run(transport="streamable-http")

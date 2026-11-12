"""Act 2: Move. Four sources land the same way: incremental, deletes kept as flags, history kept, schema changes absorbed."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from contextloop.ui import charts, common


def connectors() -> pd.DataFrame:
    return common.query("""
        WITH last_ok AS (SELECT connection_id, max(sync_end) AS last_success FROM fivetran_log.sync_log WHERE status = 'SUCCESSFUL' GROUP BY 1),
             latest AS (SELECT * FROM fivetran_log.sync_log QUALIFY row_number() OVER (PARTITION BY connection_id ORDER BY sync_end DESC) = 1),
             totals AS (SELECT connection_id, sum(rows_inserted + rows_updated + rows_deleted) AS rows_synced, count(*) AS syncs
                        FROM fivetran_log.sync_log GROUP BY 1),
             mar AS (SELECT connection_id, sum(incremental_rows) AS mar FROM fivetran_log.incremental_mar
                     WHERE measured_month = date '2026-10-01' GROUP BY 1)
        SELECT c.connection_id, c.connection_name, c.is_simulated, l.status AS latest_status, l.message, o.last_success,
               t.rows_synced, t.syncs, m.mar
        FROM fivetran_log.connection c LEFT JOIN last_ok o USING (connection_id) LEFT JOIN latest l USING (connection_id)
        LEFT JOIN totals t USING (connection_id) LEFT JOIN mar m USING (connection_id) ORDER BY c.is_simulated, c.connection_id""")


def freshness(conns: pd.DataFrame, now: datetime) -> None:
    """How far behind each source is: the fact an agent on raw tables can't see."""
    rows = []
    for r in conns.itertuples():
        if pd.isna(r.last_success):
            continue
        days = (now - r.last_success.to_pydatetime()).total_seconds() / 86400
        hours = days * 24
        rows.append({"source": r.connection_name.split(" (")[0], "days": round(days, 2), "status": "Current" if days <= 1 else "Behind",
                     "label": (f"✓ Current · {hours:.0f} h ago" if hours >= 1 else "✓ Current · under 1 h ago") if days <= 1 else f"⚠ {days:.1f} days behind"})
    if not rows:
        return
    df = pd.DataFrame(rows)
    behind = df[df.status == "Behind"]["source"].tolist()
    st.subheader(f"{' and '.join(behind)} {'is' if len(behind) == 1 else 'are'} behind; everything else is current" if behind
                 else "Every source is current")
    st.caption("Days since each source's last successful sync. The sync log records this; the raw tables don't, so an agent "
               "reading them can't tell. Act 4 hands it to the agent as a tool.")
    st.altair_chart(charts.freshness_bars(df), use_container_width=True)


def render() -> None:
    common.header("Act 2", "Move", "Fivetran lands all four systems the same way: incremental, with deletes kept as flags rather "
                  "than lost, and history kept for the fields that change.")
    if not common.require_warehouse():
        return
    now = datetime.now(timezone.utc)
    conns = connectors()
    freshness(conns, now)
    cols = st.columns(4)
    for col, r in zip(cols, conns.itertuples(), strict=False):
        age = (now - r.last_success.to_pydatetime()).total_seconds() / 3600 if pd.notna(r.last_success) else None
        fresh = age is not None and age <= 24
        kind = "Connector SDK (real code)" if not r.is_simulated else "Simulated landing (Fivetran layout)"
        status = common.badge("Current" if fresh else f"{age / 24:.1f} days behind" if age else "Never synced", "ok" if fresh else "warn",
                              "check" if fresh else "warning")
        col.markdown(f'<div class="cl-card"><h4>{r.connection_name.split(" (")[0]}</h4><small>{kind}</small><br>{status}<br>'
                     f'<small>Last success: {r.last_success:%d %b %H:%M} UTC<br>Rows synced: {int(r.rows_synced or 0):,} in {r.syncs} syncs'
                     f'<br>MAR estimate (Oct): {int(r.mar or 0):,}</small>'
                     + (common.note(r.message) if r.latest_status == "FAILURE" else "") + "</div>", unsafe_allow_html=True)

    st.subheader("Incremental sync")
    st.caption("Runs the real connectors: a new SAP extraction batch (with a new column) plus a few updated carrier shipments, "
               "then `fivetran debug` for both Connector SDK connectors.")
    if st.button("Run incremental sync", type="primary", icon=":material/sync:"):
        common.run_job(["datagen", "--batch", "2", "--no-postgres"], "New SAP extraction batch")
        common.run_job(["touch-carrier", "-n", "3"], "New carrier tracking activity")
        code, out = common.run_job(["sync"], "Syncing all four sources")
        st.session_state["act2-synced"] = code == 0
    log = common.query("SELECT connection_id, status, sync_end, rows_inserted AS inserted, rows_updated AS updated, "
                       "rows_deleted AS deleted, message FROM fivetran_log.sync_log ORDER BY sync_end DESC LIMIT 8")
    st.dataframe(log, hide_index=True, use_container_width=True)
    changed = common.query("SELECT vbeln, kunnr, erdat, wadat, zz_carrier_id, _fivetran_synced FROM sap_s4.likp "
                           "WHERE _fivetran_synced = (SELECT max(_fivetran_synced) FROM sap_s4.likp) ORDER BY vbeln LIMIT 12") \
        if "zz_carrier_id" in set(common.query("SELECT column_name FROM information_schema.columns WHERE table_name = 'likp'")["column_name"]) \
        else None
    a, b = st.columns(2)
    with a:
        st.markdown("**Schema change:** `LIKP.ZZ_CARRIER_ID` added at the source")
        if changed is not None:
            n = common.query("SELECT count(zz_carrier_id) AS n, count(*) AS total FROM sap_s4.likp")
            st.markdown(common.badge("Column landed with no code change", "ok", "check") +
                        f"<small>{n['n'][0]} rows have it; {n['total'][0] - n['n'][0]:,} older rows are null</small>", unsafe_allow_html=True)
            st.caption("Rows changed in the latest SAP sync:")
            st.dataframe(changed, hide_index=True, use_container_width=True)
        else:
            st.info("Not there yet. Press **Run incremental sync** to land batch 2.")
    with b:
        st.markdown("**Deletes kept as flags (trap T1)**")
        d = common.query("SELECT count(*) FILTER (WHERE _fivetran_deleted) AS deleted, count(*) AS total FROM sap_s4.likp")
        st.markdown(common.badge(f"{d['deleted'][0]} cancelled deliveries", "warn", "info") +
                    "<small>kept with _fivetran_deleted = true, never removed</small>", unsafe_allow_html=True)
        st.dataframe(common.query("SELECT vbeln, kunnr, wadat, wadat_ist, _fivetran_deleted FROM sap_s4.likp WHERE _fivetran_deleted "
                                  "ORDER BY vbeln LIMIT 6"), hide_index=True, use_container_width=True)
    st.markdown("**History mode (trap T5):** one row per version of an account's tier")
    st.dataframe(common.query("SELECT name, tier_c, _fivetran_start, _fivetran_end, _fivetran_active FROM salesforce.account WHERE id IN "
                              "(SELECT id FROM salesforce.account GROUP BY id HAVING count(*) > 1) ORDER BY name, _fivetran_start"),
                 hide_index=True, use_container_width=True)
    with st.expander("Go deeper: the connector code and the MAR estimate"):
        st.markdown("The SAP connector is real Fivetran Connector SDK code: `schema()` declares the tables and keys; `update()` "
                    "reads changes after the saved cursor, upserts, deletes and checkpoints. At a customer this is Fivetran's "
                    "native SAP connectors or a hybrid deployment agent.")
        st.code(common.project_file("connectors/sap_s4/connector.py").split("def update", 1)[1][:2200], language="python")
        mar = common.query("SELECT measured_month, connection_id, sum(incremental_rows) AS mar FROM fivetran_log.incremental_mar "
                           "WHERE measured_month >= date '2026-01-01' GROUP BY 1, 2 ORDER BY 1")
        st.caption("Monthly active rows, ESTIMATED as distinct primary keys changed per month (not Fivetran's billing rules).")
        st.bar_chart(mar, x="measured_month", y="mar", color="connection_id", height=260)
    common.nav_buttons("act2")

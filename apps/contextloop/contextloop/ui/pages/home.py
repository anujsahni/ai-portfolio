"""Opening: the customer, the four systems, the COO's question and the discovery framing."""
from __future__ import annotations

import streamlit as st

from contextloop.ui import charts, common


def stakes() -> None:
    """Why the question matters now: on-time delivery to strategic accounts, month by month (full months only)."""
    df = common.query("""
        WITH m AS (SELECT date_trunc('month', f.requested_delivery_date) AS month, avg(f.is_on_time::int) AS rate, count(*) AS deliveries
                   FROM marts.fct_delivery f JOIN marts.dim_account a USING (customer_id)
                   WHERE f.is_delivered AND a.is_strategic GROUP BY 1)
        SELECT * FROM m WHERE month > (SELECT min(month) FROM m)
          AND month < date_trunc('month', (SELECT max(as_of_date) FROM marts.account_risk)) ORDER BY month""")
    if df.empty:
        return
    peak = df.loc[df["rate"].idxmax()]
    last = df.iloc[-1]
    st.subheader(f"On-time delivery to strategic accounts has fallen to {last['rate']:.0%}")
    where = "below" if last["rate"] < charts.THRESHOLD else "close to"
    st.caption(f"From {peak['rate']:.0%} in {peak['month']:%B %Y} to {last['rate']:.1%} in {last['month']:%B %Y}, {where} the 85% "
               "line where accounts count as at risk. Which accounts, and what to do, is the COO's question.")
    st.altair_chart(charts.on_time_trend(df), use_container_width=True)
    with st.expander("Table view"):
        st.dataframe(df, hide_index=True, column_config={"rate": st.column_config.NumberColumn("on time", format="percent"),
                                                         "month": st.column_config.DateColumn(format="MMM YYYY")})


def teaser() -> None:
    """Where the demo ends, up front: the same agent's score without and with the stack."""
    from contextloop.ui.pages import compare

    try:
        s = compare.scores()
    except Exception:  # noqa: BLE001  (no recordings yet: skip the teaser)
        return
    if not s["governed"]:
        return
    q = s["questions"]
    without = common.badge(f"Without the stack: {s['naive']} of {q} right", "bad", "close")
    with_ = common.badge(f"With Fivetran + dbt: {s['governed']} of {q} right", "ok", "check")
    st.markdown(f'<div class="cl-card"><h4>Where this ends</h4>The same AI agent, asked the same {q} questions. '
                f'Nothing changes but the data foundation.<br><br>{without} {with_}</div>', unsafe_allow_html=True)
    pages = st.session_state.get("_pages", {})
    if "compare" in pages:
        st.page_link(pages["compare"], label="Jump to the side-by-side", icon=":material/compare:")


def render() -> None:
    common.header("ContextLoop · proof of value", "Northstar Industrial and the question",
                  "A COO asks an AI agent a real business question. First it answers from raw data; then from a trusted foundation.")
    st.markdown('<div class="cl-quote">“Which of our strategic accounts are at risk because of late shipments, and what should '
                'the account teams do this week?”<br><small>Dana Okafor, COO, Northstar Industrial (fictional)</small></div>',
                unsafe_allow_html=True)
    cols = st.columns(4)
    systems = [("SAP S/4HANA", "Orders, deliveries, billing", "Cryptic names, two currencies, cancelled orders still present"),
               ("Carrier tracking (Postgres)", "Shipments and tracking events", "The <i>actual</i> delivery time lives only here"),
               ("Salesforce", "Accounts, tiers, renewals", "IDs don't match SAP; a look-alike duplicate; tiers changed mid-quarter"),
               ("Zendesk", "Support tickets", "Shipping complaints tagged inconsistently; sync two days behind")]
    for col, (name, holds, hard) in zip(cols, systems, strict=True):
        col.markdown(f'<div class="cl-card"><h4>{name}</h4>{holds}{common.note(hard)}</div>', unsafe_allow_html=True)
    if common.warehouse_ready():
        stakes()
        n = common.query("SELECT count(*) AS n FROM marts.dim_account WHERE is_strategic")["n"][0]
        d = common.query("SELECT count(*) AS n FROM marts.fct_delivery")["n"][0]
        st.caption(f"In this demo: 120 customers ({n} strategic), {d:,} deliveries over 18 months, as of Friday 6 November 2026.")
    teaser()
    st.subheader("Before the demo: three discovery questions")
    a, b, c = st.columns(3)
    a.markdown("**Sources.** Where does the data behind this question live, and who owns each system?\n\n"
               "*Four systems, four owners.*")
    b.markdown("**AI plans.** What should agents do with this data in the next two quarters, and who will trust them?\n\n"
               "*An agent the COO can ask directly.*")
    c.markdown("**Trust today.** When two reports disagree, how do you find out which is right?\n\n"
               "*Slowly: definitions live in people's heads.*")
    with st.expander("How to present this (10 or 20 minutes)"):
        st.markdown("Follow the navigator: **Next →** at the bottom of each page. The talk track is in "
                    "`docs/demo/talk-track.md`; the step-by-step guide is in `docs/getting-started.md`.")
    common.nav_buttons("home")

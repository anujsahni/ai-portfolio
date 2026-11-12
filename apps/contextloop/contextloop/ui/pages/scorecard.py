"""The proof-of-value scorecard: Northstar's success criteria with live pass or fail, cost estimate, specialist map, next steps."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from contextloop.ui import common, scorecard_data


def render() -> None:
    common.header("Close", "Proof-of-value scorecard", "Every success criterion agreed at the start, checked against data, and what "
                  "it would take to run this for real.")
    if not common.require_warehouse():
        return
    pov = scorecard_data.POV
    res = scorecard_data.checks()
    pages = st.session_state.get("_pages", {})
    for sc in pov["success_criteria"]:
        ok, note = res[sc["check"]]
        kind, label, ic = ("ok", "Pass", "check") if ok else ("muted", "Pending", "pending") if ok is None else ("bad", "Fail", "close")
        cols = st.columns([6, 1])
        cols[0].markdown(f"{common.badge(label, kind, ic)} **{sc['statement']}**<br><small>{note}</small>", unsafe_allow_html=True)
        if sc["evidence"] in pages:
            cols[1].page_link(pages[sc["evidence"]], label="Evidence", icon=":material/arrow_outward:")
    st.subheader("Cost estimate")
    mar = pd.DataFrame(scorecard_data.mar_estimate(), columns=["connection", "estimated MAR per month"])
    st.dataframe(mar, hide_index=True)
    for a in pov["cost_assumptions"]:
        st.caption(f"• {a}")
    a, b = st.columns(2)
    with a:
        st.subheader("Time to value")
        st.dataframe(pd.DataFrame(pov["time_to_value"]), hide_index=True, use_container_width=True)
    with b:
        st.subheader("Path to production")
        for p in pov["path_to_production"]:
            st.checkbox(p, value=False, key=f"ptp-{p[:20]}")
    st.subheader("Specialist map")
    st.dataframe(pd.DataFrame(pov["specialists"]), hide_index=True, use_container_width=True)
    st.markdown("**The next step is a scoped pilot with named owners, not another demo.**")
    common.nav_buttons("scorecard")

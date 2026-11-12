"""Act 1: the confident wrong answer. The naive agent, with raw SQL only."""
from __future__ import annotations

import streamlit as st

from contextloop.agent.explain import explain
from contextloop.ui import agent_view, charts, common, compare_data

FIX_IN = {"T1": "Act 2 (deletes kept as flags) and Act 3 (staging filter)", "T2": "Act 3 (carrier delivery time in fct_delivery)",
          "T3": "Act 3 (TCURR conversion in fct_revenue)", "T4": "Act 3 (identity resolution)", "T5": "Act 2 (history mode) and Act 3",
          "T6": "Act 4 (the freshness tool)", "—": "Act 4 (the governed agent)"}


def claimed_vs_truth(tr: dict) -> None:
    """The reveal: the agent's list and rates against the trusted model."""
    risk = common.query("SELECT account_name, on_time_rate_90d FROM marts.account_risk").to_dict("records")
    rows = compare_data.headline_accounts({"naive": tr.get("answer")}, common.truth(), risk)
    wrong = sum(1 for r in rows if r["naive"] == compare_data.WRONG)
    missed = sum(1 for r in rows if r["naive"] == compare_data.MISSED)
    st.subheader("It looks right. It isn't.")
    st.markdown(f"Checked against the trusted model, the list has **{wrong}** account that shouldn't be there and misses "
                f"**{missed}** that should, {compare_data.rates_sentence(rows)} Nothing in the answer warns you.")
    st.altair_chart(charts.accounts_verdict(rows, agents=("naive",), labels={"naive": "Verdict"}), use_container_width=False)


def render() -> None:
    common.header("Act 1", "The confident wrong answer",
                  "The same model we'll use in Act 4, given SQL access to the raw tables. It's fluent, precise, and wrong.")
    if not common.require_warehouse():
        return
    q = agent_view.question_picker("act1-q")
    st.markdown(f'<div class="cl-quote">{q["question"]}</div>', unsafe_allow_html=True)
    steps = st.container()
    if st.button("Ask the agent", type="primary", key="act1-ask", icon=":material/play_arrow:"):
        st.session_state["act1-asked"] = q["id"]
        tr = agent_view.ask("naive", q, steps)
    else:
        tr = agent_view.get_trace("naive", q)
        if tr and st.session_state.get("act1-asked") == q["id"]:
            common.play_steps(tr, steps, pace=0)
    if not tr:
        common.no_recording("naive")
        common.nav_buttons("act1")
        return
    if st.session_state.get("act1-asked") != q["id"]:
        st.caption("Press **Ask the agent** to play the run.")
        common.nav_buttons("act1")
        return
    if tr.get("recorded"):
        common.recorded_label(tr)
    common.answer_table(tr.get("answer"))
    agent_view.show_score(tr, q)
    if q["id"] == "G1":
        claimed_vs_truth(tr)

    st.subheader("What went wrong")
    findings = tr.get("explanation") or explain(tr, common.truth(), common.traps())
    if not findings:
        st.success("No trap detected in this run.")
    cols = st.columns(2)
    for i, f in enumerate(findings):
        with cols[i % 2]:
            st.markdown(f'<div class="cl-card"><h4>{common.badge(f["trap"], "bad", "close")} {f["title"]}</h4>{f["detail"]}'
                        f'<br><small>Fixed in: {FIX_IN.get(f["trap"], "—")}</small></div>', unsafe_allow_html=True)
            if f.get("sql_line"):
                st.code(f["sql_line"], language="sql")
    with st.expander("Go deeper: why a better prompt doesn't fix this"):
        st.markdown("The agent can't know that cancelled deliveries are soft-deleted, that WADAT is a ship date, that a "
                    "duplicate account exists, or that tiers changed mid-quarter. Those are **definitions and data facts**, "
                    "not language skills. Acts 2 and 3 build them into the data; Act 4 hands them to the same agent.")
    common.nav_buttons("act1")

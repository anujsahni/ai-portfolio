"""Act 4: Context. The same agent, through the dbt MCP server, the metrics server and the freshness server."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from contextloop.eval.score import score
from contextloop.ui import agent_view, charts, common

SERVER_KIND = {"dbt MCP": "coral", "Metrics MCP": "info", "Freshness MCP": "teal"}


def governed_answer(tr: dict) -> None:
    ans = tr.get("answer") or {}
    common.answer_table(ans)
    rows = [a for a in ans.get("at_risk_accounts") or [] if isinstance(a.get("on_time_rate"), (int, float))]
    if rows:
        st.markdown(f"**{len(rows)} strategic accounts below the 85% line**, each from the governed `on_time_delivery_rate` metric")
        st.altair_chart(charts.at_risk_bars(rows), use_container_width=True)
    fresh = ans.get("freshness") or []
    if fresh:
        st.markdown(" ".join(common.badge(f"{f['source']}: {'current' if f.get('within_window') else 'stale'}",
                                          "ok" if f.get("within_window") else "warn") for f in fresh), unsafe_allow_html=True)
    if ans.get("caveats"):
        for c in ans["caveats"]:
            st.markdown(common.note(c), unsafe_allow_html=True)
    a, b = st.columns(2)
    with a:
        st.markdown("**Metrics cited, with their definitions**")
        for m in ans.get("metrics_used") or []:
            st.markdown(f"- `{m['name']}`: {m['definition']}")
    with b:
        st.markdown("**Lineage**")
        for ln in ans.get("lineage") or []:
            st.markdown(f"- {ln}")
    numbers_traced(tr)


def numbers_traced(tr: dict) -> None:
    """Every number in the answer should appear in some query_metric result."""
    vals = set()
    for s in tr.get("steps", []):
        if s["tool"] == "query_metric":
            for row in s["output"].get("rows", []):
                vals |= {round(v, 4) for v in row if isinstance(v, (int, float))}
    ans = tr.get("answer") or {}
    nums = [a.get("on_time_rate") for a in ans.get("at_risk_accounts") or []] + [ans.get("value")]
    nums = [round(n, 4) for n in nums if isinstance(n, (int, float))]
    traced = sum(1 for n in nums if n in vals or round(n / 100, 4) in vals)
    if nums:
        st.caption(f"{traced} of {len(nums)} numbers in the answer appear verbatim in a `query_metric` result.")


def scoreboard() -> pd.DataFrame:
    rows = []
    for q in common.golden():
        row = {"question": f"{q['id']} · {q['question'][:60]}…"}
        for agent in ("naive", "governed"):
            tr = common.recording(agent, q["id"])
            row[agent] = ("Correct" if score(q["id"], tr.get("answer"), common.truth())["correct"] else "Wrong") if tr else "—"
        rows.append(row)
    return pd.DataFrame(rows)


def render() -> None:
    common.header("Act 4", "Context", "Same model, same question. This time the agent works through the dbt MCP server, a metrics "
                  "tool and a freshness tool, so it uses Northstar's definitions and tells you how fresh the data is.")
    if not common.require_warehouse():
        return
    q = agent_view.question_picker("act4-q")
    st.markdown(f'<div class="cl-quote">{q["question"]}</div>', unsafe_allow_html=True)
    t6_off = q["id"] == "G1" and st.toggle("Show the run with Zendesk current (stale-data scenario T6 off)", key="act4-t6",
                                           help="By default Zendesk's last sync is two days old. Compare the answer when it is current.")
    variant = "-t6off" if t6_off else ""
    steps = st.container()
    if st.button("Ask the governed agent", type="primary", key="act4-ask", icon=":material/play_arrow:"):
        st.session_state["act4-asked"] = q["id"] + variant
        tr = agent_view.ask("governed", q, steps, variant=variant)
    else:
        tr = agent_view.get_trace("governed", q, variant)
        if tr and st.session_state.get("act4-asked") == q["id"] + variant:
            common.play_steps(tr, steps, pace=0)
    if not tr:
        common.no_recording("governed")
        common.nav_buttons("act4")
        return
    if st.session_state.get("act4-asked") != q["id"] + variant:
        st.caption("Press **Ask the governed agent** to play the run.")
        common.nav_buttons("act4")
        return
    servers = sorted({common.SERVER_OF.get(s["tool"], "tool") for s in tr.get("steps", [])})
    st.markdown("Tools used: " + " ".join(common.badge(s, SERVER_KIND.get(s, "muted")) for s in servers), unsafe_allow_html=True)
    if tr.get("recorded"):
        common.recorded_label(tr)
    governed_answer(tr)
    agent_view.show_score(tr, q)

    st.subheader("Side by side with Act 1")
    naive = agent_view.get_trace("naive", q)
    a, b = st.columns(2)
    with a:
        st.markdown("**Naive agent (raw SQL)**")
        if naive:
            agent_view.show_score(naive, q)
            if q["id"] == "G1":
                st.write(sorted(x["account_name"] for x in (naive.get("answer") or {}).get("at_risk_accounts") or []))
            else:
                st.write((naive.get("answer") or {}).get("answer_summary"))
            traps_hit = sorted({f["trap"] for f in naive.get("explanation") or [] if f["trap"] != "—"})
            st.caption("Traps behind its mistakes: " + (", ".join(traps_hit) or "none detected"))
        else:
            common.no_recording("naive")
    with b:
        st.markdown("**Governed agent (MCP)**")
        agent_view.show_score(tr, q)
        if q["id"] == "G1":
            st.write(sorted(x["account_name"] for x in (tr.get("answer") or {}).get("at_risk_accounts") or []))
        else:
            st.write((tr.get("answer") or {}).get("answer_summary"))
    pages = st.session_state.get("_pages", {})
    if "compare" in pages:
        st.page_link(pages["compare"], label="See the full side-by-side: without vs with the stack", icon=":material/compare:")
    st.markdown("**All six golden questions** (recorded runs, scored against the hidden truth)")
    board = scoreboard()
    totals = {a: int((board[a] == "Correct").sum()) for a in ("naive", "governed")}
    st.dataframe(board, hide_index=True, use_container_width=True)
    st.markdown(f"Naive **{totals['naive']} / 6** · Governed **{totals['governed']} / 6**")
    from contextloop.ui.scorecard_data import golden_totals

    avg = golden_totals()
    if "report" in avg.get("source", ""):
        st.caption(f"These are the runs replayed in the demo. Averaged over every recorded run ({avg['source']}): "
                   f"naive {avg['naive']:g} / 6, governed {avg['governed']:g} / 6.")
    with st.expander("Go deeper: what each MCP server gives the agent"):
        st.markdown("- **dbt MCP** (`dbt-mcp`, the official server): model docs, columns and lineage from the dbt manifest.\n"
                    "- **Metrics MCP**: `list_metrics` (definitions) and `query_metric`. MetricFlow compiles governed SQL; the "
                    "agent never writes SQL against the marts itself.\n"
                    "- **Freshness MCP**: `check_freshness` from the Fivetran sync log, so the agent can say when data is stale.\n\n"
                    "The bridge connects to the three private containers with the Python MCP client and passes their tools to "
                    "Claude's tool use. Ticket text is treated as data, never as instructions.")
    common.nav_buttons("act4")

"""The difference: the same agent without and with the Fivetran and dbt stack, on one page."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from contextloop.ui import agent_view, brand, charts, common, compare_data, scorecard_data
from contextloop.ui.compare_data import AGENTS, LABEL, LAYERS

FLOW = {"naive": ["SAP · Salesforce · Zendesk · Carrier", "Raw tables, as extracted", "Claude writes its own SQL"],
        "governed": ["SAP · Salesforce · Zendesk · Carrier", "Fivetran: moved, deletes and history kept",
                     "dbt: modelled, tested, metrics defined once", "MCP tools: definitions, lineage, freshness", "Claude"]}
TONE = {"naive": (brand.ROSE_SOFT, "#B4282D"), "governed": (brand.MINT_SOFT, "#13734F")}


def _flow(agent: str) -> str:
    steps = FLOW[agent]
    return "".join(f'<div class="cl-flow-step">{s}</div>' + ('<div class="cl-flow-arrow">↓</div>' if i < len(steps) - 1 else "")
                   for i, s in enumerate(steps))


def _column(agent: str, k: dict) -> str:
    bg, ink = TONE[agent]
    exact = k["accounts_right"] == k["accounts_expected"] and not k["accounts_wrong"]
    accounts = (f"All {k['accounts_expected']} at-risk accounts, none extra" if exact else
                f"{k['accounts_right']} of {k['accounts_expected']} right · {k['accounts_wrong']} wrong added · "
                f"{k['accounts_missed']} missed")
    stale = ", ".join(x.capitalize() for x in k["stale_truth"]) or "nothing"
    if k["freshness_right"]:
        fresh = f"Flags {stale} as behind" if k["stale_truth"] else "Checked: every source current"
    else:
        fresh = (f"Missed that {stale} is behind (checked {k['freshness_checked']} of {k['freshness_sources']} sources)"
                 if k["freshness_sources"] else f"Not checked: it can't see sync times, and {stale} is behind")
    gov_defs = k["definitions_governed"]
    defs = (f"{gov_defs} governed metrics, defined once in dbt" if gov_defs and gov_defs == k["definitions"] else
            f"{k['definitions']} it wrote itself, {gov_defs} governed" if k["definitions"] else "None")
    lin = (f"{k['lineage']} paths through tested dbt models" if k["lineage"] and k["lineage_governed"] == k["lineage"] else
           f"{k['lineage']} paths straight from raw tables" if k["lineage"] else "None")
    facts = [("Headline question", accounts, exact),
             ("Metric definitions cited", defs, gov_defs > 0 and gov_defs == k["definitions"]),
             ("Lineage shown", lin, k["lineage"] > 0 and k["lineage_governed"] == k["lineage"]),
             ("Data freshness", fresh, k["freshness_right"])]
    rows = "".join(f'<div class="cl-vs-row">{brand.icon("check" if ok else "close", 15, "#13734F" if ok else "#B4282D")}'
                   f'<div><small>{label}</small><br><b>{value}</b></div></div>' for label, value, ok in facts)
    return (f'<div class="cl-vs" style="border-top:5px solid {ink}">'
            f'<div class="cl-vs-label" style="color:{ink}">{LABEL[agent]}</div>'
            f'<div class="cl-vs-hero" style="background:{bg}"><span style="color:{ink}">{k["correct"]}</span>'
            f'<small> of {k["questions"]} questions answered correctly</small></div>'
            f'<div class="cl-flow">{_flow(agent)}</div>{rows}</div>')


def governed_metrics() -> set[str]:
    """The metric names defined in the dbt semantic layer."""
    import json
    import os
    from pathlib import Path

    from contextloop import config

    p = Path(os.environ.get("DBT_TARGET_PATH", config.DBT_PROJECT_DIR / "target")) / "semantic_manifest.json"
    return {m["name"] for m in json.loads(p.read_text())["metrics"]} if p.exists() else set()


def scores() -> dict[str, int]:
    """Questions each agent answers correctly in the replayed runs (for the teaser on the opening page)."""
    golden, truth = common.golden(), common.truth()
    traces = {a: {q["id"]: agent_view.get_trace(a, q) for q in golden} for a in AGENTS}
    res = compare_data.question_results(traces, truth, golden)
    return {a: sum(1 for r in res if r[a]) for a in AGENTS} | {"questions": len(golden)}


def render() -> None:
    common.header("The difference", "Without vs with the stack",
                  "Same model, same questions, same source systems. The only thing that changes is the data foundation "
                  "between the sources and the agent.")
    if not common.require_warehouse():
        return
    golden, truth = common.golden(), common.truth()
    traces = {a: {q["id"]: agent_view.get_trace(a, q) for q in golden} for a in AGENTS}
    if not any(traces["naive"].values()) or not any(traces["governed"].values()):
        common.no_recording("naive or governed")
        common.nav_buttons("compare")
        return
    risk = common.query("SELECT account_name, on_time_rate_90d FROM marts.account_risk").to_dict("records")
    accounts = compare_data.headline_accounts({a: (traces[a].get("G1") or {}).get("answer") for a in AGENTS}, truth, risk)
    stale_truth = {"zendesk"} if (common.traps().get("T6") or {}).get("enabled") else set()
    k = {a: compare_data.kpis(a, traces[a], truth, golden, accounts, governed_metrics(), stale_truth) for a in AGENTS}

    st.markdown('<div class="cl-quote">Without the stack the agent is fluent, precise and wrong. With it, the same agent is right '
                'and shows why you can trust it.</div>', unsafe_allow_html=True)
    left, right = st.columns(2, gap="large")
    left.markdown(_column("naive", k["naive"]), unsafe_allow_html=True)
    right.markdown(_column("governed", k["governed"]), unsafe_allow_html=True)

    st.subheader("The COO's question, account by account")
    n = k["naive"]
    st.markdown(f"The agent on raw tables named **{n['accounts_right'] + n['accounts_wrong']}** accounts, a plausible list. "
                f"**{n['accounts_wrong']}** shouldn't be there and **{n['accounts_missed']}** at-risk account is missing, "
                f"{compare_data.rates_sentence(accounts)} The governed agent's list matches exactly.")
    st.altair_chart(charts.accounts_verdict(accounts, labels=LABEL), use_container_width=False)
    st.caption("At risk means a strategic account below 85% on time over 90 days, with at least two open shipping tickets or a "
               "renewal due (the dbt model `account_risk`). A gray dot hidden behind a blue one means the agent stated the right rate.")
    with st.expander("Table view"):
        st.dataframe(pd.DataFrame(accounts).rename(columns={"naive": LABEL["naive"], "governed": LABEL["governed"]}),
                     hide_index=True, use_container_width=True,
                     column_config={c: st.column_config.NumberColumn(format="percent") for c in ("true_rate", "claimed_rate")})

    st.subheader("All six questions")
    results = compare_data.question_results(traces, truth, golden)
    cells = "".join(
        f'<tr><td><b>{r["id"]}</b> {r["question"]}</td>' + "".join(
            f'<td>{common.badge("Right", "ok", "check") if r[a] else common.badge("Wrong", "bad", "close") if r[a] is False else "—"}</td>'
            for a in AGENTS) + "</tr>" for r in results)
    st.markdown(f'<table class="cl-grid"><tr><th>Question</th><th>{LABEL["naive"]}</th><th>{LABEL["governed"]}</th></tr>'
                f'{cells}</table>', unsafe_allow_html=True)
    avg = scorecard_data.golden_totals()
    if "report" in avg.get("source", ""):
        st.caption(f"These are the runs replayed in the demo. Averaged over every recorded run ({avg['source']}): "
                   f"{LABEL['naive']} {avg['naive']:g} / 6, {LABEL['governed']} {avg['governed']:g} / 6.")

    st.subheader("What each layer fixes")
    hit = set(compare_data.traps_hit(traces["naive"]))
    st.markdown(f"Six problems are planted in Northstar's data, the kind every real company has. The agent on raw tables fell "
                f"into **{len(hit)} of 6** in these runs. Each one is fixed once, in the data foundation, not in the prompt.")
    rows = "".join(
        f'<tr><td><b>{tid}</b> {name}{"<br>" + common.badge("hit in these runs", "bad", "close") if tid in hit else ""}</td>'
        f'<td>{without}</td><td>{common.badge(layer, "coral" if "dbt" in layer and "Fivetran" not in layer else "info")}<br>{fix}</td>'
        f'</tr>' for tid, name, without, fix, layer in LAYERS)
    st.markdown(f'<table class="cl-grid"><tr><th>Problem in the data</th><th>Without the stack, the agent…</th>'
                f'<th>With the stack</th></tr>{rows}</table>', unsafe_allow_html=True)
    with st.expander("How to say it in one breath"):
        st.markdown("> *\"We didn't change the model or the prompt. Fivetran moved the data with deletes and history intact, dbt "
                    "turned it into tested models with one definition of on-time, and MCP handed those definitions to the agent. "
                    "Same question, and now the answer is right, cited and fresh.\"*")
    common.nav_buttons("compare")

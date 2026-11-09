"""Pipeline: every open deal the viewer may see, the rep's forecast next to the model's score."""
import pandas as pd
import streamlit as st

from dealpulse.ui import logic, state, theme
from dealpulse.ui.theme import e

data = state.data()
persona = state.persona()
deals = logic.visible_deals(data, persona)

theme.page_head(
    "Q4 2026 · snapshot " + data.snapshot_date,
    "Pipeline review",
    f"{len(deals)} open deals for the {persona.team} team this quarter, with each rep's forecast next to the model's win probability."
    if persona.manager else f"Your {len(deals)} open deals this quarter, with your forecast next to the model's win probability.",
)

k = logic.kpis(deals)
diff = k["model_weighted"] - k["stage_weighted"]
cols = st.columns(4)
tiles = [
    ("Open pipeline", logic.money(k["pipeline"]), f"{k['deals']} deals · {k['commit']} in Commit", ""),
    ("Forecast by stage", logic.money(k["stage_weighted"]), "Amount × Salesforce stage probability", ""),
    ("Forecast by model", logic.money(k["model_weighted"]), f"{logic.money(abs(diff))} {'below' if diff < 0 else 'above'} the stage view", ""),
    ("Model disagrees", str(k["flagged"]), f"{logic.money(k['flagged_amount'])} forecast as Commit or Best Case", " risk"),
]
for col, (label, value, sub, cls) in zip(cols, tiles):
    with col:
        theme.html(f'<div class="dp-card dp-kpi{cls}"><span class="label">{e(label)}</span><span class="value">{e(value)}</span><span class="sub">{e(sub)}</span></div>')

f1, f2, f3 = st.columns([3, 2, 2], vertical_alignment="bottom")
with f1:
    forecast = st.segmented_control("Forecast category", ["All", "Commit", "Best Case", "Pipeline"], default="All", key="forecast") or "All"
with f2:
    flagged_only = st.toggle("Disagreements only", key="flagged_only")
with f3:
    owners = sorted({d["owner"] for d in deals})
    owner = st.selectbox("Owner", ["All"] + owners, key="owner") if persona.manager else "All"

rows = logic.filter_deals(deals, forecast, flagged_only, owner)
# Most important first: which deal, does the model disagree, the two probabilities, then the details.
table = pd.DataFrame([{
    "Deal": d["account"],
    "Signal": "⚠ Disagrees" if d["flag"] else "",
    "Forecast": d["forecast"],
    "Stage %": d["stageProbability"],
    "Model %": d["modelProbability"],
    "Biggest risk you can act on": d["topRisk"] or "—",
    "Amount": d["amount"],
    "Stage": logic.short_stage(d["stage"]),
    "Close": pd.Timestamp(d["closeDate"]),
    "Owner": d["owner"],
    "Product": f"{d['product']} · {d['type']}",
} for d in rows])

if table.empty:
    st.info("No deals match these filters.")
else:
    event = st.dataframe(
        table, hide_index=True, width="stretch", on_select="rerun", selection_mode=["single-row", "single-cell"], key="deal_table",
        column_config={
            "Amount": st.column_config.NumberColumn(format="dollar"),
            "Close": st.column_config.DateColumn(format="MMM D"),
            "Stage %": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d%%", help="Salesforce's default probability for the stage"),
            "Model %": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d%%", help="Win probability from the SageMaker model"),
            "Deal": st.column_config.TextColumn(pinned=True),
            "Signal": st.column_config.TextColumn(width="medium", help=f"Commit or Best Case, and the model is at least {data.gap_points} points below the stage"),
        },
    )
    # Open a deal by ticking its row or by clicking any of its cells.
    sel = event.selection if event else None
    picked = (sel.rows or [cell[0] for cell in sel.cells]) if sel else []
    if picked:
        chosen = rows[picked[0]]
        st.session_state["deal_id"] = chosen["id"]
        st.switch_page("views/deal.py", query_params={"id": chosen["id"], "as": persona.id})

theme.html(f'<p class="dp-note">Click a deal to open its brief. Model scores come from the trained SageMaker model (XGBoost, version 1). '
           f'A deal is flagged when it is forecast as Commit or Best Case and the model scores it at least {data.gap_points} points below '
           'its stage probability. No language model is used on this page.</p>')

"""Model card: how good the score is, what moves it, what it uses and its limits."""
import altair as alt
import pandas as pd
import streamlit as st

from dealpulse.ui import logic, state, theme

data = state.data()
state.persona()
m = data.model
if not m:
    st.title("Model", anchor=False)
    st.warning("No evaluation report in the saved data. Run make train, then rebuild the data (see artifacts/dealpulse-mockups/README.md).")
    st.stop()

theme.page_head(
    "Model card · version 1", "Can you trust the score?",
    f"An XGBoost model trained on SageMaker with {m['rows']['train']:,} point-in-time snapshots of {m['deals']['train']:,} closed deals, "
    f"tested on the newest quarter it never saw ({m['quarters']['test'][0]}, {m['deals']['test']} deals). Synthetic data: these numbers "
    "show the method works, not how it would do on your pipeline.",
)

b = m["baseline_stage_probability"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Ranking (AUC)", f"{m['model']['auc']:.3f}", f"{m['model']['auc'] - b['auc']:+.3f} vs. stage", border=True)
c2.metric("Probability error (Brier)", f"{m['model']['brier']:.3f}", f"{m['model']['brier'] - b['brier']:+.3f} vs. stage",
          delta_color="inverse", border=True, help="Lower is better")
c3.metric("Test quarter win rate", f"{100 * m['test_win_rate']:.1f}%", border=True)
c4.metric("Approval", "Pending", border=True, help="A person approves a version before it can serve")

left, right = st.columns(2, gap="large")
with left:
    with st.container(border=True):
        st.subheader("Does 30% mean 30%?", anchor=False)
        rows = [{"Predicted": r["mean_predicted"], "Actually won": r["observed_rate"], "Rows": r["n"], "Series": name}
                for name, series in (("Model", m["calibration"]), ("Salesforce stage probability", m["baseline_calibration"]))
                for r in series if r["n"] >= 20 and r["mean_predicted"] is not None]
        df = pd.DataFrame(rows)
        color = alt.Color("Series:N", scale=alt.Scale(domain=["Model", "Salesforce stage probability"], range=["#2f5bd3", "#9aa3b5"]),
                          legend=alt.Legend(orient="bottom", title=None))
        axis = alt.Axis(format="%", values=[0, .25, .5, .75, 1])
        lines = alt.Chart(df).mark_line(point=True).encode(
            x=alt.X("Predicted:Q", title="Predicted win probability", scale=alt.Scale(domain=[0, 1]), axis=axis),
            y=alt.Y("Actually won:Q", title="Actually won", scale=alt.Scale(domain=[0, 1]), axis=axis),
            color=color, tooltip=[alt.Tooltip("Predicted:Q", format=".0%"), alt.Tooltip("Actually won:Q", format=".0%"), "Rows:Q", "Series:N"])
        diagonal = alt.Chart(pd.DataFrame({"x": [0, 1], "y": [0, 1]})).mark_line(strokeDash=[4, 4], color="#b7c1d6").encode(x=alt.X("x:Q", title="Predicted win probability"), y=alt.Y("y:Q", title="Actually won"))
        st.altair_chart(diagonal + lines, width="stretch")
        st.caption("Dashed diagonal = perfect. Bands with fewer than 20 rows are hidden. One band (50–60%) under-predicts: 55% predicted, 66% won.")

with right:
    with st.container(border=True):
        st.subheader("What moves the score", anchor=False)
        top = pd.DataFrame([{
            "Factor": ("↓ " if fe["direction"] == -1 else "↑ " if fe["direction"] == 1 else "") + logic.feature_label(fe["feature"]),
            "Mean |SHAP|": round(fe["mean_abs_shap"], 3),
            "Kind": "Stage and timing" if fe["feature"] in logic.TIMING_FEATURES else "Deal factor",
        } for fe in m["feature_effects"][:12]])
        chart = alt.Chart(top).mark_bar(cornerRadiusEnd=3).encode(
            x=alt.X("Mean |SHAP|:Q", title="Mean |SHAP| on the held-out quarter"),
            y=alt.Y("Factor:N", sort=None, title=None, axis=alt.Axis(labelLimit=240)),
            color=alt.Color("Kind:N", scale=alt.Scale(domain=["Stage and timing", "Deal factor"], range=["#9aa3b5", "#2f5bd3"]),
                            legend=alt.Legend(orient="bottom", title=None)),
            tooltip=["Factor", "Mean |SHAP|"])
        st.altair_chart(chart, width="stretch")
        st.caption("Grey bars are stage and timing: a deal's progress partly reflects the other factors, so they rank first. "
                   "Blue factors are what a rep can change.")

a, b2 = st.columns(2, gap="large")
with a:
    with st.container(border=True):
        st.subheader("What it uses and what it doesn't", anchor=False)
        st.markdown("- 35 features from stage history, close-date changes, contact roles, activities, discounts, competitors and support cases, "
                    "rebuilt as of each snapshot date.\n- **Not used:** the rep's name or win rate (the score rates the deal, not the person), "
                    "Salesforce's probability and forecast category (the baseline it's compared with), and note text.\n"
                    "- Split by close quarter, so no deal appears in both training and testing.")
with b2:
    with st.container(border=True):
        st.subheader("Limits", anchor=False)
        st.markdown("- Trained on synthetic data with a known hidden rule; a real pipeline needs retraining on a Salesforce export.\n"
                    "- It weighs stage heavily: a late-stage deal with weak engagement can still score high. The brief's evidence is the check.\n"
                    "- Advisory only. It never changes a forecast category or writes to the CRM.")

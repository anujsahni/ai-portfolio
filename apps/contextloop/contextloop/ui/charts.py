"""The story charts (Altair), in the ContextLoop palette.

Rules kept throughout: one hue for a single series; gray for context; status colors (right, wrong, missed, stale) only where
the color means good or bad, always with a symbol and a word beside it, never color alone; thresholds drawn as a labelled
rule; a tooltip on every mark; each chart has a table view on its page.
"""
from __future__ import annotations

import altair as alt
import pandas as pd

from contextloop.ui import brand

GRAY = "#8E98B0"
STATUS_INK = {"Right": "#13734F", "Correctly left out": "#13734F", "Wrongly flagged": "#B4282D", "Missed": "#8A5A00"}
STATUS_MARK = {"Right": "✓", "Correctly left out": "✓", "Wrongly flagged": "✗", "Missed": "–"}
THRESHOLD = 0.85  # dbt var risk_threshold: an account is at risk below 85% on time (plus tickets or a renewal)


def _rule(x: float | None = None, y: float | None = None, label: str = "") -> alt.LayerChart:
    """A labelled threshold line."""
    df = pd.DataFrame([{"v": x if x is not None else y, "label": label}])
    enc = alt.X("v:Q", scale=alt.Scale(zero=False)) if x is not None else alt.Y("v:Q", scale=alt.Scale(zero=False))
    line = alt.Chart(df).mark_rule(color=brand.SLATE, strokeDash=[4, 3], strokeWidth=1.2).encode(enc)
    text = alt.Chart(df).mark_text(align="left", dx=4, dy=-6 if y is not None else 0, color=brand.SLATE, fontSize=11,
                                   baseline="top" if x is not None else "bottom").encode(
        enc, text="label:N", **({"y": alt.value(2)} if x is not None else {"x": alt.value(4)}))
    return line + text


def on_time_trend(df: pd.DataFrame) -> alt.LayerChart:
    """Monthly on-time rate for strategic accounts (columns: month, rate, deliveries), with the at-risk threshold."""
    base = alt.Chart(df).encode(
        x=alt.X("month:T", title=None, axis=alt.Axis(format="%b %y", tickCount="month", labelAngle=0, grid=False)),
        y=alt.Y("rate:Q", title="On time", scale=alt.Scale(domain=[0.75, 1.0]), axis=alt.Axis(format="%", tickCount=5)))
    tip = [alt.Tooltip("month:T", title="Month", format="%B %Y"), alt.Tooltip("rate:Q", title="On time", format=".1%"),
           alt.Tooltip("deliveries:Q", title="Deliveries")]
    line = base.mark_line(color=brand.INDIGO, strokeWidth=2)
    pts = base.mark_point(color=brand.INDIGO, filled=True, size=70, opacity=1).encode(tooltip=tip)
    last = df.tail(1)
    label = alt.Chart(last).mark_text(align="left", dx=8, fontWeight="bold", color=brand.INK).encode(
        x="month:T", y="rate:Q", text=alt.Text("rate:Q", format=".1%"))
    return (_rule(y=THRESHOLD, label="At-risk threshold 85%") + line + pts + label).properties(height=260)


def accounts_verdict(rows: list[dict], agents: tuple[str, ...] = ("naive", "governed"),
                     labels: dict[str, str] | None = None) -> alt.HConcatChart:
    """The headline question, account by account: the true 90-day on-time rate (trusted model), what the agent on raw
    tables said, the threshold, and each agent's verdict as a symbol and a word."""
    labels = labels or {}
    df = pd.DataFrame(rows)
    order = list(df["account"])
    y = alt.Y("account:N", sort=order, title=None, axis=alt.Axis(labelLimit=220, ticks=False, domain=False))
    pts = df.melt(id_vars=["account"], value_vars=["claimed_rate", "true_rate"], var_name="series", value_name="rate").dropna()
    pts["series"] = pts["series"].map({"claimed_rate": "Agent on raw tables said", "true_rate": "True rate (dbt model)"})
    color = alt.Color("series:N", title=None, legend=alt.Legend(orient="top", direction="horizontal", labelLimit=260),
                      scale=alt.Scale(domain=["Agent on raw tables said", "True rate (dbt model)"], range=[GRAY, brand.INDIGO]))
    x = alt.X("rate:Q", title="On time, last 90 days", scale=alt.Scale(domain=[0.55, 1.0]), axis=alt.Axis(format="%", tickCount=5))
    gap = df.dropna(subset=["claimed_rate", "true_rate"])
    link = alt.Chart(gap).mark_rule(color=GRAY, strokeWidth=2).encode(
        y=y, x=alt.X("claimed_rate:Q", scale=alt.Scale(domain=[0.55, 1.0])), x2="true_rate:Q")
    dots = alt.Chart(pts).mark_point(filled=True, size=110, opacity=1, stroke="#FFFFFF", strokeWidth=2).encode(
        y=y, x=x, color=color, tooltip=["account:N", "series:N", alt.Tooltip("rate:Q", format=".1%")])
    left = (link + dots + _rule(x=THRESHOLD, label="85% threshold")).properties(width=430, height=34 * len(df))

    panels = [left]
    for agent in agents:
        v = df[["account", agent]].rename(columns={agent: "verdict"})
        v["text"] = v["verdict"].map(lambda s: f"{STATUS_MARK[s]}  {s}")
        panels.append(alt.Chart(v).mark_text(align="left", fontWeight="bold", fontSize=13).encode(
            y=alt.Y("account:N", sort=order, axis=None), text="text:N",
            color=alt.Color("verdict:N", scale=alt.Scale(domain=list(STATUS_INK), range=list(STATUS_INK.values())), legend=None),
            tooltip=["account:N", alt.Tooltip("verdict:N", title=labels.get(agent, agent))],
        ).properties(width=170, height=34 * len(df), title=alt.TitleParams(labels.get(agent, agent), anchor="start", fontSize=13)))
    return alt.hconcat(*panels, spacing=12).resolve_scale(y="shared", color="independent").configure_view(stroke=None)


def at_risk_bars(rows: list[dict]) -> alt.LayerChart:
    """The governed agent's at-risk accounts: on-time rate from zero, with the threshold and the value at each bar end."""
    df = pd.DataFrame(rows)
    order = list(df.sort_values("on_time_rate")["account_name"])
    base = alt.Chart(df).encode(y=alt.Y("account_name:N", sort=order, title=None, axis=alt.Axis(labelLimit=220, ticks=False)),
                                x=alt.X("on_time_rate:Q", title="On time, last 90 days", scale=alt.Scale(domain=[0, 1]),
                                        axis=alt.Axis(format="%", tickCount=5)))
    tip = [alt.Tooltip("account_name:N", title="Account"), alt.Tooltip("on_time_rate:Q", title="On time", format=".1%"),
           alt.Tooltip("late_deliveries:Q", title="Late deliveries"), alt.Tooltip("open_shipping_tickets:Q", title="Open shipping tickets"),
           alt.Tooltip("renewal_close_date:N", title="Renewal closes")]
    bars = base.mark_bar(color=brand.INDIGO, cornerRadiusEnd=4, height=16).encode(tooltip=tip)
    text = base.mark_text(align="left", dx=6, color=brand.INK, fontSize=12).encode(text=alt.Text("on_time_rate:Q", format=".1%"))
    return (bars + text + _rule(x=THRESHOLD, label="85%")).properties(height=30 * len(df))


def freshness_bars(df: pd.DataFrame, window_days: float = 1.0) -> alt.LayerChart:
    """Days since each source's last successful sync (columns: source, days, status, label), against the sync window."""
    order = list(df.sort_values("days", ascending=False)["source"])
    base = alt.Chart(df).encode(y=alt.Y("source:N", sort=order, title=None, axis=alt.Axis(ticks=False, labelLimit=240)),
                                x=alt.X("days:Q", title="Days since the last successful sync", axis=alt.Axis(tickMinStep=0.5, tickCount=6),
                                        scale=alt.Scale(domain=[0, max(3.0, float(df["days"].max()) * 1.25)])))
    bars = base.mark_bar(cornerRadiusEnd=4, height=18).encode(
        color=alt.Color("status:N", scale=alt.Scale(domain=["Current", "Behind"], range=[brand.LAGOON, brand.AMBER]), legend=None),
        tooltip=["source:N", alt.Tooltip("days:Q", format=".1f", title="Days behind"), "status:N"])
    text = base.mark_text(align="left", dx=6, color=brand.INK, fontSize=12).encode(text="label:N")
    return (bars + text + _rule(x=window_days, label="24-hour window")).properties(height=46 * len(df))

"""Look and small HTML building blocks shared by the Streamlit pages (matches the approved mockup)."""
from __future__ import annotations

from html import escape

import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&family=Newsreader:opsz,wght@6..72,400;6..72,500&display=swap');
:root { --ink:#14213d; --ink-soft:#46516b; --muted:#7b8499; --line:#e2e6ee; --card:#fff; --brand:#2f5bd3; --brand-dark:#2346a8;
  --brand-soft:#e9eefc; --risk:#b42318; --risk-soft:#fdecea; --warn:#a15c07; --warn-soft:#fff3df; --good:#157347; --good-soft:#e6f4ec;
  --mono:"IBM Plex Mono", ui-monospace, Menlo, monospace; --display:"Newsreader", Georgia, serif; }
h1 { font-weight: 500 !important; letter-spacing: -.5px; }
h2, h3 { font-weight: 500 !important; }
.block-container { padding-top: 2.2rem; max-width: 1320px; }
.dp-eyebrow { color: var(--brand); font-size: 11px; font-weight: 600; letter-spacing: 1.6px; text-transform: uppercase; }
.dp-lead { color: var(--ink-soft); font-size: 15px; line-height: 1.55; max-width: 70ch; margin: 0 0 6px; }
.dp-note { color: var(--muted); font-size: 12px; line-height: 1.5; }
.dp-mono { font-family: var(--mono); font-variant-numeric: tabular-nums; }
.dp-card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 16px 18px; box-shadow: 0 6px 22px rgba(20,33,61,.05); }
.dp-kpi { display: grid; gap: 4px; }
.dp-kpi .label { color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: .8px; text-transform: uppercase; }
.dp-kpi .value { font: 500 26px/1.1 var(--mono); }
.dp-kpi .sub { color: var(--ink-soft); font-size: 12px; }
.dp-kpi.risk { box-shadow: inset 4px 0 0 var(--risk); border-color: #f3c7c2; }
.dp-kpi.risk .value { color: var(--risk); }
.dp-pill { display: inline-flex; align-items: center; padding: 3px 9px; border-radius: 999px; font-size: 11.5px; font-weight: 600; white-space: nowrap; }
.dp-pill.risk { background: var(--risk-soft); color: var(--risk); } .dp-pill.warn { background: var(--warn-soft); color: var(--warn); }
.dp-pill.good { background: var(--good-soft); color: var(--good); } .dp-pill.quiet { background: #f0f2f6; color: var(--ink-soft); font-weight: 500; }
.dp-pill.commit { background: #e8edfb; color: var(--brand-dark); } .dp-pill.best { background: #eef0f5; color: var(--ink-soft); }
.dp-pill.pipeline { background: #f2f3f6; color: var(--muted); }
.dp-facts { display: flex; gap: 8px; flex-wrap: wrap; margin: 6px 0 14px; }
.dp-fact { display: inline-flex; gap: 6px; align-items: baseline; padding: 5px 10px; border: 1px solid var(--line); border-radius: 8px; background: #fff; font-size: 12.5px; }
.dp-fact span { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .6px; }
.dp-score { display: flex; align-items: baseline; gap: 12px; margin: 6px 0; }
.dp-score .value { font: 500 46px/1 var(--mono); }
.dp-score.flagged .value { color: var(--risk); }
.dp-score .vs { color: var(--muted); font-size: 13px; line-height: 1.3; }
.dp-driver { display: grid; grid-template-columns: minmax(0,1fr) 96px; gap: 10px; align-items: center; font-size: 13px; margin: 6px 0; }
.dp-bar { position: relative; height: 10px; background: linear-gradient(90deg, transparent calc(50% - .5px), #cfd5e2 calc(50% - .5px), #cfd5e2 calc(50% + .5px), transparent calc(50% + .5px)); }
.dp-bar span { position: absolute; top: 0; height: 10px; border-radius: 3px; }
.dp-bar .down { right: 50%; background: var(--risk); } .dp-bar .up { left: 50%; background: var(--good); }
.dp-list { list-style: none; margin: 0 0 8px; padding: 0; display: grid; gap: 9px; }
.dp-list li { padding: 10px 12px; border: 1px solid var(--line); border-radius: 10px; line-height: 1.5; background: #fff; }
.dp-list.risks li { box-shadow: inset 3px 0 0 var(--risk); } .dp-list.steps li { box-shadow: inset 3px 0 0 var(--brand); }
.dp-list.strengths li { box-shadow: inset 3px 0 0 var(--good); }
.dp-meta { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; color: var(--muted); font-size: 11.5px; margin-top: 4px; }
.dp-cite { border: 1px solid #c9d4f3; background: var(--brand-soft); color: var(--brand-dark) !important; border-radius: 6px; padding: 1px 7px; font: 500 11px var(--mono); text-decoration: none !important; }
.dp-cite.shared { border-color: #e1d3b5; background: #fbf5e8; color: #7a5a17 !important; }
.dp-trace { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.dp-trace li { display: grid; grid-template-columns: 18px 1fr; gap: 8px; font-size: 13px; line-height: 1.4; }
.dp-trace li::before { content: "✓"; color: var(--good); font-weight: 700; }
.dp-trace small { display: block; color: var(--muted); font-size: 11.5px; }
.dp-notice { padding: 12px 14px; border-radius: 10px; background: var(--warn-soft); color: #6b4105; border: 1px solid #f1d8a8; line-height: 1.5; }
.dp-notice.block { background: var(--risk-soft); color: #7a1a12; border-color: #f3c7c2; }
.dp-answer { padding: 12px 14px; border-radius: 10px; background: #f6f8fd; border: 1px solid #dfe6f8; line-height: 1.55; }
.dp-source { display: grid; gap: 8px; height: 100%; }
.dp-source.highlight { outline: 2px solid var(--brand); }
.dp-badge { font: 600 10.5px "IBM Plex Sans", sans-serif; letter-spacing: .8px; text-transform: uppercase; padding: 3px 8px; border-radius: 6px; background: #eef1f7; color: var(--ink-soft); }
.dp-badge.shared { background: #fbf5e8; color: #7a5a17; }
.dp-row { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.dp-mode { display: inline-flex; align-items: center; gap: 8px; padding: 6px 11px; border: 1px solid #33456f; border-radius: 999px; font-size: 10.5px; font-weight: 600; letter-spacing: 1px; color: #c8d1e6; }
.dp-mode i { width: 7px; height: 7px; border-radius: 50%; background: #f0b44c; display: inline-block; }
</style>
"""


def inject() -> None:
    # st.markdown (not st.html) so the styles apply to the whole page, including the fragments below.
    st.markdown(CSS, unsafe_allow_html=True)


def html(fragment: str) -> None:
    """Render trusted, app-built HTML (every value inside has been escaped with e())."""
    # Collapse newlines (markdown would treat indented lines as code) and encode $ (markdown renders $…$ as math).
    st.markdown(fragment.replace("\n", " ").replace("$", "&#36;"), unsafe_allow_html=True)


def e(value) -> str:
    return escape(str(value if value is not None else ""))


def page_head(eyebrow: str, title: str, lead: str = "") -> None:
    html(f'<div class="dp-eyebrow">{e(eyebrow)}</div>')
    st.title(title, anchor=False)
    if lead:
        html(f'<p class="dp-lead">{e(lead)}</p>')


def forecast_pill(forecast: str) -> str:
    cls = {"Commit": "commit", "Best Case": "best"}.get(forecast, "pipeline")
    return f'<span class="dp-pill {cls}">{e(forecast)}</span>'


def cite_chip(citation: str, deal_id: str, persona_id: str) -> str:
    shared = citation.startswith(("PB-", "PO-"))
    label = citation if shared else citation[-4:]
    href = f"sources?id={e(deal_id)}&as={e(persona_id)}&cite={e(citation)}"
    return f'<a class="dp-cite{" shared" if shared else ""}" href="{href}" target="_self" title="Open in Sources">{e(label)}</a>'

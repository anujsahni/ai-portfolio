"""Act 3: Transform and Trust. dbt models, tests and contracts; metrics defined once; Iceberg read by two engines."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from contextloop import config
from contextloop.ui import common

TARGET = Path(os.environ.get("DBT_TARGET_PATH", config.DBT_PROJECT_DIR / "target"))
LAYER_COLOR = {"source": "#EEF1F6", "staging": "#ECEEFD", "intermediate": "#E3F7F4", "marts": "#FFEFEA", "metric": "#E2F6EE"}


def _json(name: str) -> dict | None:
    p = TARGET / name
    return json.loads(p.read_text()) if p.exists() else None


def lineage_dot(focus: str = "fct_delivery") -> str:
    m = _json("manifest.json")
    sm = _json("semantic_manifest.json") or {"metrics": [], "semantic_models": []}
    parents = m["parent_map"]
    keep: set[str] = set()

    def up(node):
        for p in parents.get(node, []):
            if p not in keep and (p.startswith("model.") or p.startswith("source.")):
                keep.add(p)
                up(p)
    start = f"model.contextloop.{focus}"
    keep.add(start)
    up(start)
    layers: dict[str, list[str]] = {k: [] for k in LAYER_COLOR}
    for n in keep:
        if n.startswith("source."):
            layers["source"].append(n)
        else:
            name = n.split(".")[-1]
            layers["staging" if name.startswith("stg_") else "intermediate" if name.startswith("int_") else "marts"].append(n)
    model_of = {s["name"]: s["node_relation"]["alias"] for s in sm["semantic_models"]}
    measure_model = {ms["name"]: s["name"] for s in sm["semantic_models"] for ms in s.get("measures", [])}
    metric_edges = []
    for met in sm["metrics"]:
        meas = (met.get("type_params") or {}).get("measure") or {}
        sm_name = measure_model.get(meas.get("name")) if meas else None
        if sm_name and model_of.get(sm_name) == focus:
            metric_edges.append((f"model.contextloop.{focus}", f"metric.{met['name']}"))
            layers["metric"].append(f"metric.{met['name']}")
    shown = {n.split(".", 1)[1] for n in layers["metric"]}
    for met in sm["metrics"]:  # ratio and derived metrics built from the metrics already shown
        tp = met.get("type_params") or {}
        inputs = [x["name"] for x in (tp.get("metrics") or [])] + [x["name"] for x in (tp.get("numerator"), tp.get("denominator")) if x]
        if inputs and any(i in shown for i in inputs) and met["name"] not in shown:
            layers["metric"].append(f"metric.{met['name']}")
            metric_edges += [(f"metric.{i}", f"metric.{met['name']}") for i in inputs if i in shown]
    lines = ['digraph G { rankdir=LR; graph [fontname="Helvetica", fontsize=10, nodesep=0.15, ranksep=0.6]; '
             'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#C9D0DF", fontcolor="#18203A"]; '
             'edge [color="#8E98B0"];']
    for layer, nodes in layers.items():
        title = next(f"{name} · {plain.lower()}" for k, name, plain, *_ in LAYERS if k == layer)
        lines.append(f'subgraph cluster_{layer} {{ label="{title}"; style=dashed; color="#D6DCE8"; fontcolor="#5B6478";')
        for n in sorted(set(nodes)):
            label = n.split(".", 2)[-1] if n.startswith("source.") else n.split(".")[-1]
            lines.append(f'"{n}" [label="{label}", fillcolor="{LAYER_COLOR[layer]}"];')
        lines.append("}")
    for n in keep:
        for p in parents.get(n, []):
            if p in keep:
                lines.append(f'"{p}" -> "{n}";')
    lines += [f'"{a}" -> "{b}";' for a, b in metric_edges]
    return "\n".join(lines) + "}"


# The five layers, in plain words: what each is, what it does to one delivery on its way to the on-time rate, and what it fixes.
LAYERS = [
    ("source", "Source", "The raw copy",
     "The tables exactly as Fivetran landed them from SAP, Salesforce, Zendesk and the carrier database. Nothing is changed, so "
     "every later step can be checked against what the systems really hold.",
     "A delivery sits in SAP's <code>LIKP</code> table with cryptic columns (<code>WADAT</code>, <code>LFDAT</code>) and, if it was "
     "cancelled, <code>_fivetran_deleted = true</code>. Its real arrival time is in a different system: the carrier's events.",
     []),
    ("staging", "Staging", "Cleaned up, one table at a time",
     "One model per source table: rename cryptic columns, fix types and drop deleted rows. No business rules yet, so each "
     "model is easy to check against its source.",
     "<code>stg_sap__deliveries</code>: <code>WADAT</code> becomes <code>planned_goods_issue_date</code>, and cancelled "
     "deliveries are removed.",
     [("T1", "cancelled deliveries dropped")]),
    ("intermediate", "Intermediate", "Business rules, one named step each",
     "Where systems are joined and Northstar's rules are applied. Each rule lives in its own model with its own test, so when a "
     "number looks wrong you know exactly where to look.",
     "<code>int_delivery_actuals</code> takes the carrier's <i>delivered</i> event as the real arrival; "
     "<code>int_deliveries_enriched</code> marks the delivery on time or late against the date the customer asked for.",
     [("T2", "real delivery date"), ("T3", "euros converted to dollars"), ("T4", "duplicate account merged"),
      ("T5", "tier as it was at the time")]),
    ("marts", "Mart", "Ready-to-use tables",
     "One table per thing the business asks about: deliveries, revenue, tickets, accounts, the at-risk list. A contract fixes "
     "the columns and types, so tools and agents can rely on them.",
     "<code>fct_delivery</code>: one row per real delivery, with customer, requested date, delivered time and an "
     "<code>is_on_time</code> flag.",
     []),
    ("metric", "Metric", "The agreed number",
     "The business definition, written once in the semantic layer. Every dashboard and every agent computes it the same way, "
     "instead of each writing its own formula.",
     "<code>on_time_delivery_rate</code> = on-time deliveries ÷ deliveries over the last 90 days. In Act 4 the agent asks for "
     "this by name instead of guessing.",
     []),
]


TIP_CSS = """<style>
.cl-layers {display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin:.3rem 0 .4rem}
.cl-layer {position:relative; display:inline-flex; align-items:center; gap:7px; padding:7px 12px; border-radius:10px;
  border:1px solid #E3E7F0; font-size:.9rem; cursor:default}
.cl-layer b {font-weight:700} .cl-layer small {color:#5B6478}
.cl-layer .cl-i {display:inline-grid; place-items:center; width:17px; height:17px; border-radius:50%; border:1.5px solid #4B5BDC;
  color:#4B5BDC; font:700 11px/1 Georgia, serif; font-style:italic; cursor:help}
.cl-layer .cl-tip {display:none; position:absolute; top:calc(100% + 8px); left:0; z-index:1000; width:360px; padding:14px 16px;
  background:#fff; border:1px solid #E3E7F0; border-radius:12px; box-shadow:0 12px 32px rgba(24,32,58,.18);
  font-size:.86rem; line-height:1.5; color:#18203A; white-space:normal}
.cl-layer.right .cl-tip {left:auto; right:0}
.cl-layer .cl-i:hover + .cl-tip, .cl-layer .cl-tip:hover {display:block}
.cl-tip h5 {margin:0 0 .2rem; font-size:.95rem} .cl-tip .plain {font-weight:600; margin-bottom:.4rem}
.cl-tip code {font-size:.78rem}
.cl-arrow {color:#8E98B0}
</style>"""


def _tip(inner: str, right: bool = False, label: str = "", bg: str = "#FFFFFF") -> str:
    return (f'<span class="cl-layer{" right" if right else ""}" style="background:{bg}">{label}'
            f'<span class="cl-i" title="">i</span><span class="cl-tip">{inner}</span></span>')


def layers_explainer(n_test: int | None) -> None:
    st.subheader("How raw data becomes a number you can trust")
    st.markdown("dbt builds the trusted data in **layers**, each reading only from the one before it. Every Act 1 trap is fixed in "
                "one named place" + (f" and checked by {n_test} tests on every build" if n_test else "") +
                ". Hover the **ⓘ** on a layer to follow one delivery through it.")
    chips = []
    for i, (key, name, plain, what, example, fixes) in enumerate(LAYERS):
        traps = " ".join(t for t, _ in fixes)
        fixed = ("<div style='margin-top:.5rem'>" + "".join(common.badge(f"{t} · {d}", "ok", "check") for t, d in fixes)
                 + "</div>") if fixes else ""
        inner = (f"<h5>{name}</h5><div class='plain'>{plain}</div>{what}"
                 f"<div style='margin-top:.5rem'><b>One delivery:</b> {example}</div>{fixed}")
        label = f"<b>{name}</b>" + (f" {common.badge('fixes ' + traps, 'ok')}" if traps else "")
        chips.append(_tip(inner, right=i >= 3, label=label, bg=LAYER_COLOR[key]))
    why = _tip("<h5>Why layers?</h5>Each step is small enough to test. A broken rule fails a named test instead of quietly "
               "changing a number, and anyone (or any agent) can trace a metric back to the raw rows it came from.",
               right=True, label="<small>Why layers?</small>")
    st.markdown(TIP_CSS + '<div class="cl-layers">' + ' <span class="cl-arrow">→</span> '.join(chips) + f" {why}</div>",
                unsafe_allow_html=True)


def test_results() -> pd.DataFrame:
    rr = _json("run_results.json")
    if not rr:
        return pd.DataFrame()
    rows = [{"node": r["unique_id"].split(".")[2], "type": r["unique_id"].split(".")[0], "status": r["status"]} for r in rr["results"]]
    return pd.DataFrame(rows)


def render() -> None:
    common.header("Act 3", "Transform and trust", "dbt turns raw tables into one tested model, the semantic layer defines each "
                  "number once, and the trusted tables are stored as Iceberg so any engine reads the same data.")
    if not common.require_warehouse() or not _json("manifest.json"):
        st.warning("Run `make build` to create the dbt models.")
        return
    tests = test_results()
    n_test = None
    if not tests.empty:
        counts = tests.groupby(["type", "status"]).size().reset_index(name="n")
        n_test = int(counts[counts.type == "test"]["n"].sum())
        n_fail = int(counts[(counts.type == "test") & (counts.status.isin(["fail", "error"]))]["n"].sum())
        n_model = int(counts[counts.type == "model"]["n"].sum())
        a, b, c = st.columns(3)
        a.metric("Models built", n_model)
        b.metric("Tests run", n_test)
        c.metric("Tests failing", n_fail, delta=None if n_fail == 0 else "broken", delta_color="inverse")

    layers_explainer(n_test)

    st.subheader("Lineage: from four sources to one governed metric")
    st.caption("The real models behind one mart, layer by layer (left to right). Pick a mart to see what it is built from.")
    focus = st.radio("Mart", ["fct_delivery", "account_risk", "fct_revenue", "fct_ticket"], horizontal=True, key="act3-focus")
    st.graphviz_chart(lineage_dot(focus), use_container_width=True)

    st.subheader("Break it")
    st.caption("Removes the handling of trap T1 (cancelled deliveries) from the dbt project for one build, so a named test fails "
               "live; then restores the trusted build.")
    if st.button("Break it, then restore", type="primary", icon=":material/build:"):
        code, out = common.run_job(["build", "--break", "T1"], "dbt build with trap T1 re-introduced")
        failed = next((ln.split(":", 1)[1] for ln in out.splitlines() if ln.startswith("Failing tests")), "")
        st.error(f"Failing tests with T1 broken: {failed.strip() or 'see the log above'}")
        common.run_job(["build"], "Restoring the trusted build")
        st.success("Restored: every test passes again.")

    st.subheader("Metrics, defined once")
    sm = _json("semantic_manifest.json")
    if sm:
        st.dataframe(pd.DataFrame([{"metric": m["name"], "label": m.get("label"), "type": m["type"],
                                    "definition": " ".join((m.get("description") or "").split())} for m in sm["metrics"]]),
                     hide_index=True, use_container_width=True)

    st.subheader("Open lakehouse: the same Iceberg table, two engines")
    if st.button("Run the at-risk query on DuckDB and Trino", icon=":material/compare_arrows:"):
        from contextloop.lakehouse import compare
        from contextloop.lakehouse.publish import history, location

        loc = location()
        a, b = st.columns(2)
        try:
            d = compare._norm(compare.via_duckdb())
            a.markdown(f"**DuckDB** · iceberg extension · snapshot `{loc['snapshot_id']}`")
            a.dataframe(pd.DataFrame(d, columns=["customer_id", "account", "on_time", "tickets", "renewal"]), hide_index=True)
        except Exception as exc:  # noqa: BLE001
            a.error(f"DuckDB could not read the table: {exc}")
            d = None
        try:
            t = compare._norm(compare.via_trino(timeout=30))
            b.markdown("**Trino** · Iceberg connector · same REST catalog")
            b.dataframe(pd.DataFrame(t, columns=["customer_id", "account", "on_time", "tickets", "renewal"]), hide_index=True)
            if d is not None:
                st.markdown(common.badge("Identical results", "ok", "check") if d == t else common.badge("Results differ", "bad", "close"),
                            unsafe_allow_html=True)
        except Exception:  # noqa: BLE001
            b.info("Trino isn't running. Start it with `make lakehouse` (it's optional).")
        st.caption(f"Storage: `{loc['location']}` (RustFS console: http://127.0.0.1:9001)")
        hist = pd.DataFrame(history())
        hist["published"] = hist["timestamp_ms"].map(lambda ms: datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%d %b %H:%M:%S"))
        st.caption("Snapshot history of northstar.marts.account_risk (one snapshot per build):")
        st.dataframe(hist[["snapshot_id", "published", "total_records"]], hide_index=True)
    with st.expander("Go deeper: how each trap is handled"):
        st.markdown("| Trap | Handled in | Guarded by |\n|---|---|---|\n"
                    "| T1 deleted rows | every `stg_sap__*` model | `no_deleted_rows` test |\n"
                    "| T2 wrong date | `int_delivery_actuals` | truth comparison |\n"
                    "| T3 currency | `int_exchange_rates_monthly`, `fct_revenue` | `assert_all_revenue_converted_to_usd` |\n"
                    "| T4 duplicate account | `int_account_identity` | `assert_every_ticket_has_a_customer` |\n"
                    "| T5 tier history | `int_account_tier_history` | one active row; no overlaps |\n"
                    "| T6 stale data | source freshness | `zendesk: error` |")
    common.nav_buttons("act3")

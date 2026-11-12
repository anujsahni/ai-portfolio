"""The architecture page: the narrated pitch video (CL-18), then the interactive architecture, embedded with its CSS and JavaScript
inlined (the same file opens on its own too)."""
from __future__ import annotations

import re
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from contextloop import config

HERE = Path(__file__).resolve().parents[1] / "architecture"
VIDEO = Path(__file__).resolve().parents[1] / "assets" / "video"
PITCH = VIDEO / "contextloop-pitch.mp4"
CAPTIONS = VIDEO / "contextloop-pitch.vtt"


def inlined() -> str:
    html = (HERE / "index.html").read_text()
    html = html.replace('<link rel="stylesheet" href="architecture.css">', f"<style>{(HERE / 'architecture.css').read_text()}</style>")
    return html.replace('<script src="architecture.js"></script>', f"<script>{(HERE / 'architecture.js').read_text()}</script>")


ADDS = {1: "where we start: the sources, a raw copy and the agent", 2: "Move", 3: "Transform and trust", 4: "Context",
        5: "Activate, which completes the loop"}


def act_diagram(act: int) -> None:
    """The architecture as it stands after `act`: earlier acts' boxes built, this act's marked NEW, later ones ghosted."""
    label = ("Architecture at Act 1: where we start (the sources, a raw copy and the agent)" if act == 1
             else f"Architecture after Act {act}: what this act relies on, and what it adds ({ADDS[act]})" if act < 5
             else "The complete architecture: Act 5 adds Activate, which completes the loop")
    with st.expander(label, icon=":material/schema:"):
        html = inlined().replace("<script>", f"<script>window.__ARCH_INIT = {{build: {act}, embed: true}};</script><script>", 1)
        components.html(html, height=700, scrolling=True)
        st.caption("Solid boxes are built by this act or an earlier one; boxes marked NEW arrive in this act; faded ones come later. "
                   "Step through the whole build-up on the Architecture page (Build it up).")


def pitch_minutes() -> int | None:
    """Length of the pitch in whole minutes, from the end of the last caption."""
    if not CAPTIONS.exists():
        return None
    ends = re.findall(r"--> (\d+):(\d+):([\d.]+)", CAPTIONS.read_text())
    if not ends:
        return None
    h, m, s = ends[-1]
    return max(1, round((int(h) * 3600 + int(m) * 60 + float(s)) / 60))


def has_pitch() -> bool:
    return bool(config.PITCH_VIDEO_URL) or PITCH.exists()


def _video(autoplay: bool = False) -> None:
    """The hosted pitch when there is a link (CloudFront, or YouTube with its own captions), else the locally rendered copy."""
    url = config.PITCH_VIDEO_URL
    if url and ("youtube.com" in url or "youtu.be" in url):
        st.video(url, autoplay=autoplay)
    elif url:
        st.video(url, subtitles={"English": str(CAPTIONS)} if CAPTIONS.exists() else None, autoplay=autoplay)
    else:
        st.video(str(PITCH), subtitles={"English": str(CAPTIONS)} if CAPTIONS.exists() else None, autoplay=autoplay)


def _blurb() -> str:
    minutes = pitch_minutes()
    return (f"A narrated brief{f' of about {minutes} minutes' if minutes else ''}: the problem, the solution, then each act walked "
            "through on the architecture diagram. Captions are available from the player.")


# What each technology is, and exactly how this demo uses it: (technology, what it is, how it is used here).
STACK = {
    "Transform & trust": (
        "Raw tables landed by Fivetran → `dbt build` (models and tests) → marts in DuckDB → semantic layer metrics → "
        "Iceberg snapshot → read by DuckDB and Trino.",
        [("DuckDB", "Warehouse: an embedded analytical database in one file, with no server.",
          "`dbt build` writes every model into `warehouse.db` (raw → staging → marts). Act 1's naive agent runs `run_sql` on the raw "
          "schemas. The services open `serving.db`, a read-only copy swapped in after each build."),
         ("dbt Core", "Transformation: SQL models with tests, contracts, docs and lineage, run as code.",
          "`make build` runs `dbt build` with dbt-duckdb: 16 staging, 5 intermediate and 6 mart models. Each trap is fixed in a named "
          "model (`int_delivery_actuals` for T2, `int_account_identity` for T4, `int_exchange_rates_monthly` for T3) and guarded by a "
          "test. Marts have enforced contracts. `make break TRAP=T1` makes a named test fail live."),
         ("Semantic layer (MetricFlow)", "Metrics defined once in YAML. MetricFlow generates the SQL, so nobody rewrites the logic.",
          "`semantic_models.yml` defines five semantic models and nine metrics, such as `on_time_delivery_rate`, `net_revenue` and "
          "`at_risk_strategic_accounts`. The metrics MCP server calls `mf query --explain`, then runs the compiled SQL read-only."),
         ("Apache Iceberg", "Open table format: Parquet files plus metadata and snapshots, registered in a catalog any engine can read.",
          "After each build, PyIceberg publishes the six marts to `northstar.marts` through the Iceberg REST catalog. The files land in "
          "a RustFS (S3-compatible) bucket, and every build adds a new snapshot."),
         ("Trino", "A distributed SQL engine that reads Iceberg through its connector.",
          "`make lakehouse` asks the at-risk question twice against the same Iceberg table: once through DuckDB's iceberg extension and "
          "once through Trino. Act 3 shows that both return the same rows.")]),
    "Context · MCP": (
        "COO's question → `list_metrics` → `check_freshness` → `query_metric` → dbt lineage → an answer with its definitions and "
        "a freshness warning.",
        [("MCP (Model Context Protocol)", "An open standard for giving an agent tools and context through one interface.",
          "Three MCP servers run in private containers and speak streamable HTTP. The agent sees only their tools, not the "
          "warehouse."),
         ("dbt MCP server", "The official `dbt-mcp` server from dbt Labs.",
          "Only the read-only project tools are on: `list`, `get_node_details_dev` and `get_lineage_dev`. They read the manifest "
          "from the latest build. The build, run and SQL tools are off."),
         ("Metrics MCP server", "A small MCP server (Python MCP SDK) in front of the semantic layer.",
          "`list_metrics` returns the definitions, the dimensions and the filter syntax. `query_metric` has MetricFlow compile the "
          "SQL and returns it with up to 200 rows, so every number can be traced."),
         ("Freshness MCP server", "A small MCP server in front of the Fivetran sync log.",
          "`check_freshness` reports the last successful sync, its age, row counts and errors for each source, checked against a "
          "24-hour window. Zendesk is held two days behind, so the agent has to say so."),
         ("Claude + bridge", "The agent. It is the same model as in Act 1; only its context is different.",
          "`mcp_bridge.py` connects to the three servers with the Python MCP client, hands their tools to Claude's tool use and "
          "routes each call. The agent never touches the raw tables.")]),
    "Activate": (
        "`marts.account_risk` → compare with the CRM → dry run → write only the changes → Salesforce record and Slack summary.",
        [("Reverse ETL sync", "Pushes governed data from the warehouse back into business tools.",
          "`activation/sync.py` reads `marts.account_risk` and compares four risk fields with the CRM. It shows a dry run, then "
          "writes only the differences, so a second run changes nothing. Next steps come from the agent's answer (AI-drafted) or "
          "from the dbt playbook rule."),
         ("Mock Salesforce", "A small FastAPI stand-in for a Salesforce org.",
          "Each at-risk account gets `Delivery_Risk__c`, `Delivery_Risk_Drivers__c`, `Next_Step__c` and `Next_Step_Source__c`. "
          "Every write is recorded in an audit log, which Act 5 shows."),
         ("Slack", "An incoming webhook to the account team's channel.",
          "When `SLACK_WEBHOOK_URL` is set, the sync posts one summary message. Without it, Act 5 shows a preview and makes no network "
          "call."),
         ("Fivetran Activations (at a customer)", "Managed, audited reverse ETL from governed models to business tools.",
          "Replaces the custom sync code. The source of truth stays the same dbt mart.")]),
}


def stack_explained() -> None:
    """What each technology in Transform & trust, Context and Activate does, and how this demo uses it."""
    st.markdown("##### What each technology does, and how this demo uses it")
    for tab, (flow, rows) in zip(st.tabs(list(STACK)), STACK.values()):
        with tab:
            st.caption(f"**Flow:** {flow}")
            for name, what, use in rows:
                left, right = st.columns([1, 3])
                left.markdown(f"**{name}**")
                right.markdown(f"{what}  \n:gray[**In this demo:** {use}]")


@st.dialog("Watch the pitch", width="large")
def _pitch_dialog() -> None:
    _video(autoplay=True)  # opened by a click, so the browser lets it start with sound
    st.caption(_blurb())


def render() -> None:
    head, button = st.columns([4, 1], vertical_alignment="bottom")
    head.markdown("#### Architecture")
    if has_pitch() and button.button("Watch the pitch", icon=":material/play_circle:", type="primary", width="stretch",
                                        help="Play the narrated pitch video in a pop-up"):
        _pitch_dialog()
    st.caption("Hover a box for details, click to pin it, use ← and → to step through the acts, and switch between this laptop and "
               "a customer deployment.")
    components.html(inlined(), height=900, scrolling=True)

    stack_explained()

    st.divider()
    st.markdown("##### Watch the pitch")
    if has_pitch():
        st.caption(_blurb())
        _, mid, _ = st.columns([1, 10, 1])
        with mid:
            _video()
        if config.PITCH_PAGE_URL:
            st.markdown(f":material/share: **Share with a customer:** [{config.PITCH_PAGE_URL}]({config.PITCH_PAGE_URL}) "
                        "· a public watch page with captions; anyone with the link can view it.")
    else:
        st.caption("The pitch video isn't published yet: run `make pitch-video`, then `make publish-pitch` on the host.")

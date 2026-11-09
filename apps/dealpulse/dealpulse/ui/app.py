"""DealPulse web app (Streamlit). Run from apps/dealpulse/: make run  →  http://localhost:8501

Five pages, each with its own address: / (Pipeline), /deal, /sources, /model, /architecture.
Data mode: DEALPULSE_DATA=offline (default) uses saved synthetic data and real scores from the trained
model, with no AWS calls. Live services replace it page by page (MVP-05, MVP-07, MVP-08).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from dealpulse.ui import state, theme  # noqa: E402

HERE = Path(__file__).resolve().parent

st.set_page_config(page_title="DealPulse", page_icon=str(ROOT / "artifacts/dealpulse-mockups/favicon.svg"), layout="wide")
theme.inject()

PAGES = {
    "Deal desk": [
        st.Page(HERE / "views/pipeline.py", title="Pipeline", icon=":material/table_rows:", url_path="pipeline", default=True),
        st.Page(HERE / "views/deal.py", title="Deal brief", icon=":material/track_changes:", url_path="deal"),
        st.Page(HERE / "views/sources.py", title="Sources", icon=":material/format_quote:", url_path="sources"),
    ],
    "Under the hood": [
        st.Page(HERE / "views/model.py", title="Model", icon=":material/monitoring:", url_path="model"),
        st.Page(HERE / "views/architecture.py", title="Architecture", icon=":material/account_tree:", url_path="architecture"),
    ],
}
nav = st.navigation(PAGES)

data = state.data()
current = state.persona()
with st.sidebar:
    st.html('<div style="font-size:19px;font-weight:700;color:#fff;letter-spacing:-.4px">Deal<span style="color:#7aa2ff">Pulse</span></div>')
    ids = [p.id for p in data.personas]
    chosen = st.selectbox("Viewing as", ids, index=ids.index(current.id),
                          format_func=lambda pid: data.persona(pid).label + (" (manager)" if data.persona(pid).manager else ""),
                          help="Simulated sign-in. Managers see their team's deals; account executives see only their own.")
    if chosen != current.id:
        state.set_persona(chosen)
        st.rerun()
    st.caption(f"{'Sees the ' + current.team + ' team' if current.manager else 'Sees only their own'} deals · simulated sign-in")
    st.html('<span class="dp-mode"><i></i>OFFLINE · SAVED DATA · NO AWS</span>')
    st.caption(f"Snapshot {data.snapshot_date}. Fictional companies and people. DealPulse never writes to the CRM.")

nav.run()

"""ContextLoop: the Streamlit app. A story navigator through five acts, the architecture page and the POV scorecard."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from contextloop import config
from contextloop.ui import common
from contextloop.ui.brand import PAGE_ICONS
from contextloop.ui.pages import act1, act2, act3, act4, act5, architecture, compare, home, scorecard

ASSETS = Path(__file__).resolve().parent / "assets"

st.set_page_config(page_title="ContextLoop", page_icon=str(ASSETS / "favicon.png"), layout="wide", initial_sidebar_state="expanded")
st.logo(str(ASSETS / "logo.png"), icon_image=str(ASSETS / "mark.png"), size="large")

SPEC = [
    ("home", home.render, "Northstar and the question", "home"),
    ("act1", act1.render, "1 · The confident wrong answer", "act-1"),
    ("act2", act2.render, "2 · Move", "act-2"),
    ("act3", act3.render, "3 · Transform and trust", "act-3"),
    ("act4", act4.render, "4 · Context", "act-4"),
    ("act5", act5.render, "5 · Activate", "act-5"),
    ("compare", compare.render, "The difference: without vs with", "difference"),
    ("scorecard", scorecard.render, "Proof-of-value scorecard", "scorecard"),
    ("architecture", architecture.render, "Architecture", "architecture"),
]
PAGES = {key: st.Page(fn, title=title, icon=PAGE_ICONS[key], url_path=path, default=key == "home") for key, fn, title, path in SPEC}
st.session_state["_pages"] = PAGES

nav = st.navigation({"The story": [PAGES[k] for k in common.STORY], "Reference": [PAGES["architecture"]]})

with st.sidebar:
    st.caption("Your AI agent is only as good as your data.")
    if "mode" not in st.session_state:
        st.session_state["mode"] = "live" if config.MODE == "live" and common.has_key() else "replay"
    live = st.toggle("Live mode (call Claude now)", value=st.session_state["mode"] == "live", disabled=not common.has_key(),
                     help="Replay plays recorded, scored runs and needs no network. Live calls Claude with your API key.")
    st.session_state["mode"] = "live" if live else "replay"
    st.markdown(common.CSS + (common.badge("Live · calling Claude", "warn", "bolt") if live
                              else common.badge("Replay · recorded runs", "info", "record")), unsafe_allow_html=True)
    if not common.has_key():
        st.caption("No API key in `.env`, so live mode is off.")
    st.divider()
    st.caption("**Synthetic demo data.** Northstar Industrial and every account, order and ticket are invented. "
               "Nothing here touches a real SAP, Salesforce, Zendesk or Slack system.")

nav.run()

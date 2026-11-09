"""Architecture: the interactive service map, embedded from dealpulse/ui/architecture/ (the same files as the mockup)."""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from dealpulse.ui import state

state.persona()
ARCH = Path(__file__).resolve().parents[1] / "architecture"


@st.cache_data
def page_html() -> str:
    html = (ARCH / "index.html").read_text()
    html = html.replace('<link rel="stylesheet" href="architecture.css" />', f"<style>{(ARCH / 'architecture.css').read_text()}</style>")
    html = html.replace('<script src="architecture.js"></script>', f"<script>{(ARCH / 'architecture.js').read_text()}</script>")
    return html


components.html(page_html(), height=1560, scrolling=True)
st.caption("Hover a service for what it does; click to pin. Click inside the diagram, then use ← and → to walk through a deal review.")

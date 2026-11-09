"""Who is viewing and which deal is open, kept in the URL (?as=…&id=…) so links and reloads keep them."""
from __future__ import annotations

import streamlit as st

from dealpulse.ui import logic


def data() -> logic.OfflineData:
    return logic.load()


def persona() -> logic.Persona:
    d = data()
    pid = st.query_params.get("as") or st.session_state.get("persona_id")
    p = d.persona(pid)
    st.session_state["persona_id"] = p.id
    if st.query_params.get("as") != p.id:
        st.query_params["as"] = p.id
    return p


def set_persona(persona_id: str) -> None:
    st.session_state["persona_id"] = persona_id
    st.query_params["as"] = persona_id


def deal_id() -> str:
    did = st.query_params.get("id") or st.session_state.get("deal_id") or logic.FEATURED_DEAL
    st.session_state["deal_id"] = did
    if st.query_params.get("id") != did:
        st.query_params["id"] = did
    return did


def params(**extra) -> dict:
    """Query parameters to carry to another page."""
    out = {"as": st.session_state.get("persona_id", data().default_persona().id)}
    if st.session_state.get("deal_id"):
        out["id"] = st.session_state["deal_id"]
    out.update({k: v for k, v in extra.items() if v})
    return out

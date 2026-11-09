"""Sources: every record the brief cites, shown from the records themselves (never from model text)."""
import streamlit as st

from dealpulse.ui import logic, state, theme
from dealpulse.ui.theme import e

data = state.data()
persona = state.persona()
deal = data.deal(state.deal_id()) or data.deal(logic.FEATURED_DEAL)
highlight = st.query_params.get("cite")

if not logic.can_see(persona, deal):
    st.title("Sources", anchor=False)
    theme.html(f'<div class="dp-notice block">{e(persona.name)} can\'t view this deal\'s sources.</div>')
    st.stop()

theme.page_head("Evidence behind the brief", f"Sources for {deal['account']}",
                "Every claim in the brief links to one of these. Deal notes come only from this opportunity; shared guidance "
                "is the same for every deal.")
st.page_link("views/deal.py", label="← Back to the brief", query_params={"id": deal["id"], "as": persona.id})

brief = data.briefs.get(deal["id"])
if not brief:
    theme.html('<div class="dp-notice">This deal has no sample brief in offline mode, so nothing is cited yet. '
               'Open Northbeam Logistics Group, Harborline Freight or Silverpine Retail Group from the Pipeline.</div>')
    st.stop()

uses = logic.citation_uses(brief)


def card(cid: str) -> str:
    cited = "".join(f'<span class="dp-pill quiet">{e(u)}</span>' for u in uses[cid])
    hl = " highlight" if cid == highlight else ""
    if logic.is_shared(cid):
        k = data.knowledge[cid]
        badge = "Playbook" if k["kind"] == "playbook" else "Pricing policy"
        text = k["text"][:420] + ("…" if len(k["text"]) > 420 else "")
        return (f'<div class="dp-card dp-source{hl}"><div class="dp-row"><span class="dp-badge shared">{badge}</span>'
                f'<span class="dp-mono dp-note">{e(cid)}</span></div><b>{e(k["title"])}</b><span>{e(text)}</span>'
                f'<div class="dp-meta">Cited in: {cited}</div></div>')
    n = data.note(cid)
    return (f'<div class="dp-card dp-source{hl}"><div class="dp-row"><span class="dp-badge">{e(n["type"])} note</span>'
            f'<span class="dp-mono dp-note">{e(cid)}</span></div><span>{e(n["text"])}</span>'
            f'<span class="dp-note">{e(n["date"])} · {e(n["author"])} · with {e(n["contact"])}, {e(n["contactTitle"])}</span>'
            f'<div class="dp-meta">Cited in: {cited}</div></div>')


for title, ids in (("This deal's notes", [c for c in uses if not logic.is_shared(c)]),
                   ("Shared guidance", [c for c in uses if logic.is_shared(c)])):
    st.subheader(f"{title} ({len(ids)})", anchor=False)
    for start in range(0, len(ids), 3):
        cols = st.columns(3)
        for col, cid in zip(cols, ids[start:start + 3]):
            with col:
                theme.html(card(cid))

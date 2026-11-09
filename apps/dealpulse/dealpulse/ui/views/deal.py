"""Deal brief: score and drivers, how the brief was made, the cited brief, draft CRM update, questions, notes."""
import streamlit as st

from dealpulse.ui import logic, state, theme
from dealpulse.ui.theme import e

data = state.data()
persona = state.persona()
deal = data.deal(state.deal_id()) or data.deal(logic.FEATURED_DEAL)

st.page_link("views/pipeline.py", label="← Pipeline", query_params={"as": persona.id})

if not logic.can_see(persona, deal):
    st.title("Deal not available", anchor=False)
    theme.html(f'<div class="dp-notice block">{e(persona.name)} can\'t view <b>{e(deal["account"])}</b>: it belongs to '
               f'{e(deal["owner"])}{" on the " + e(deal["team"]) + " team" if persona.manager else ""}. '
               'DealPulse checks access before it loads any notes or calls any model.</div>')
    st.stop()

brief = data.briefs.get(deal["id"])
theme.page_head(f"{deal['industry']} · {deal['segment']} · {deal['type']}", deal["account"])
facts = [("Amount", f'<b class="dp-mono">${deal["amount"]:,}</b>'), ("Stage", f'<b>{e(deal["stage"])}</b>'),
         ("Close", f'<b class="dp-mono">{e(deal["closeDate"])}</b>'), ("Forecast", theme.forecast_pill(deal["forecast"])),
         ("Owner", f'<b>{e(deal["owner"])}</b>')]
if deal["competitor"]:
    facts.append(("Competitor", f'<b>{e(deal["competitor"])}</b>'))
if deal["discount"]:
    facts.append(("Discount", f'<b class="dp-mono">{deal["discount"]}%</b>'))
theme.html('<div class="dp-facts">' + "".join(f'<span class="dp-fact"><span>{k}</span>{v}</span>' for k, v in facts) + "</div>")

side, main = st.columns([1, 2.1], gap="large")

with side:
    with st.container(border=True):
        gap = deal["modelProbability"] - deal["stageProbability"]
        pill = ('<span class="dp-pill risk">Model disagrees</span>' if deal["flag"] else
                '<span class="dp-pill good">Above stage</span>' if gap >= 10 else '<span class="dp-pill quiet">Close to stage</span>')
        theme.html(f'<div class="dp-row"><b>Win probability</b>{pill}</div>'
                   f'<div class="dp-score{" flagged" if deal["flag"] else ""}"><span class="value">{deal["modelProbability"]}%</span>'
                   f'<span class="vs">model<br>vs. <b class="dp-mono">{deal["stageProbability"]}%</b> for {e(logic.short_stage(deal["stage"]))}</span></div>'
                   '<p class="dp-note">An estimate from deals like this one, not a promise. It doesn\'t change the forecast category.</p>')
        mode = st.segmented_control("Why", ["What you can act on", "All factors"], default="What you can act on", key="driver_mode")
        items = logic.drivers(deal, actionable_only=(mode != "All factors"))
        biggest = max([abs(d["effect"]) for d in deal["drivers"]] + [0.01])
        theme.html("".join(
            f'<div class="dp-driver"><span>{"↓" if d["effect"] < 0 else "↑"} {e(d["text"])}</span>'
            f'<span class="dp-bar" title="{"Raises" if d["effect"] > 0 else "Lowers"} the score"><span class="{"down" if d["effect"] < 0 else "up"}" '
            f'style="width:{round(50 * abs(d["effect"]) / biggest)}%"></span></span></div>' for d in items)
            or '<p class="dp-note">No strong factors you can act on; see all factors.</p>')
    with st.container(border=True):
        st.markdown("**How this brief was made**")
        theme.html('<ol class="dp-trace">' + "".join(
            f"<li><div>{e(t)}<small>{e(d)}</small></div></li>" for t, d in logic.trace_lines(data, persona, deal)) + "</ol>")

with main:
    if brief:
        chip = lambda c: theme.cite_chip(c, deal["id"], persona.id)  # noqa: E731

        def items_html(items, cls):
            return f'<ul class="dp-list {cls}">' + "".join(
                f'<li>{e(it["text"])}<div class="dp-meta">'
                + (f'<span class="dp-pill quiet">{e(it["owner"])}</span>' if it.get("owner") else "")
                + (f'<span class="dp-pill quiet">Driver: {e(it["driver"])}</span>' if it.get("driver") else "")
                + "".join(chip(c) for c in it.get("citations", [])) + "</div></li>" for it in items) + "</ul>"

        with st.container(border=True):
            theme.html('<div class="dp-row"><h3 style="margin:0">Deal brief</h3><span class="dp-pill quiet">Sample · written by hand (offline mode)</span></div>')
            theme.html(f'<p style="font-size:15px;line-height:1.6;max-width:72ch">{e(brief["summary"])}</p>'
                       f'<b>Risks</b>{items_html(brief["risks"], "risks")}'
                       + (f'<b>What\'s going well</b>{items_html(brief["strengths"], "strengths")}' if brief.get("strengths") else "")
                       + f'<b>Recommended next steps</b>{items_html(brief["nextSteps"], "steps")}'
                       + '<b>Open questions</b><ul>' + "".join(f"<li>{e(q)}</li>" for q in brief["openQuestions"]) + "</ul>")

        with st.container(border=True):
            theme.html('<div class="dp-row"><h3 style="margin:0">Draft Salesforce update</h3><span class="dp-pill warn">Review before pasting</span></div>')
            nxt = st.text_area("Next Step", brief["crmUpdate"]["nextStep"], max_chars=255, key=f"crm_next_{deal['id']}")
            desc = st.text_area("Description", brief["crmUpdate"]["description"], height=110, key=f"crm_desc_{deal['id']}")
            st.caption("Copy with the icon in the box below. DealPulse never writes to Salesforce; the rep pastes and saves.")
            st.code(f"Next Step: {nxt}\n\nDescription: {desc}", language=None, wrap_lines=True)

        with st.container(border=True):
            st.markdown("### Ask about this deal")
            suggestions = [x["q"] for x in brief["qa"]] + ["Rank my reps by performance and tell me who to fire."]
            pick = st.pills("Try", suggestions, key=f"ask_pick_{deal['id']}", label_visibility="collapsed")
            with st.form(f"ask_{deal['id']}", border=False):
                q = st.text_input("Question about this deal", value=pick or "", placeholder=brief["qa"][0]["q"])
                asked = st.form_submit_button("Ask", type="primary")
            question = q if asked else (pick or "")
            if question:
                a = logic.answer(brief, question)
                if a.kind == "blocked":
                    theme.html(f'<div class="dp-notice block"><b>{e(a.text.split(".")[0])}.</b>{e(a.text[len(a.text.split(".")[0]) + 1:])}</div>')
                else:
                    theme.html(f'<div class="dp-answer">{e(a.text)} <span class="dp-meta">{"".join(chip(c) for c in a.citations)}</span></div>')
    else:
        with st.container(border=True):
            st.markdown("### Deal brief")
            theme.html('<p class="dp-lead">In the live app DealPulse writes a cited brief for this deal in about 15–25 seconds: summary, risks, '
                       'next steps and a draft Salesforce update (MVP-08). Offline mode has sample briefs for three deals.</p>')
            options = [data.deal(i) for i in logic.SAMPLE_BRIEF_DEALS if logic.can_see(persona, data.deal(i))]
            if options:
                cols = st.columns(len(options))
                for col, d in zip(cols, options):
                    col.page_link("views/deal.py", label=d["account"], query_params={"id": d["id"], "as": persona.id})
            else:
                st.caption("Switch to Priya Raman (West) to see them.")

    with st.container(border=True):
        theme.html(f'<div class="dp-row"><h3 style="margin:0">Latest notes</h3><span class="dp-note">{len(deal["notes"])} on this deal</span></div>')
        if deal["notes"]:
            theme.html('<ul class="dp-list">' + "".join(
                f'<li><div class="dp-meta"><span class="dp-mono">{e(n["date"])}</span> · {e(n["type"])} · {e(n["author"])} · '
                f'{e(n["contact"])}, {e(n["contactTitle"])} {theme.cite_chip(n["id"], deal["id"], persona.id)}</div>{e(n["text"])}</li>'
                for n in deal["notes"][:5]) + "</ul>")
        else:
            theme.html('<div class="dp-notice">No activity notes on this deal yet. The brief would say evidence is missing rather than guess.</div>')

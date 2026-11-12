"""Running or replaying an agent on a question, shared by Act 1 (naive) and Act 4 (governed)."""
from __future__ import annotations

import json

import streamlit as st

from contextloop.eval.score import score
from contextloop.ui import common


def question_picker(key: str) -> dict:
    qs = common.golden()
    labels = {q["id"]: f"{q['id']} · {q['question']}" for q in qs}
    qid = st.selectbox("Question", list(labels), format_func=labels.get, key=key, index=0)
    return next(q for q in qs if q["id"] == qid)


def get_trace(agent: str, q: dict, variant: str = "") -> dict | None:
    """The trace to show: this session's live run if there is one, else the recording."""
    live = st.session_state.get(f"live-{agent}-{q['id']}{variant}")
    return live or common.recording(agent, q["id"], variant)


def ask(agent: str, q: dict, steps_box, variant: str = "", env_note: str = "") -> dict | None:
    """Plays the recording (replay) or calls Claude (live), rendering tool calls as they happen."""
    if common.mode() == "live":
        from contextloop.agent import governed, naive

        st.session_state.pop(f"live-{agent}-{q['id']}{variant}", None)
        count = {"n": 0}
        with steps_box:
            live = st.empty()  # calls stream in here while the agent works; replaced by the staged story when it finishes
        live_box = live.container()

        def on_step(s):
            count["n"] += 1
            with live_box:
                with common.step_expander(count["n"], {"tool": s.tool, "input": s.input, "output": s.output,
                                                       "is_error": s.is_error}):
                    st.code(s.input.get("sql") or json.dumps(s.input, indent=1), language="sql" if "sql" in s.input else "json")
                    st.json(s.output, expanded=False)

        with st.spinner(f"The {agent} agent is working… (Claude, live{env_note})"):
            tr = (naive.answer if agent == "naive" else governed.answer)(q["id"], q["question"], on_step=on_step).to_dict()
        tr["score"] = score(q["id"], tr["answer"], common.truth())
        if agent == "naive":
            from contextloop.agent.explain import explain

            tr["explanation"] = explain(tr, common.truth(), common.traps())
        st.session_state[f"live-{agent}-{q['id']}{variant}"] = tr
        live.empty()
        common.play_steps(tr, steps_box, pace=0)
        return tr
    tr = common.recording(agent, q["id"], variant)
    if tr:
        common.play_steps(tr, steps_box)
    return tr


def show_score(tr: dict, q: dict) -> None:
    sc = score(q["id"], tr.get("answer"), common.truth())
    exp = sc.get("expected")
    detail = ""
    if q["id"] == "G1":
        detail = f" · named {len(sc.get('got') or [])}, {len(sc.get('extra', []))} wrong, missed {len(sc.get('missed', []))} of {len(exp)}"
    elif q["id"] != "G5":
        detail = f" · expected {exp:,} · got {sc.get('got')}"
    st.markdown(common.score_badge(sc) + f"<small>Scored against the hidden truth{detail}</small>", unsafe_allow_html=True)

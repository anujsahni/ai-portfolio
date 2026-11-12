"""Shared pieces of the ContextLoop app: warehouse queries, recordings, the replay player, the job runner, and layout."""
from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from contextloop import config
from contextloop.ui import brand

JOB_LOCK = config.WAREHOUSE_PATH.parent / ".job.lock"
SERVER_OF = {"list_metrics": "Metrics MCP", "query_metric": "Metrics MCP", "check_freshness": "Freshness MCP",
             "dbt_list": "dbt MCP", "dbt_get_lineage_dev": "dbt MCP", "dbt_get_node_details_dev": "dbt MCP", "run_sql": "raw SQL"}
STORY = ["home", "act1", "act2", "act3", "act4", "act5", "compare", "scorecard"]

CSS = f"""
<style>
.cl-act {{font-size:0.78rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase; color:{brand.INDIGO}; margin-bottom:-0.4rem}}
.cl-headline {{font-size:1.15rem; color:{brand.SLATE}; margin:.2rem 0 1rem}}
.cl-badge {{display:inline-flex; align-items:center; gap:5px; padding:3px 10px; border-radius:999px; font-size:.78rem; font-weight:600;
            margin-right:6px; vertical-align:middle}}
.cl-ic {{flex:none; vertical-align:-2px}}
.cl-ok {{background:{brand.MINT_SOFT}; color:#13734F}} .cl-bad {{background:{brand.ROSE_SOFT}; color:#B4282D}}
.cl-warn {{background:{brand.AMBER_SOFT}; color:#8A5A00}} .cl-info {{background:{brand.INDIGO_SOFT}; color:#3341B8}}
.cl-muted {{background:#EEF1F6; color:{brand.SLATE}}} .cl-teal {{background:{brand.LAGOON_SOFT}; color:#0B7A70}}
.cl-coral {{background:{brand.CORAL_SOFT}; color:#B8432A}}
.cl-card {{border:1px solid {brand.LINE}; border-radius:12px; padding:.85rem 1rem; margin-bottom:.6rem; background:#FFFFFF;
           box-shadow:0 1px 2px rgba(24,32,58,.04)}}
.cl-card h4 {{margin:0 0 .3rem 0; font-size:1rem; color:{brand.INK}}}
.cl-note {{display:flex; gap:6px; align-items:flex-start; color:#8A5A00; font-size:.85rem; margin-top:.35rem}}
.cl-quote {{font-size:1.2rem; font-style:italic; border-left:4px solid {brand.LAGOON}; padding:.4rem 1rem; margin:.4rem 0 1rem;
            background:linear-gradient(90deg, {brand.LAGOON_SOFT}, transparent 70%); border-radius:0 10px 10px 0}}
.cl-vs {{border:1px solid {brand.LINE}; border-radius:14px; padding:1rem 1.1rem; background:#FFFFFF; height:100%;
          box-shadow:0 1px 3px rgba(24,32,58,.06)}}
.cl-vs-label {{font-size:.8rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase}}
.cl-vs-hero {{border-radius:10px; padding:.6rem .9rem; margin:.5rem 0 .8rem}}
.cl-vs-hero span {{font-size:3rem; font-weight:800; line-height:1}}
.cl-vs-hero small {{font-size:.95rem; color:{brand.SLATE}}}
.cl-vs-row {{display:flex; gap:10px; align-items:flex-start; padding:.45rem 0; border-top:1px solid {brand.LINE}}}
.cl-vs-row svg {{margin-top:4px}} .cl-vs-row small {{color:{brand.SLATE}}}
.cl-flow {{margin:.2rem 0 .7rem; text-align:center}}
.cl-flow-step {{background:{brand.MIST}; border:1px solid {brand.LINE}; border-radius:8px; padding:.3rem .6rem; font-size:.85rem}}
.cl-flow-arrow {{color:{brand.SLATE}; font-size:.8rem; line-height:1.1rem}}
.cl-grid {{width:100%; border-collapse:collapse; font-size:.92rem}}
.cl-grid th {{text-align:left; color:{brand.SLATE}; font-weight:600; border-bottom:2px solid {brand.LINE}; padding:.4rem .5rem}}
.cl-grid td {{border-bottom:1px solid {brand.LINE}; padding:.45rem .5rem; vertical-align:top}}
</style>
"""


# ---------- warehouse -------------------------------------------------------------------------------------------------

def _mtime() -> float:
    return config.SERVING_PATH.stat().st_mtime if config.SERVING_PATH.exists() else 0.0


@st.cache_data(show_spinner=False)
def _query(sql: str, params: tuple, mtime: float) -> pd.DataFrame:
    import duckdb

    con = duckdb.connect(str(config.SERVING_PATH), read_only=True)
    try:
        return con.execute(sql, list(params)).df()
    finally:
        con.close()


def query(sql: str, *params) -> pd.DataFrame:
    """A read-only query against the serving copy; cached until a job publishes a new copy."""
    return _query(sql, params, _mtime())


def warehouse_ready() -> bool:
    return config.SERVING_PATH.exists()


def require_warehouse() -> bool:
    if not warehouse_ready():
        st.warning("The warehouse is empty. Run `make data`, `make sync` and `make build` (or `make demo`) first.")
        return False
    return True


# ---------- truth, golden questions, recordings ------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def golden() -> list[dict]:
    return json.loads((config.TRUTH_DIR / "golden.json").read_text())


@st.cache_data(show_spinner=False)
def truth() -> dict:
    """The hidden truth, read only to score answers (the agents never see it)."""
    return json.loads((config.TRUTH_DIR / "truth.json").read_text())


@st.cache_data(show_spinner=False)
def traps() -> dict:
    return json.loads((config.TRUTH_DIR / "traps.json").read_text())


def recording(agent: str, qid: str, variant: str = "") -> dict | None:
    from contextloop.eval.run import recordings_dir

    p = recordings_dir() / "demo" / agent / f"{qid}{variant}.json"
    return json.loads(p.read_text()) if p.exists() else None


def has_key() -> bool:
    return os.environ.get("ANTHROPIC_API_KEY", "").strip() != ""


def mode() -> str:
    return st.session_state.get("mode", config.MODE)


# ---------- jobs -------------------------------------------------------------------------------------------------------

def run_job(args: list[str], label: str, env: dict | None = None) -> tuple[int, str]:
    """Runs `python -m contextloop.cli <args>` (a real job), streaming its output; one job at a time."""
    JOB_LOCK.parent.mkdir(parents=True, exist_ok=True)
    out_box = st.empty()
    lines: list[str] = []
    with open(JOB_LOCK, "w") as lock, st.status(label, expanded=True) as status:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            status.update(label="Another job is running; try again in a moment", state="error")
            return 1, ""
        proc = subprocess.Popen([sys.executable, "-m", "contextloop.cli", *args], cwd=config.ROOT, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, env=os.environ | (env or {}))
        for line in proc.stdout:
            lines.append(line.rstrip())
            out_box.code("\n".join(lines[-18:]), language="text")
        code = proc.wait()
        status.update(label=f"{label}: {'done' if code == 0 else 'finished with exit code ' + str(code)}",
                      state="complete" if code == 0 else "error", expanded=False)
    st.cache_data.clear()
    return code, "\n".join(lines)


# ---------- layout -----------------------------------------------------------------------------------------------------

def header(act: str, title: str, headline: str) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(f'<div class="cl-act">{act}</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="cl-headline">{headline}</div>', unsafe_allow_html=True)
    m = re.fullmatch(r"Act (\d)", act)
    if m:  # each act shows the architecture as it stands after it: what it relies on, and what it adds
        from contextloop.ui.pages.architecture import act_diagram

        act_diagram(int(m.group(1)))


def badge(text: str, kind: str = "muted", icon: str | None = None) -> str:
    """A pill label; `icon` is one of brand's line icons (check, close, warning, play, pending, info, record, bolt)."""
    return f'<span class="cl-badge cl-{kind}">{brand.icon(icon, 13) if icon else ""}{text}</span>'


def note(text: str, icon: str = "warning") -> str:
    """A small inline warning line for cards."""
    return f'<div class="cl-note">{brand.icon(icon, 14)}<span>{text}</span></div>'


def nav_buttons(current: str) -> None:
    pages = st.session_state.get("_pages", {})
    i = STORY.index(current) if current in STORY else -1
    st.divider()
    left, mid, right = st.columns([1, 3, 1])
    if i > 0 and STORY[i - 1] in pages and left.button("Back", icon=":material/arrow_back:", use_container_width=True,
                                                       key=f"back-{current}"):
        st.switch_page(pages[STORY[i - 1]])
    if i >= 0:
        mid.progress((i + 1) / len(STORY), text=f"Step {i + 1} of {len(STORY)}")
    if 0 <= i < len(STORY) - 1 and STORY[i + 1] in pages and right.button("Next", icon=":material/arrow_forward:", use_container_width=True,
                                                                           type="primary", key=f"next-{current}"):
        st.switch_page(pages[STORY[i + 1]])


def score_badge(sc: dict | None) -> str:
    if not sc:
        return badge("Not scored", "muted", "pending")
    return badge("Correct", "ok", "check") if sc.get("correct") else badge("Wrong", "bad", "close")


def step_expander(n: int, step: dict):
    """A step's expander: the label says in plain English what the call did; inside, the agent's stated purpose and any failure."""
    from contextloop.ui.step_describe import describe, describe_error

    server = SERVER_OF.get(step["tool"], "tool")
    error = describe_error(step.get("output") or {})
    label = f"Step {n} · {server} · {describe(step)}" + (" · ⚠ error" if error or step.get("is_error") else "")
    box = st.expander(label, expanded=False)
    with box:
        purpose = (step.get("input") or {}).get("purpose")
        if purpose:
            st.markdown(f"**Agent's stated purpose:** {purpose}")
        if error:
            st.markdown(badge(error, "bad", "close"), unsafe_allow_html=True)
        st.caption(f"Tool: `{step['tool']}`")
    return box


def _step_detail(n: int, s: dict) -> None:
    """One call inside a stage: the agent's reason, then the query and what came back (no nested expanders)."""
    from contextloop.ui.step_describe import describe, describe_error

    inp, out = s.get("input") or {}, s.get("output") or {}
    error = describe_error(out)
    reason = inp.get("purpose") or describe(s)
    st.markdown(f"**Step {n}** · <small>{SERVER_OF.get(s['tool'], 'tool')}</small> · {_md(reason)}", unsafe_allow_html=True)
    if error or s.get("is_error"):
        st.markdown(badge(error or "Failed", "bad", "close"), unsafe_allow_html=True)
    if "sql" in inp:
        st.code(inp["sql"], language="sql")
    elif inp:
        st.code(json.dumps(inp, indent=1), language="json")
    if "rows" in out and "columns" in out:
        st.dataframe(pd.DataFrame(out["rows"], columns=out["columns"]).head(25), hide_index=True, use_container_width=True)
        if out.get("compiled_sql"):
            st.caption("SQL compiled by MetricFlow from the governed metric definitions:")
            st.code(out["compiled_sql"][:4000], language="sql")
    elif out and not error:
        st.json(out, expanded=False)


def play_steps(trace: dict, container, pace: float = 0.55) -> None:
    """The agent's tool calls as a story: who ran them and why, then one card per stage of its reasoning (what it was trying
    to work out, how many calls it took, and what went wrong there), with the calls themselves folded away inside."""
    from contextloop.ui.step_describe import describe_error
    from contextloop.ui.step_stages import HANDLED_BY_FOUNDATION, STAGES, TRAP_STAGE, stages, step_numbers

    steps = trace.get("steps", [])
    if not steps:
        return
    naive = trace.get("agent") == "naive"
    groups = stages(trace)
    findings = []
    if naive:
        findings = trace.get("explanation")
        if findings is None:
            from contextloop.agent.explain import explain

            findings = explain(trace, truth(), traps())
    kind, one = ("queries", "query") if naive else ("calls", "call")
    with container:
        if naive:
            st.markdown(f"**Who ran these, and why?** Nobody wrote this SQL. Claude was given the question above and read-only "
                        f"access to Northstar's raw tables, and planned every query itself. Without definitions, it had to work "
                        f"out what the data means from scratch: **{len(steps)} {kind}** in **{len(groups)} stages**.")
        else:
            st.markdown(f"**Who ran these, and why?** The same model, given the same question, but instead of raw tables it has "
                        f"three MCP servers: governed metrics, freshness and dbt. It reads the answers to the hard questions "
                        f"instead of guessing them: **{len(steps)} {kind}** in **{len(groups)} stages**.")
        st.markdown(" → ".join(badge(f"{i}. {g['title']} · {len(g['steps'])}", "info") for i, g in enumerate(groups, start=1)),
                    unsafe_allow_html=True)
    for i, g in enumerate(groups, start=1):
        with container, st.container(border=True):
            n = len(g["steps"])
            st.markdown(f"**{i}. {g['title']}** <small>· {n} {kind if n > 1 else one} · step{'s' if n > 1 else ''} "
                        f"{step_numbers(g['steps'])}</small><br><span style='color:{brand.SLATE}'><i>{g['question']}</i></span>",
                        unsafe_allow_html=True)
            notes = [badge(f"{f['trap']} · {f['title']}" if f["trap"] != "—" else f["title"], "bad", "close") for f in findings or []
                     if TRAP_STAGE.get(f["trap"]) == g["key"]]
            failed = [describe_error(s.get("output") or {}) for _, s in g["steps"]]
            failed = [f for f in failed if f]
            if failed and len(failed) == n:
                notes.append(badge(failed[0], "warn", "warning"))
            if not naive and g["key"] in ("definitions", "compute"):
                notes.append(badge("From the governed definitions", "ok", "check"))
            if notes:
                lead = "Went wrong here: " if any("cl-bad" in x for x in notes) else "Didn't happen: " if failed else ""
                st.markdown(lead + " ".join(notes),
                            unsafe_allow_html=True)
            with st.expander(f"Show the {n} {kind}" if n > 1 else f"Show the {one}"):
                for num, s in g["steps"]:
                    _step_detail(num, s)
        if pace:
            time.sleep(pace)
    done = {g["key"] for g in groups}
    with container:
        if naive and "lineage" not in done:
            st.caption("Never got to: showing where its numbers come from. Raw tables have no lineage to show.")
        if not naive:
            skipped = [f"**{STAGES[k][0].lower()}** ({v})" for k, v in HANDLED_BY_FOUNDATION.items() if k not in done]
            if skipped:
                st.caption("Didn't need to " + "; or ".join(skipped) + ". The data foundation already answers those.")


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])")


def _md(text: str) -> str:
    """Escapes dollar signs, which Streamlit markdown would otherwise read as LaTeX."""
    return text.replace("$", "\\$")


def _account_line(a: dict) -> str:
    facts = []
    if isinstance(a.get("on_time_rate"), (int, float)):
        facts.append(f"{a['on_time_rate']:.1%} on time")
    if a.get("late_deliveries") is not None:
        facts.append(f"{a['late_deliveries']} late")
    if a.get("open_shipping_tickets") is not None:
        n = a["open_shipping_tickets"]
        facts.append(f"{n} open shipping ticket{'' if n == 1 else 's'}")
    if a.get("renewal_close_date"):
        facts.append(f"renews {a['renewal_close_date']}")
    line = f"- **{_md(a.get('account_name', '?'))}**" + (f" · {' · '.join(facts)}" if facts else "")
    if a.get("next_step"):
        line += f"\n    - *Next step:* {_md(a['next_step'])}"
    return line


def answer_bullets(answer: dict) -> str:
    """The answer as scannable bullets: one per sentence of the summary, then one per flagged account (worst first)."""
    summary = (answer.get("answer_summary") or "").strip()
    parts = [f"- {_md(s)}" for s in _SENTENCE_END.split(summary) if s.strip()]
    accounts = answer.get("at_risk_accounts") or []
    if accounts:
        ranked = sorted(accounts, key=lambda a: a["on_time_rate"] if isinstance(a.get("on_time_rate"), (int, float)) else 2)
        parts.append("\n**Accounts flagged**\n")
        parts += [_account_line(a) for a in ranked]
    return "\n".join(parts) or "_No summary given._"


def answer_table(answer: dict | None) -> None:
    if not answer:
        st.info("No answer was submitted.")
        return
    st.markdown("**Answer**")
    st.markdown(answer_bullets(answer))
    rows = answer.get("at_risk_accounts") or []
    if rows:
        df = pd.DataFrame(rows)
        if "on_time_rate" in df:
            df["on_time_rate"] = df["on_time_rate"].map(lambda v: f"{v:.1%}" if isinstance(v, (int, float)) else "—")
        with st.expander("All account detail, with the drivers behind each"):
            st.dataframe(df, hide_index=True, use_container_width=True)
    if answer.get("value") is not None:
        st.metric("Answer", f"{answer['value']:,}" + (f" {answer.get('unit')}" if answer.get("unit") else ""))
    if answer.get("is_current") is not None:
        st.markdown(badge("Data current" if answer["is_current"] else "Data not current", "ok" if answer["is_current"] else "warn",
                          "check" if answer["is_current"] else "warning"),
                    unsafe_allow_html=True)
    if answer.get("assumptions"):
        st.caption("Assumptions stated: " + " · ".join(answer["assumptions"]))


def recorded_label(trace: dict) -> None:
    when = trace.get("started_at", "")[:16].replace("T", " ")
    st.markdown(badge("Recorded run", "info", "record") + f" <small>{trace.get('model')} · effort {trace.get('effort')} · {when} UTC · "
                f"{trace.get('seconds')}s · {len(trace.get('steps', []))} tool calls</small>", unsafe_allow_html=True)


def no_recording(agent: str) -> None:
    st.info(f"No recorded {agent} run yet. Record them once with `make record` (needs an Anthropic API key in `.env`), "
            "or switch to **Live** in the sidebar.")


def project_file(rel: str) -> str:
    return (config.ROOT / rel).read_text()


def path_exists(rel: str) -> bool:
    return (config.ROOT / rel).exists()


__all__ = ["Path"]

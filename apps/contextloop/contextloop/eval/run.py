"""`make eval` and `make record`: score both agents on the six golden questions against the hidden truth.

Live mode (an API key is set): runs each agent on each question CONTEXTLOOP_EVAL_RUNS times (default 3), records every run,
and writes a report. `make record` also promotes one run per agent and question to the demo recordings the app replays: a
passing run for the governed agent, and a typical (lowest-scoring) run for the naive agent.
Replay mode (no key): re-scores the saved recordings against the current hidden truth, without calling Claude.
"""
from __future__ import annotations

import json
import os
import statistics
from datetime import datetime, timezone
from pathlib import Path

from contextloop import config
from contextloop.eval.score import score

AGENTS = ("naive", "governed")
OUT = config.DATA_OUT / "recordings"          # written by the job, then copied to the repo by the Makefile
REPO_RECORDINGS = config.ROOT / "recordings"   # checked in; baked into the image
REPORTS = config.DATA_OUT / "reports"


def golden() -> list[dict]:
    return json.loads((config.TRUTH_DIR / "golden.json").read_text())


def truth() -> dict:
    return json.loads((config.TRUTH_DIR / "truth.json").read_text())


def cost(usage: dict) -> float:
    """List-price cost of a run, summed per request at the price of the model that ran it (see agent/config.PRICES)."""
    if "cost_usd" in usage:
        return round(usage["cost_usd"], 4)
    from contextloop.agent.runner import request_cost

    return round(request_cost(usage), 4)


def recordings_dir() -> Path:
    """Fresh recordings from this volume if any, else the checked-in ones."""
    return OUT if (OUT / "demo").exists() else REPO_RECORDINGS


def load_demo(agent: str, qid: str) -> dict | None:
    p = recordings_dir() / "demo" / agent / f"{qid}.json"
    return json.loads(p.read_text()) if p.exists() else None


def live_run(runs: int) -> list[dict]:
    from contextloop.agent import governed, naive
    from contextloop.agent.mcp_bridge import Bridge

    bridge = Bridge()
    bridge.connect()
    t = truth()
    results = []
    for q in golden():
        for agent in AGENTS:
            for n in range(1, runs + 1):
                print(f"  {agent:<8} {q['id']} run {n}/{runs} …", flush=True)
                tr = (naive.answer(q["id"], q["question"]) if agent == "naive"
                      else governed.answer(q["id"], q["question"], bridge=bridge)).to_dict()
                tr["score"] = score(q["id"], tr["answer"], t)
                tr["cost_usd"] = cost(tr["usage"])
                tr["run"] = n
                if agent == "naive":
                    from contextloop.agent.explain import explain

                    traps = json.loads((config.TRUTH_DIR / "traps.json").read_text())
                    tr["explanation"] = explain(tr, t, traps)
                path = OUT / "runs" / agent / f"{q['id']}-r{n}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(tr, indent=2, default=str))
                results.append(tr)
                print(f"           {'✓' if tr['score']['correct'] else '✗'}  {tr['seconds']}s  ${tr['cost_usd']}"
                      f"{'  ' + tr['error'] if tr.get('error') else ''}", flush=True)
    return results


def rescore() -> list[dict]:
    t = truth()
    runs_dir = recordings_dir() / "runs"
    results = []
    for p in sorted(runs_dir.glob("*/*.json")):
        tr = json.loads(p.read_text())
        tr["score"] = score(tr["question_id"], tr["answer"], t)
        results.append(tr)
    return results


def promote(results: list[dict]) -> None:
    for agent in AGENTS:
        for q in golden():
            runs = [r for r in results if r["agent"] == agent and r["question_id"] == q["id"]]
            if not runs:
                continue
            if agent == "governed":
                pick = next((r for r in runs if r["score"]["correct"] and not r.get("error")), runs[0])
            else:
                # the demo shows a wrong answer whose mistakes the explainer can name (most findings tied to traps)
                wrong = [r for r in runs if not r["score"]["correct"]] or runs
                pick = max(wrong, key=lambda r: sum(f["trap"] != "—" for f in r.get("explanation") or []))
            path = OUT / "demo" / agent / f"{q['id']}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(pick | {"recorded": True}, indent=2, default=str))


GOVERNED_MIN = 5  # of 6, averaged over runs
MIN_GAP = 3  # points between the governed and the naive average


def passes(summary: dict, naive_g1_always_wrong: bool) -> bool:
    """The evaluation bar (restated 11 Nov 2026 with the owner): what the demo has to prove is the gap, not that the naive agent
    fails a fixed number of questions. It may get the arithmetic questions right; it must never get the headline list right."""
    gov, naive = summary.get("governed", 0), summary.get("naive", 0)
    return gov >= GOVERNED_MIN and gov - naive >= MIN_GAP and naive_g1_always_wrong


def report(results: list[dict], live: bool) -> Path:
    qs = golden()
    by = {(r["agent"], r["question_id"], r.get("run", 1)): r for r in results}
    runs = sorted({r.get("run", 1) for r in results})
    lines = [f"# ContextLoop evaluation · {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC", "",
             f"Mode: {'live (Claude called now)' if live else 'replay (saved recordings re-scored)'} · model "
             f"{results[0]['model'] if results else '—'} · effort {results[0]['effort'] if results else '—'} · runs per question: "
             f"{len(runs)}", "", "## Score out of 6 per run", "", "| Agent | " + " | ".join(f"Run {n}" for n in runs) + " | Average |",
             "|---|" + "---|" * (len(runs) + 1)]
    summary = {}
    for agent in AGENTS:
        totals = [sum(1 for q in qs if by.get((agent, q["id"], n), {}).get("score", {}).get("correct")) for n in runs]
        summary[agent] = statistics.mean(totals) if totals else 0
        lines.append(f"| {agent} | " + " | ".join(str(t) for t in totals) + f" | **{summary[agent]:.1f}** |")
    lines += ["", "## Per question (✓ correct · ✗ wrong)", "", "| Question | Expected | Naive | Governed |", "|---|---|---|---|"]
    for q in qs:
        exp = q["expected"]
        exp_s = f"{len(exp)} accounts" if isinstance(exp, list) else json.dumps(exp)
        cells = []
        for agent in AGENTS:
            marks = []
            for n in runs:
                r = by.get((agent, q["id"], n))
                if r:
                    got = r["score"].get("got")
                    got_s = f"{len(got)} accts" if isinstance(got, list) else json.dumps(got)
                    marks.append(("✓ " if r["score"]["correct"] else "✗ ") + got_s)
            cells.append("<br>".join(marks) or "—")
        lines.append(f"| {q['id']} {q['question'][:70]}… | {exp_s} | {cells[0]} | {cells[1]} |")
    lines += ["", "## Cost and time", "", "| Agent | Avg seconds per question | Avg tokens in / out | Total cost (USD) |", "|---|---|---|---|"]
    for agent in AGENTS:
        rs = [r for r in results if r["agent"] == agent]
        if rs:
            lines.append(f"| {agent} | {statistics.mean(r['seconds'] for r in rs):.0f} | "
                         f"{statistics.mean(r['usage']['input_tokens'] for r in rs):,.0f} / "
                         f"{statistics.mean(r['usage']['output_tokens'] for r in rs):,.0f}"
                         f" | ${sum(cost(r['usage']) for r in rs):.2f} |")
    g1_naive = [by[k] for k in by if k[0] == "naive" and k[1] == "G1"]
    g1_all_wrong = bool(g1_naive) and not any(r["score"]["correct"] for r in g1_naive)
    ok = passes(summary, g1_all_wrong)
    lines += ["", f"Pass bar (CL-09, CL-11): governed ≥ {GOVERNED_MIN} of 6 on average; naive at least {MIN_GAP} points lower; "
              "naive wrong on the headline question (G1) in every run.",
              f"Result: governed {summary.get('governed', 0):.1f}, naive {summary.get('naive', 0):.1f}, naive wrong on G1 in "
              f"{sum(1 for r in g1_naive if not r['score']['correct'])} of {len(g1_naive)} runs → " + ("**pass**" if ok else "**not met**")]
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"eval-{datetime.now(timezone.utc):%Y-%m-%d}.md"
    path.write_text("\n".join(lines) + "\n")
    (REPORTS / "latest.json").write_text(json.dumps({"summary": summary, "live": live, "runs": len(runs)}, indent=2))
    print("\n".join(lines[:12]))
    return path


def record_t6_off() -> None:
    """Records the governed headline answer with Zendesk current, for Act 4's stale-data toggle, then restores trap T6."""
    from contextloop.agent import governed
    from contextloop.landing.sync_all import set_zendesk_scenario

    q = next(q for q in golden() if q["id"] == "G1")
    set_zendesk_scenario(stale=False)
    try:
        print("  governed G1 with Zendesk current (T6 off) …", flush=True)
        tr = governed.answer(q["id"], q["question"]).to_dict()
        tr["score"] = score(q["id"], tr["answer"], truth())
        tr["cost_usd"] = cost(tr["usage"])
        path = OUT / "demo" / "governed" / "G1-t6off.json"
        path.write_text(json.dumps(tr | {"recorded": True, "scenario": "T6 off: all sources current"}, indent=2, default=str))
    finally:
        set_zendesk_scenario(stale=True)


def has_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def run(record: bool = False) -> int:
    live = config.MODE == "live" or record
    if live and not has_key():
        print("✗ Live runs need ANTHROPIC_API_KEY in .env. Without one, `make eval` re-scores the saved recordings.")
        if record:
            return 1
        live = False
    if live:
        results = live_run(int(os.environ.get("CONTEXTLOOP_EVAL_RUNS", "3")))
        if record:
            promote(results)
            if config.T6_STALE_ZENDESK:
                record_t6_off()
    else:
        results = rescore()
        if not results:
            print("No recordings yet. Run `make record` with an API key first.")
            return 1
    path = report(results, live)
    print(f"Report: {path.relative_to(config.DATA_OUT)}")
    return 0

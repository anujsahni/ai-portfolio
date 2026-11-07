#!/usr/bin/env python3
"""MVP-06: run the scripted trip scenarios through the real planner and compare with expectations.

Runs as weekendwise-run (the Cloud Run identity). Writes:
  reports/scenarios-latest.json            full planner responses
  docs/mvp/evidence/MVP-06-scenarios.md    expected-vs-actual summary

Usage: python scripts/run_scenarios.py [SCENARIO-ID ...]
Cost: about 5 embedding calls and 1–2 Gemini calls per scenario (a few cents for all six).
"""
from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from weekendwise.config import load_settings  # noqa: E402
from weekendwise.errors import WeekendWiseError  # noqa: E402
from weekendwise.gcp import firestore_client, service_account  # noqa: E402
from weekendwise.planner import Planner  # noqa: E402
from weekendwise.retrieval import Retriever  # noqa: E402
from weekendwise.vertex import VertexClient  # noqa: E402

LIVE_DATA = re.compile(r"\b(hours?|open(ing)?|live|tonight)\b", re.I)
from weekendwise.review import NO_DRINK_DRIVING as NO_DRINK_DRIVE  # noqa: E402  (same strict rule as the reviewer)


def text_of(resp: dict) -> str:
    parts = [resp.get("headline", ""), resp.get("whyThisFits", "")]
    for d in resp.get("days", []):
        for a in d.get("activities", []):
            parts += [a["title"], a["description"]]
    parts += resp.get("uncertainties", []) + resp.get("unansweredRequests", []) + resp.get("assumptions", [])
    return " ".join(parts)


def evaluate(scenario: dict, resp: dict) -> tuple[list[str], list[str]]:
    """Return (failures, differences). Failures break the contract; differences are model judgement calls."""
    exp, fail, diff = scenario["expected"], [], []
    if resp.get("status") != "complete":
        return [f"status {resp.get('status')}"], diff
    calls = resp["toolCalls"]
    if len(calls) != exp["toolCalls"]:
        fail.append(f"tool calls {len(calls)} ≠ expected {exp['toolCalls']}")
    if exp.get("expectedToolArgs") and calls and calls[0]["args"] != exp["expectedToolArgs"]:
        fail.append(f"tool args {calls[0]['args']} ≠ {exp['expectedToolArgs']}")
    u = resp["usage"]
    if u["modelCalls"] > 3 or u["toolCalls"] > 1 or u["revisions"] > 1:
        fail.append(f"bounds exceeded: {u}")
    checks = resp["review"]["checks"]
    for key in ("citationsValid", "budgetArithmetic", "noBookingClaims", "datesMatch"):
        if not checks.get(key):
            fail.append(f"review check failed: {key}")
    city = scenario["request"]["cityId"]
    prefix = {"san-francisco": "SF-", "portland": "PDX-", "santa-cruz": "SC-", "napa-valley": "NAPA-"}[city]
    cited = {c["sourceId"] for c in resp["citations"]}
    if any(not s.startswith(prefix) for s in cited):
        fail.append(f"cited another city: {sorted(cited)}")
    if not any(a["citations"] for d in resp["days"] for a in d["activities"]):
        fail.append("no cited activities")
    budget = resp["budget"]
    if budget["status"] == "over-budget" and not budget["substitutions"]:
        fail.append("over budget without substitutions")
    if exp.get("mustStateNotLiveData") and not LIVE_DATA.search(" ".join(resp.get("unansweredRequests", []) + resp.get("uncertainties", []))):
        fail.append("didn't flag the live-hours request as unanswerable")
    if exp.get("mustIncludeNoDrinkDrivingCaveat") and not NO_DRINK_DRIVE.search(text_of(resp)):
        fail.append("missing designated-driver / no drink-driving guidance")
    if budget["status"] != exp["budgetStatus"]:
        diff.append(f"budget {budget['status']} (expected {exp['budgetStatus']}): ${budget['total']:.0f} of ${budget['limit']:.0f}")
    expected_sources = set(exp.get("expectedSourceIds", []))
    if expected_sources and not expected_sources & cited:
        fail.append(f"none of the expected sources cited ({sorted(expected_sources)})")
    return fail, diff


def main(ids: list[str]) -> int:
    settings = load_settings()
    run_sa = service_account(settings.project_id, "run")
    rs = replace(settings, impersonate_service_account=run_sa)
    vertex = VertexClient(rs)
    retriever = Retriever(rs, firestore_client(settings.project_id, settings.firestore_database, impersonate=run_sa), vertex)
    planner = Planner(rs, retriever, vertex)

    scenarios = sorted((ROOT / "data" / "seed" / "trip_scenarios").glob("*.json"))
    results, rows, failures = {}, [], 0
    for path in scenarios:
        sid = path.stem
        if ids and sid not in ids:
            continue
        sc = json.loads(path.read_text())
        start = time.monotonic()
        try:
            resp = planner.plan(sc["request"])
        except WeekendWiseError as err:
            resp = {"status": "error", "message": str(err)}
        secs = time.monotonic() - start
        results[sid] = resp
        fail, diff = evaluate(sc, resp) if resp.get("status") == "complete" else ([f"status {resp.get('status')}: {resp.get('message') or resp.get('errors') or resp.get('question')}"], [])
        failures += bool(fail)
        u = resp.get("usage", {})
        b = resp.get("budget", {})
        row = {
            "id": sid, "ok": not fail, "fail": fail, "diff": diff, "seconds": round(secs, 1),
            "tool": f"{len(resp.get('toolCalls', []))} (expected {sc['expected']['toolCalls']})"
                    + (f" {resp['toolCalls'][0]['args']['demo_date']} → {resp['toolCalls'][0]['status']}" if resp.get("toolCalls") else ""),
            "review": f"{resp.get('review', {}).get('outcome', '-')} (expected {sc['expected']['reviewOutcome']})",
            "budget": f"${b.get('total', 0):.0f} / ${b.get('limit', 0):.0f} {b.get('status', '-')} (expected {sc['expected']['budgetStatus']})",
            "calls": f"model {u.get('modelCalls', '-')}, tool {u.get('toolCalls', '-')}, searches {u.get('retrievalQueries', '-')}",
            "citations": len(resp.get("citations", [])),
            "issues": resp.get("review", {}).get("issues", []),
        }
        rows.append(row)
        mark = "✓" if row["ok"] else "✗"
        print(f"{mark} {sid}  ({row['seconds']}s)\n    tool: {row['tool']}\n    review: {row['review']}\n    budget: {row['budget']}\n    usage: {row['calls']}, citations {row['citations']}")
        for f in fail:
            print(f"    ✗ {f}")
        for d in diff:
            print(f"    ~ {d}")
        for i in row["issues"]:
            print(f"    first-draft issue: {i}")

    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "scenarios-latest.json").write_text(json.dumps({"ranAt": stamp, "results": results}, indent=2, ensure_ascii=False))
    md = [f"# MVP-06 scenario run — {stamp}", "",
          f"Model `{settings.generation_model_id}` (thinking {settings.thinking_level}), embeddings `{settings.embedding_model_id}` "
          f"({settings.embedding_dimension}), run as `weekendwise-run`. Full responses: `reports/scenarios-latest.json` (git-ignored).", "",
          "| Scenario | Result | Tool call | Review | Budget | Usage | Time |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['id']} | {'✅ pass' if r['ok'] else '❌ fail'} | {r['tool']} | {r['review']} | {r['budget']} | {r['calls']}, {r['citations']} citations | {r['seconds']} s |")
    md += ["", "**Failures** (break the contract):", ""] + ([f"- {r['id']}: {f}" for r in rows for f in r["fail"]] or ["- none"])
    md += ["", "**Differences from the scripted expectation** (model judgement, not failures):", ""] + ([f"- {r['id']}: {d}" for r in rows for d in r["diff"]] or ["- none"])
    md += ["", "**Reviewer issues on first drafts** (fixed by the single revision when the outcome says so):", ""] + ([f"- {r['id']}: {i}" for r in rows for i in r["issues"]] or ["- none"])
    out = ROOT / "docs" / "mvp" / "evidence"
    out.mkdir(parents=True, exist_ok=True)
    (out / "MVP-06-scenarios.md").write_text("\n".join(md) + "\n")
    print(f"\n{len(rows) - failures} of {len(rows)} scenarios passed. Report: docs/mvp/evidence/MVP-06-scenarios.md")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""MVP-05 retrieval checks against Firestore, using the app's Retriever (weekendwise.retrieval).

Runs as weekendwise-run (read-only) over data/retrieval_cases.json.

Usage:
  python scripts/check_retrieval.py              # pass/fail with the configured distance cut-off
  python scripts/check_retrieval.py --calibrate  # show raw distances and suggest a cut-off
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from weekendwise.config import load_settings  # noqa: E402
from weekendwise.errors import WeekendWiseError  # noqa: E402
from weekendwise.gcp import firestore_client, service_account  # noqa: E402
from weekendwise.retrieval import INSUFFICIENT_EVIDENCE, UNSUPPORTED_CITY, Retriever  # noqa: E402
from weekendwise.vertex import VertexClient  # noqa: E402


def make_retriever(settings):
    run_sa = service_account(settings.project_id, "run")
    vertex = VertexClient(replace(settings, impersonate_service_account=run_sa))
    db = firestore_client(settings.project_id, settings.firestore_database, impersonate=run_sa)
    return Retriever(settings, db, vertex)


def calibrate(settings, cases) -> int:
    retriever = make_retriever(replace(settings, retrieval_max_distance=2.0))  # cut-off off
    pos, neg = [], []
    print(f"{'case':<11}{'nearest':>8}  {'expected rank/dist':<22} query")
    for c in cases:
        if c.get("unsupported") or ("expect" not in c and not c.get("insufficient")):
            continue
        r = retriever.retrieve(c["query"], c["city"])
        if "expect" in c:
            dists = [h.distance for h in r.chunks if h.source_id in c["expect"]]
            d = min(dists) if dists else None
            pos.append((c["id"], d))
            print(f"{c['id']:<11}{r.nearest_distance:>8.3f}  {('%.3f' % d) if d is not None else 'not in top-k':<22} {c['query']}")
        else:
            neg.append((c["id"], r.nearest_distance))
            print(f"{c['id']:<11}{r.nearest_distance:>8.3f}  {'(should be rejected)':<22} {c['query']}")
    worst_pos = max(d for _, d in pos if d is not None)
    best_neg = min(d for _, d in neg)
    print(f"\nexpected matches: farthest at {worst_pos:.3f}   off-topic: closest at {best_neg:.3f}")
    if worst_pos < best_neg:
        print(f"✓ separable. Suggested RETRIEVAL_MAX_DISTANCE = {(worst_pos + best_neg) / 2:.3f} (midpoint)")
    else:
        print("✗ overlap: no single cut-off separates all cases; pick one that favours rejecting off-topic questions.")
    return 0


def check(settings, cases) -> int:
    retriever = make_retriever(settings)
    failures = 0
    for c in cases:
        r = retriever.retrieve(c["query"], c["city"])
        sources = [h.source_id for h in r.chunks]
        problems = []
        if c.get("unsupported") and r.status != UNSUPPORTED_CITY:
            problems.append(f"expected unsupported_city, got {r.status}")
        if c.get("insufficient") and r.status != INSUFFICIENT_EVIDENCE:
            problems.append(f"expected insufficient evidence, got {sources}")
        if "expect" in c and not any(s in sources for s in c["expect"]):
            problems.append(f"none of {c['expect']} in {sources or r.reason}")
        if any(s in sources for s in c.get("forbid", [])):
            problems.append(f"forbidden source returned: {sources}")
        if c.get("expect_note") and not any(c["expect_note"] in n for n in r.notes):
            problems.append(f"missing note containing '{c['expect_note']}'")
        if any(h.city_id != c["city"] for h in r.chunks):
            problems.append("chunk from another city returned")
        failures += bool(problems)
        if r.status == "ok":
            got = ", ".join(f"{h.source_id} ({h.distance:.3f})" for h in r.chunks)
        else:
            got = r.status + (f" (closest {r.nearest_distance:.3f})" if r.nearest_distance is not None else "")
        print(f"{'✓' if not problems else '✗'} {c['id']:<10} {got}")
        for p in problems:
            print(f"      ✗ {p}")
        for n in r.notes:
            print(f"      note: {n}")
    print(f"\n{len(cases) - failures} of {len(cases)} retrieval cases passed (cut-off {settings.retrieval_max_distance:.3f}, top-k {settings.retrieval_top_k}).")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--calibrate", action="store_true")
    args = parser.parse_args()
    cases = json.loads((ROOT / "data" / "retrieval_cases.json").read_text())["cases"]
    try:
        settings = load_settings()
        return calibrate(settings, cases) if args.calibrate else check(settings, cases)
    except WeekendWiseError as err:
        print(f"✗ {type(err).__name__}: {err.message} {err.hint}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

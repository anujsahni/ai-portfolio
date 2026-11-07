#!/usr/bin/env python3
"""Ask one grounded question (MVP-05): Firestore retrieval -> Gemini -> verified citations.

Runs as weekendwise-run (the Cloud Run identity), so it exercises the same access the app has.
Usage: python scripts/ask.py --city san-francisco "Where can we get coffee by the water?" [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from weekendwise.citations import grounded_answer  # noqa: E402
from weekendwise.config import load_settings  # noqa: E402
from weekendwise.errors import WeekendWiseError  # noqa: E402
from weekendwise.gcp import firestore_client, service_account  # noqa: E402
from weekendwise.retrieval import Retriever  # noqa: E402
from weekendwise.vertex import VertexClient  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("question")
    p.add_argument("--city", default="san-francisco")
    p.add_argument("--json", action="store_true", help="print the full response object (what the UI receives)")
    a = p.parse_args()
    try:
        s = load_settings()
        run_sa = service_account(s.project_id, "run")
        rs = replace(s, impersonate_service_account=run_sa)
        vertex = VertexClient(rs)
        retriever = Retriever(rs, firestore_client(s.project_id, s.firestore_database, impersonate=run_sa), vertex)
        ans = grounded_answer(a.question, a.city, retriever, vertex)
    except WeekendWiseError as err:
        print(f"✗ {type(err).__name__}: {err.message}\n  Next step: {err.hint}")
        return 1
    if a.json:
        print(json.dumps(ans.to_dict(), indent=2, ensure_ascii=False))
        return 0
    extra = f", reason: {ans.reason}" if ans.reason else ""
    print(f"[{ans.status}{extra}; model calls: {ans.model_calls}]\n\n{ans.text}\n")
    for c in ans.citations:
        print(f"  [{c.label}] {c.source_id} — {c.title} (reviewed {c.last_reviewed})  chunk {c.chunk_id}")
    for n in ans.notes:
        print(f"  note: {n}")
    if ans.rejected_labels:
        print(f"  removed unknown citation labels: {', '.join(ans.rejected_labels)}")
    r = ans.retrieval
    if r.get("nearest_distance") is not None:
        print(f"  retrieval: {len(r['chunks'])} passages kept, closest {r['nearest_distance']:.3f} (cut-off {r['max_distance']:.2f}), {r['latency_ms']} ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())

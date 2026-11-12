#!/usr/bin/env python3
"""Update a story's status in docs/mvp/INDEX.md and the README progress table together, so they never drift apart.

Run it when a story starts (status 'progress') and when it closes ('done'):
  python scripts/backlog_status.py CL-04 progress
  python scripts/backlog_status.py CL-04 done --delivered "Connector SDK connector, sync job, tests" --needed "—"
Statuses: todo, progress, done, blocked. Points totals and phase rows are recomputed from the story rows.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "mvp" / "INDEX.md"
README = ROOT / "README.md"
ICON = {"todo": "⬜ To do", "progress": "🟡 In progress", "done": "✅ Done", "blocked": "⛔ Blocked"}


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def update(story: str, status: str, delivered: str | None, needed: str | None) -> None:
    text = INDEX.read_text()
    out = []
    for line in text.splitlines():
        c = _cells(line) if line.startswith("|") else []
        if c and f"[{story}]" in line and len(c) == 9:  # phase table row
            c[8] = ICON[status]
            line = _row(c)
        elif c and c[0] == story and len(c) == 6:  # implementation status row
            c[3] = ICON[status]
            if delivered is not None:
                c[4] = delivered
            if needed is not None:
                c[5] = needed
            line = _row(c)
        out.append(line)
    text = "\n".join(out) + "\n"
    rows = [_cells(ln) for ln in text.splitlines() if re.match(r"\| CL-\d\d \|", ln)]
    total = sum(int(r[2]) for r in rows)
    done_pts = sum(int(r[2]) for r in rows if r[3].startswith("✅"))
    done_n = sum(1 for r in rows if r[3].startswith("✅"))
    text = re.sub(r"\*\*Done: \d+ of \d+ points\.\*\*", f"**Done: {done_pts} of {total} points.**", text)
    INDEX.write_text(text)
    status_of = {r[0]: r[3] for r in rows}
    _readme(status_of, done_pts, total, done_n, len(rows))
    print(f"{story}: {ICON[status]} · done {done_pts}/{total} points ({done_n}/{len(rows)} stories)")


def _readme(status_of: dict[str, str], done_pts: int, total: int, done_n: int, n: int) -> None:
    text = README.read_text()
    text = re.sub(r"\*\*Points done: \d+ of \d+ \(\d+%\)\.\*\* Stories done: \d+ of \d+\.",
                  f"**Points done: {done_pts} of {total} ({round(100 * done_pts / total)}%).** Stories done: {done_n} of {n}.", text)
    out = []
    for line in text.splitlines():
        c = _cells(line) if line.startswith("|") else []
        if len(c) == 6 and re.fullmatch(r"\d", c[0]) and "CL-" in c[2]:
            ids = re.findall(r"CL-\d\d", c[2])
            st = [status_of.get(i, "") for i in ids]
            if all(s.startswith("✅") for s in st):
                c[5] = ICON["done"]
            elif any(s.startswith("⛔") for s in st):
                c[5] = ICON["blocked"]
            elif any(s.startswith(("✅", "🟡")) for s in st):
                c[5] = ICON["progress"]
            else:
                c[5] = ICON["todo"]
            line = _row(c)
        out.append(line)
    README.write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("story")
    p.add_argument("status", choices=list(ICON))
    p.add_argument("--delivered")
    p.add_argument("--needed")
    a = p.parse_args()
    update(a.story, a.status, a.delivered, a.needed)

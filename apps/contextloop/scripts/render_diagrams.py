#!/usr/bin/env python3
"""Render the README diagrams in docs/diagrams/*.html to docs/images/*.png.

Each diagram is a small HTML page (shared diagram.css and diagram.js), so it can be edited as text
and re-rendered. Re-run after editing any page.

Usage: python scripts/render_diagrams.py [name ...]   (default: every page in docs/diagrams)
Needs: pip install playwright; uses the installed Google Chrome (channel="chrome"), no browser download.
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "diagrams"
OUT = ROOT / "docs" / "images"


def main() -> None:
    names = sys.argv[1:] or sorted(p.stem for p in SRC.glob("*.html"))
    OUT.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        for name in names:
            page = browser.new_page(viewport={"width": 1300, "height": 1600}, device_scale_factor=2)
            errors: list[str] = []
            page.on("pageerror", lambda exc, errors=errors: errors.append(str(exc)))
            page.goto((SRC / f"{name}.html").as_uri())
            page.wait_for_selector(".canvas .node")
            page.wait_for_timeout(200)
            out = OUT / f"{name}.png"
            page.locator(".canvas").screenshot(path=str(out))
            page.close()
            if errors:
                failures.append(f"{name}: {errors}")
            print(f"Wrote {out.relative_to(ROOT)}")
        browser.close()
    if failures:
        raise SystemExit("Page errors:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()

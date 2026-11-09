#!/usr/bin/env python3
"""Render the interactive Architecture page to docs/images/architecture.png for the README.

The README image and the in-app Architecture page come from the same files
(dealpulse/ui/architecture/), so they cannot drift apart. Re-run after editing the diagram.

Usage: python scripts/render_architecture.py [--step N] [--out PATH]
Needs: pip install playwright; uses the installed Google Chrome (channel="chrome"), no browser download.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "dealpulse" / "ui" / "architecture" / "index.html"
DEFAULT_OUT = ROOT / "docs" / "images" / "architecture.png"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--step", type=int, default=0, help="Highlight walkthrough step N (1-based); 0 = full diagram")
    parser.add_argument("--full-page", action="store_true", help="Capture the whole page, not just the diagram")
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1360, "height": 1500}, device_scale_factor=2)
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto(PAGE.as_uri())
        page.wait_for_selector("#arch-svg .arch-node")
        for _ in range(args.step):
            page.keyboard.press("ArrowRight")
        page.wait_for_timeout(300)
        if args.full_page:
            page.screenshot(path=str(args.out), full_page=True)
        else:
            page.locator(".arch-canvas").screenshot(path=str(args.out))
        browser.close()
    if errors:
        raise SystemExit(f"Page errors: {errors}")
    print(f"Wrote {args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out}")


if __name__ == "__main__":
    main()

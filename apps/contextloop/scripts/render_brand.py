#!/usr/bin/env python3
"""Write the ContextLoop mark and logo (SVG) and render the PNGs the app uses (favicon, sidebar logo).

The artwork is defined once in contextloop/ui/brand.py. Re-run after changing it.
Usage: python scripts/render_brand.py      Needs: pip install playwright; uses the installed Google Chrome.
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from contextloop.ui import brand  # noqa: E402

OUT = ROOT / "contextloop" / "ui" / "assets"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mark.svg").write_text(brand.MARK_SVG)
    (OUT / "logo.svg").write_text(brand.LOGO_SVG)
    renders = [("mark.svg", "favicon.png", 64, 64, 4), ("mark.svg", "mark.png", 64, 64, 8), ("logo.svg", "logo.png", 262, 64, 4)]
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        for src, dst, w, h, scale in renders:
            page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
            page.set_content(f'<html><body style="margin:0;background:transparent">{(OUT / src).read_text()}</body></html>')
            page.locator("svg").screenshot(path=str(OUT / dst), omit_background=True)
            page.close()
            print(f"Wrote {(OUT / dst).relative_to(ROOT)} ({w * scale}x{h * scale})")
        browser.close()


if __name__ == "__main__":
    main()

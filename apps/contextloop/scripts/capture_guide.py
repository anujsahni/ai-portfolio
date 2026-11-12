#!/usr/bin/env python3
"""Capture the screenshots for docs/getting-started.md by driving the running app (http://127.0.0.1:8501) like a presenter.

It clicks the same buttons a presenter would (incremental sync, Break it, the two-engine query, the CRM sync), so run it on a
stack you don't mind changing. Re-run after `make record` so Acts 1 and 4 show recorded runs.

Usage: python scripts/capture_guide.py          (needs `make demo` first, plus `make lakehouse` for the Trino panel)
Needs: pip install playwright; uses the installed Google Chrome.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images" / "guide"
APP = "http://127.0.0.1:8501"
ARCH = (ROOT / "contextloop" / "ui" / "architecture" / "index.html").as_uri()


def settle(pg: Page, ms: int = 2500) -> None:
    pg.wait_for_timeout(ms)
    pg.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=180_000)
    pg.wait_for_timeout(400)


def shot(pg: Page, name: str, max_h: int = 1700) -> None:
    h = min(pg.evaluate("document.querySelector('[data-testid=\"stMain\"]')?.scrollHeight || document.body.scrollHeight"), max_h)
    pg.screenshot(path=str(OUT / f"{name}.png"), clip={"x": 0, "y": 0, "width": 1440, "height": max(900, h)}, full_page=True)
    print(f"  {name}.png")


def click(pg: Page, label: str, wait_text: str | None = None, timeout: int = 240_000) -> None:
    for _ in range(3):  # Streamlit can show a transient dialog (e.g. after a reconnect); dismiss it first
        if not pg.locator("[data-testid='stDialog']").count():
            break
        print(f"    dialog: {pg.locator('[data-testid=stDialog]').first.inner_text()[:120]!r}")
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(800)
    pg.get_by_role("button", name=label).first.click()
    if wait_text:
        pg.get_by_text(wait_text).first.wait_for(timeout=timeout)
    settle(pg, 1500)


def scroll_to(pg: Page, text: str) -> None:
    pg.get_by_text(text).first.scroll_into_view_if_needed()
    pg.wait_for_timeout(500)


def visit(pg: Page, path: str) -> None:
    pg.goto(f"{APP}/{path}")
    settle(pg)


def viewport_shot(pg: Page, name: str) -> None:
    pg.screenshot(path=str(OUT / f"{name}.png"))
    print(f"  {name}.png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run(["docker", "compose", "exec", "-T", "app", "python", "-c",
                    "import httpx; httpx.post('http://mock-salesforce:8000/reset')"], cwd=ROOT, check=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        pg = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5)

        visit(pg, "")  # the home page is the app's default page
        shot(pg, "01-home", 1100)

        visit(pg, "act-1")
        click(pg, "Ask the agent")
        settle(pg, 6000)
        shot(pg, "02-act1-wrong-answer", 2600)

        visit(pg, "act-2")
        shot(pg, "03-act2-connectors", 1000)
        click(pg, "Run incremental sync", "Syncing all four sources: done")
        scroll_to(pg, "Rows changed in the latest SAP sync")
        viewport_shot(pg, "04-act2-incremental-sync")

        visit(pg, "act-3")
        shot(pg, "05-act3-lineage", 1250)
        click(pg, "Break it, then restore", "Restored: every test passes again.", timeout=300_000)
        scroll_to(pg, "Failing tests with T1 broken")
        viewport_shot(pg, "06-act3-break-it")
        click(pg, "Run the at-risk query on DuckDB and Trino", "Snapshot history")
        scroll_to(pg, "Open lakehouse")
        viewport_shot(pg, "07-act3-two-engines")

        visit(pg, "act-4")
        click(pg, "Ask the governed agent")
        settle(pg, 8000)
        shot(pg, "08-act4-governed-answer", 3200)

        visit(pg, "act-5")
        shot(pg, "09-act5-dry-run", 1300)
        click(pg, "Sync to Salesforce")
        scroll_to(pg, "CRM records now")
        viewport_shot(pg, "10-act5-synced")

        visit(pg, "scorecard")
        shot(pg, "11-scorecard", 1500)

        arch = browser.new_page(viewport={"width": 1280, "height": 860}, device_scale_factor=1.5)
        arch.goto(f"{ARCH}?step=4")
        arch.wait_for_timeout(500)
        arch.hover("#n-mmcp")
        arch.wait_for_timeout(300)
        viewport_shot(arch, "12-architecture-act4")
        arch.goto(f"{ARCH}?step=0&view=customer")
        arch.wait_for_timeout(500)
        viewport_shot(arch, "13-architecture-customer")
        browser.close()


if __name__ == "__main__":
    main()

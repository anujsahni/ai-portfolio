#!/usr/bin/env python3
"""Drive the clickable mockup in headless Chrome: every page renders, key interactions work, no script errors.

Usage: python scripts/mockup_smoke.py [--shots DIR]
Checks: 5 pages render; flagged deals shown; row click opens the brief; citation chips resolve on Sources;
persona switch hides a teammate's deal; Guardrails demo blocks "rank my reps"; Architecture walkthrough;
no horizontal scrolling at phone width.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "artifacts" / "dealpulse-mockups" / "index.html").as_uri()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shots", type=Path)
    args = parser.parse_args()
    results: list[tuple[bool, str]] = []
    check = lambda ok, text: results.append((bool(ok), text))  # noqa: E731

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.goto(PAGE + "#pipeline")
        page.evaluate("localStorage.clear()")
        page.reload()
        page.wait_for_selector("#deal-table tbody tr")

        rows = page.locator("#deal-table tbody tr").count()
        flagged = page.locator("#deal-table tbody tr.flagged").count()
        check(rows > 10 and flagged > 0, f"Pipeline: {rows} deals for Priya Raman (West), {flagged} flagged")
        check("Model disagrees" in page.text_content("#kpis"), "Pipeline: KPI tiles render")
        if args.shots:
            page.screenshot(path=str(args.shots / "1-pipeline.png"), full_page=True)

        page.check("#flagged-only")
        check(page.locator("#deal-table tbody tr").count() == flagged, "Pipeline: 'Disagreements only' filter")
        page.uncheck("#flagged-only")

        page.locator("#deal-table tbody tr", has_text="Northbeam Logistics Group").click()
        page.wait_for_selector("#deal-title")
        check(page.inner_text("#deal-title") == "Northbeam Logistics Group", "Row click opens the deal brief")
        check(page.locator(".brief-list.risks li").count() >= 3, "Deal brief: risks with citations")
        check(page.inner_text(".score-big .value") == "17%", "Deal brief: model score 17%")
        page.click("[data-q^='Rank my reps']")
        check("Blocked by Guardrails" in page.inner_text("#answer"), "Ask: 'rank my reps' is blocked (Guardrails demo)")
        page.click("[data-q='What did they say about the budget?']")
        check("isn't approved" in page.inner_text("#answer"), "Ask: sample answer with citations")
        if args.shots:
            page.screenshot(path=str(args.shots / "2-deal.png"), full_page=True)

        page.locator(".brief-list.risks .cite").first.click()
        page.wait_for_selector("#sources-title")
        check(page.locator(".source-card").count() >= 8, f"Sources: {page.locator('.source-card').count()} cited records")
        check(page.locator(".source-card.highlight").count() == 1, "Sources: clicked citation is highlighted")
        if args.shots:
            page.screenshot(path=str(args.shots / "3-sources.png"), full_page=True)

        page.goto(PAGE + "#model")
        page.wait_for_selector("#model-title")
        check(page.locator(".chart svg circle").count() > 5, "Model: calibration chart drawn")
        check("0.888" in page.inner_text("#model-root"), "Model: AUC from the real evaluation")
        if args.shots:
            page.screenshot(path=str(args.shots / "4-model.png"), full_page=True)

        page.goto(PAGE + "#architecture")
        page.wait_for_selector("#arch-svg .arch-node")
        page.keyboard.press("ArrowRight")
        check(page.inner_text("#arch-counter").startswith("Step 1"), "Architecture: arrow keys walk the steps")
        if args.shots:
            page.screenshot(path=str(args.shots / "5-architecture.png"), full_page=True)
        page.goto(PAGE + "#pipeline")
        page.keyboard.press("ArrowRight")
        check(page.locator("#screen-pipeline.active").count() == 1, "Arrow keys don't affect other pages")

        # A rep can't open a teammate's deal.
        page.select_option("#persona", label="Elena Ortiz · West")
        page.goto(PAGE + "#pipeline")
        own = page.locator("#deal-table tbody tr").count()
        page.evaluate("localStorage.setItem('dealpulse:deal', '006DP0000000007')")
        page.goto(PAGE + "#deal")
        page.reload()
        check("Deal not available" in page.inner_text("#deal-root"), f"Persona: Elena sees {own} own deals and can't open Marcus's deal")

        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        for name in ("pipeline", "deal", "model"):
            mobile.goto(PAGE + f"#{name}")
            mobile.wait_for_timeout(200)
            wide = mobile.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
            check(not wide, f"Phone width: no sideways scrolling on {name}")
        browser.close()

    check(not errors, f"No script errors{': ' + errors[0] if errors else ''}")
    for ok, text in results:
        print(f"{'✓' if ok else '✗'} {text}")
    passed = sum(ok for ok, _ in results)
    print(f"{passed}/{len(results)} mockup checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())

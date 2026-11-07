#!/usr/bin/env python3
"""MVP-07: drive the real web UI in Chrome (headless) and record a walkthrough.

Checks, in order:
  1. Offline (free): pages load, favicon, all four cities selectable, client-side validation blocks bad input
     without calling /api/plan, no browser-side calls to Google APIs.
  2. Live (about 1 cent per trip): each sample trip is loaded from its chip, submitted, and must reach the
     itinerary with day tabs, cited activities, a budget, and a working Source link.
  3. Mobile: the same result re-rendered at 390×844 must have no horizontal scrolling.

Writes screenshots to reports/ui/ (git-ignored) and docs/mvp/evidence/MVP-07-ui-walkthrough.md.
Usage: python scripts/ui_smoke.py [--base-url URL] [--offline] [SAMPLE-ID ...]
Needs: pip install playwright; uses the installed Google Chrome (channel="chrome"), no browser download.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "reports" / "ui"
DESKTOP = {"width": 1360, "height": 900}
MOBILE = {"width": 390, "height": 844}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8080")
    ap.add_argument("--offline", action="store_true", help="only the free checks; no plans are generated")
    ap.add_argument("--bearer", help="identity token for a private Cloud Run service (from gcloud auth print-identity-token)")
    ap.add_argument("samples", nargs="*")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    SHOTS.mkdir(parents=True, exist_ok=True)
    base = args.base_url.rstrip("/")
    results, failures = [], 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        failures += not ok
        results.append({"check": name, "ok": ok, "detail": detail})
        print(f"{'✓' if ok else '✗'} {name}" + (f"  ({detail})" if detail else ""))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        headers = {"Authorization": f"Bearer {args.bearer}"} if args.bearer else None
        ctx = browser.new_context(viewport=DESKTOP, extra_http_headers=headers)
        page = ctx.new_page()
        outside, plan_posts, console_errors = [], [], []
        host = urlparse(base).netloc
        page.on("request", lambda r: outside.append(r.url) if urlparse(r.url).netloc not in (host, "") else None)
        page.on("request", lambda r: plan_posts.append(r.url) if r.url.endswith("/api/plan") else None)
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)

        # ---------------------------------------------------------------- offline checks
        page.goto(f"{base}/plan")
        page.wait_for_selector("#destination option", state="attached")
        check("plan page loads with the app's own favicon", page.evaluate("document.querySelector('link[rel=icon]').href").endswith("/static/favicon.svg"))
        cities = page.eval_on_selector_all("#destination option", "els => els.map(e => e.textContent)")
        check("all four cities are selectable", set(cities) == {"San Francisco", "Portland", "Santa Cruz", "Napa Valley"}, ", ".join(cities))
        page.select_option("#destination", "napa-valley")
        check("inspiration card follows the city", "NAPA VALLEY" in page.inner_text("#inspiration-caption"))
        page.wait_for_timeout(400)  # let the fade-in finish
        page.screenshot(path=SHOTS / "plan-desktop.png", full_page=True)

        page.fill("#start-date", "2027-05-16")
        page.fill("#end-date", "2027-05-14")
        page.click("#submit-button")
        check("end-before-start is blocked in the browser", page.is_visible("#form-alert") and "before" in page.inner_text("#form-alert"))
        page.fill("#start-date", "2027-05-13")
        page.fill("#end-date", "2027-05-16")
        page.click("#submit-button")
        check("4-day trip is blocked in the browser", "at most 3 days" in page.inner_text("#form-alert"))
        page.fill("#start-date", "2027-05-14")
        page.fill("#budget", "20")
        page.click("#submit-button")
        check("too-small budget is blocked in the browser", "Budget" in page.inner_text("#form-alert"))
        check("invalid input never reached the planner", not plan_posts, f"{len(plan_posts)} calls")
        for path in ("itinerary", "sources", "architecture"):
            page.goto(f"{base}/{path}")
            check(f"/{path} renders", page.is_visible(f"#screen-{path}"))
        page.wait_for_selector("#arch-svg *", state="attached")
        page.click("#arch-next")
        check("architecture walkthrough responds to clicks (no inline handlers)", "Step 1" in page.inner_text("#arch-counter"))

        # ---------------------------------------------------------------- live trips
        walk = []
        if not args.offline:
            page.goto(f"{base}/plan")
            page.wait_for_selector("[data-sample]")
            samples = page.eval_on_selector_all("[data-sample]", "els => els.map(e => [e.dataset.sample, e.textContent])")
            for sid, label in samples:
                if args.samples and sid not in args.samples:
                    continue
                page.goto(f"{base}/plan")
                page.click(f"[data-sample='{sid}']")
                start = time.monotonic()
                page.click("#submit-button")
                try:
                    page.wait_for_selector("#screen-working.active", timeout=5000)
                    working_seen = True
                    page.wait_for_timeout(1500)
                    page.screenshot(path=SHOTS / f"{sid}-progress.png")
                    page.wait_for_selector("#screen-itinerary.active, #form-alert:not([hidden])", timeout=190000)
                except Exception as exc:  # noqa: BLE001
                    check(f"{sid}: finished", False, type(exc).__name__)
                    continue
                secs = round(time.monotonic() - start, 1)
                if page.is_visible("#form-alert"):
                    check(f"{sid}: produced an itinerary", False, page.inner_text("#form-alert")[:160])
                    continue
                tabs = page.locator(".day-tab").count()
                acts = page.locator(".activity-card").count()
                srcs = page.locator(".activity-tags [data-source]").count()
                status = page.inner_text("#result-budget-status")
                total = page.inner_text("#result-estimate") + " " + page.inner_text("#result-budget")
                conditions = page.inner_text("#result-conditions")
                page.wait_for_timeout(400)
                page.screenshot(path=SHOTS / f"{sid}-itinerary-desktop.png", full_page=True)
                ok = working_seen and tabs == 3 and acts >= 1 and srcs >= 1
                check(f"{sid}: itinerary with sources", ok, f"{secs}s, {tabs} days, {acts} activities, {status} {total}")
                page.locator(".activity-tags [data-source]").first.click()
                highlighted = page.locator(".source-card.highlight").count() == 1
                check(f"{sid}: Source link opens the matching source card", page.is_visible("#screen-sources") and highlighted)
                page.wait_for_timeout(600)
                page.screenshot(path=SHOTS / f"{sid}-sources-desktop.png", full_page=True)
                # Mobile: re-render the saved plan (no new model call).
                page.set_viewport_size(MOBILE)
                page.goto(f"{base}/itinerary")
                page.wait_for_selector("#itinerary-content:not([hidden])")
                page.wait_for_timeout(400)
                overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                page.screenshot(path=SHOTS / f"{sid}-itinerary-mobile.png", full_page=True)
                check(f"{sid}: mobile layout has no sideways scrolling", overflow <= 1, f"overflow {overflow}px")
                page.set_viewport_size(DESKTOP)
                walk.append({"sample": sid, "label": label, "seconds": secs, "budget": f"{status} {total}",
                             "conditions": conditions, "activities": acts, "sourceLinks": srcs})

        check("browser made no calls outside the app (no client-side Vertex AI)", not outside, ", ".join(sorted(set(outside)))[:200])
        check("no browser console errors", not console_errors, "; ".join(console_errors)[:200])
        browser.close()

    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    md = [f"# MVP-07 UI walkthrough — {stamp}", "",
          f"Driven by `scripts/ui_smoke.py` in headless Chrome against `{base}` (desktop {DESKTOP['width']}×{DESKTOP['height']}, "
          f"mobile {MOBILE['width']}×{MOBILE['height']}). Screenshots: `reports/ui/` (git-ignored).", "",
          "| Check | Result | Detail |", "|---|---|---|"]
    md += [f"| {r['check']} | {'✅' if r['ok'] else '❌'} | {r['detail']} |" for r in results]
    if walk:
        md += ["", "**Live trips**", "", "| Sample | Time | Budget | Conditions | Activities | Source links |", "|---|---|---|---|---|---|"]
        md += [f"| {w['label']} | {w['seconds']} s | {w['budget']} | {w['conditions']} | {w["activities"]} | {w['sourceLinks']} |" for w in walk]
    if not args.offline:
        out = ROOT / "docs" / "mvp" / "evidence"
        out.mkdir(parents=True, exist_ok=True)
        (out / "MVP-07-ui-walkthrough.md").write_text("\n".join(md) + "\n")
        (ROOT / "reports" / "ui" / "walkthrough.json").write_text(json.dumps({"ranAt": stamp, "results": results, "walk": walk}, indent=2))
    print(f"\n{len(results) - failures} of {len(results)} checks passed. Screenshots: reports/ui/")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

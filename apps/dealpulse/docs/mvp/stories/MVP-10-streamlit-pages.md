# MVP-10 — Streamlit pages and interaction flow

**Type:** Web UI  
**Priority:** P0  
**Estimate:** 8–12 hours  
**Story points:** 8 (five pages, persona switching, live progress, charts, citations, errors and the embedded Architecture page)  

## User story

As a sales manager, I want a clear web app where I can scan my pipeline, open a deal, read a cited brief and check its sources so that I can prepare for the forecast call without leaving one screen.

## Scope

- Streamlit multipage app (`st.navigation`) with one address per page, shared header (DealPulse brand, "viewing as" selector, "Synthetic data · no CRM changes" label) and consistent styling.
- **Pipeline** (`/pipeline`): KPI row (open pipeline, rep-weighted vs. model-weighted forecast, at-risk Commit deals); table with account, opportunity, owner, amount, stage, close date, forecast category, stage probability, model probability, gap flag and top driver; filters for team, owner, segment and forecast category; sort by gap; click a row to open the brief. **No LLM call on this page.**
- **Deal brief** (`/deal?id=…`): deal header; score card with the model vs. stage probability and a driver bar chart (contributions up/down); live progress while the workflow runs (step trace); the brief (summary, risks, next steps) with clickable citation chips; the draft CRM update with a copy button and a "review before pasting into Salesforce" note; follow-up question box with cited answers; open questions.
- **Sources** (`/sources`): the passages behind the current brief, with type, date, author role, excerpt and which claims cite them; shared vs. deal-specific clearly marked.
- **Model** (`/model`): model card from the latest evaluation report: data, features, AUC and Brier vs. baseline, calibration chart, top drivers, limits ("synthetic data", "scores deals, not people", "advisory only").
- **Architecture** (`/architecture`): embeds `dealpulse/ui/architecture/` (HTML, CSS and JS inlined into `st.components.v1.html`) with hover, pin and keyboard walkthrough working.
- **States:** loading, model warming up, no evidence for a driver, persona can't see the deal, guardrail blocked, review failed twice (score and evidence shown with a notice), service errors with a request ID.
- Charts follow one palette and are readable in light mode; tables and charts work at 1,280 px and on a 390 px phone width.
- `scripts/ui_smoke.py` (`make ui-smoke`): drives the app in headless Chrome with Playwright; `OFFLINE=1` uses recorded fixtures with no AWS calls.
- Write guide 07 (the web app).

**Out of scope:** editing CRM fields in the app, saving briefs, user accounts, dark mode and exporting to PDF.

## Acceptance criteria

- [x] All five pages load from their own address; deep links to `/deal?id=<id>` work.
- [x] Switching persona changes the visible deals immediately; a rep can't open a teammate's deal by URL.
- [ ] The Pipeline page makes no Bedrock call (checked by the UI smoke test with call counters).
- [ ] Every citation chip opens the matching source; sources are rendered from returned data, not parsed from generated text.
- [ ] The copy button copies the exact draft CRM text.
- [ ] Each error state above is reachable in offline mode and shows a safe message (request ID where relevant).
- [x] The Architecture page's hover, pin and arrow-key walkthrough work inside Streamlit.
- [ ] `make ui-smoke` passes offline and live; screenshots are saved to `reports/ui/` (git-ignored) and a summary to evidence.
- [ ] No horizontal scrolling at 390 px on the Pipeline and Deal brief pages.

## Dependencies and deliverables

**Dependencies:** MVP-05, MVP-08, MVP-09.  
**Deliverables:** `dealpulse/ui/` pages and components, `scripts/ui_smoke.py`, offline fixtures, `docs/mvp/evidence/MVP-10-ui-walkthrough.md`, guide 07.

## Completion evidence

UI walkthrough report: checks passed, screenshots of each page and state, mobile check.

## Progress record (2026-11-09) 🟡 Design reference done; Streamlit build to follow

- **Clickable mockup** of all five pages in [`artifacts/dealpulse-mockups/`](../../../artifacts/dealpulse-mockups/README.md), published as a Claude artifact (<https://claude.ai/artifact/HybQdgsSUP5qcRXXP2aZL9>). `make mockups` serves it locally.
- Uses the real synthetic CRM (60 open deals) and **real scores from the trained model** (version 1), so the Pipeline flags are genuine: 10 deals forecast as Commit/Best Case score at least 25 points below their stage (4 on the West team). Sample briefs for three deals are hand-written and labelled; they cite real note IDs and playbook sections.
- Shows the designed states: persona switching (manager sees the team, rep sees only their own; a rep opening a teammate's deal gets "Deal not available"), no-brief state, thin-notes notice, Guardrails blocking "rank my reps" and injection-style questions, Copy for the draft CRM update, citation chips that jump to the Sources page.
- **`make mockup-smoke`: 19/19 checks pass** in headless Chrome, including persona rules, citation highlighting, Architecture keyboard walkthrough (and arrow keys ignored on other pages), no sideways scrolling at 390 px, and no script errors.
- Fix carried into `dealpulse/ui/architecture/architecture.js`: arrow keys only act while the Architecture page is visible.

Still needed for this story: the Streamlit app itself (pages wired to scoring, retrieval and the workflow), the live UI smoke test and guide 07.

## Progress record (2026-11-09, later) 🟡 Streamlit app running offline; live wiring to follow

- **The real app shell is built** in Streamlit 1.67 (`dealpulse/ui/app.py` + `views/`), matching the approved mockup: Pipeline (`/`), Deal brief (`/deal`), Sources (`/sources`), Model (`/model`), Architecture (`/architecture`). `make run` serves it at http://localhost:8501/.
- **Offline mode** (`DEALPULSE_DATA=offline`, default): `data/fixtures/offline.json` (same saved deals and real model scores as the mockup) and `data/fixtures/sample_briefs.json` (one source for both the mockup and the app). No AWS calls.
- **Working in a real browser:** clicking a deal opens its brief, with the viewer and deal kept in the URL (`?as=…&id=…`) so reloads and links keep them; citation chips open Sources with the record highlighted; persona switching; draft CRM update with copy; "Ask about this deal" with the guardrail blocks; Model card with Altair charts; the Architecture page embedded with hover, pin and keyboard walkthrough. No script errors.
- **Tests:** `tests/test_ui.py`, 14 passing (39 in the whole suite): visibility rules, filters and KPIs, the flag rule against the data, **no cross-deal citations in any sample brief**, Next Step ≤ 255 characters, guardrail blocks, honest "not available" answers, and every page rendered with Streamlit's `AppTest` (including "Deal not available" for a rep).
- [Guide 07](../guides/07-web-app.md) covers running it, addresses, structure, data mode, tests and offline limits.

**Fixed while building:** styles weren't applied through `st.html` (now `st.markdown`); a `pages/` folder triggered Streamlit's older automatic page list (renamed to `views/`); Streamlit serves the default page at `/`, not `/pipeline`; clicking a table cell didn't open a deal (now single-cell selection also works); `$` pairs rendered as math (now encoded); key columns were off-screen (reordered, deal name pinned).

Still needed: live data (scores from the endpoint, retrieval, Claude briefs), the remaining states with live services (warming up, guardrail block from Bedrock, review failed twice), `scripts/ui_smoke.py` against the live app and the walkthrough evidence report.

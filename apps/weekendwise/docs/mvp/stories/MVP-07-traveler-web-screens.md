# MVP-07 — Traveler web screens and interaction flow

**Type:** User experience  
**Priority:** P0  
**Estimate:** 4–6 hours for the MVP implementation based on the existing mockup  
**Story points:** 5 (Streamlit screens from an approved mockup, for four cities)  

## User story

As a traveler, I want an approachable web flow to describe my weekend and review a plan with sources so that I can understand what the agent did and adjust my trip easily.

## Scope

Implement the existing WeekendWise visual direction and mockup screens:

1. Trip setup: destination, dates, party size, budget, interests, and constraints.
2. Agent progress: visible high-level steps and simulated-data notice.
3. Itinerary: day tabs, activities, approximate budget, assumptions, and edit action.
4. Sources & notes: citations, source metadata, and current-data limitations.

Use evergreen teal, coral, and cream; include the custom favicon. On the first MVP, Streamlit is the web framework and the browser communicates with the server-side Python workflow.

**Out of scope:** user accounts, saved trips, booking, payment, live maps, production-grade responsive administration, or client-side Vertex AI calls.

## Acceptance criteria

- [ ] The screen structure and non-violet colors match [the approved interactive mockup](../../../artifacts/google-cloud-ai-copilot/weekendwise-mockups/index.html).
- [ ] All required trip fields are sent to the server-side planner and validated before the model is called.
- [ ] Loading/progress screen appears during generation; users can return to edit inputs.
- [ ] Itinerary renders day-by-day activities, approximate budget, sample-data warnings, and valid clickable source details.
- [ ] Source screen explains the basis and limits of each recommendation.
- [ ] Error states cover invalid inputs, model failure, timeouts, and insufficient evidence without showing stack traces or credentials.
- [ ] No secrets or Vertex AI calls are made from browser-side code.
- [ ] Layout remains usable at desktop and mobile widths; favicon loads from the app.

## Dependencies and deliverables

**Dependencies:** MVP-03 and MVP-06.  
**Deliverables:** Streamlit pages/components, server request/response wiring, favicon asset, and UI smoke tests.

## Completion evidence

Record a successful walkthrough at desktop and mobile viewport sizes for all six scripted scenarios, covering all four cities.

## Completion record — ✅ Done (2026-11-06)

**Change from the original scope:** the screens are the approved mockup's own HTML and CSS, served by a small Python server (Starlette + Uvicorn) with a `/api/plan` endpoint, instead of Streamlit. This keeps the screens identical to what was approved, and all model and database calls stay on the server. Guide [06](../guides/06-web-app.md) explains the design.

| Acceptance criterion | Evidence |
|---|---|
| Screen structure and non-violet colours match the mockup | Same markup and `styles.css`; teal/coral/cream; screenshots in `reports/ui/` |
| All trip fields go to the server-side planner and are validated before the model is called | Browser checks dates/budget/interests (`ui_smoke`: invalid input never reached `/api/plan`); the planner re-validates (`test_invalid_request_is_returned_without_model_calls`) |
| Progress screen during generation; users can go back and edit | Live progress streamed from LangGraph (`plan_stream`); **Edit trip details** cancels the request |
| Day-by-day itinerary, budget, sample-data warnings, clickable sources | Day tabs, cost estimates, server-computed budget with substitutions, caveats; **Source ↗** opens the matching card (checked for all 6 trips) |
| Sources screen explains the basis and limits | One card per cited guide with passages, review date, use; stale/conflict notes and caveats |
| Errors for invalid input, model failure, timeout, insufficient evidence; no stack traces or credentials | `tests/test_web.py` (model failure, crash without leaking details, bad bodies, limits); rate-limit message seen live in the browser |
| No secrets or Vertex AI calls in the browser | Strict CSP; `ui_smoke` checks the browser contacts nothing but the app |
| Usable at desktop and mobile widths; favicon loads | 1360×900 and 390×844 for all 6 trips, 0 px sideways overflow; favicon served from `/static/` |

Walkthrough: [evidence/MVP-07-ui-walkthrough.md](../evidence/MVP-07-ui-walkthrough.md) — **31 of 31 checks**, all six scripted trips across all four cities, desktop and mobile, run with `make ui-smoke` against `make run`. The same walkthrough runs against Cloud Run with `make ui-smoke CLOUD=1`.

### Additions after completion (2026-11-06)

These came from demo preparation. The acceptance criteria above still hold.

- **Architecture page** (`/architecture`, sidebar **Under the hood**): an interactive portrait diagram of the whole system. Hover or focus any service for an **i** card explaining what it does. **Walk through a request** steps through 1–8 (request flow) and A–C (ingestion, build and deploy, guardrails) with arrow keys or buttons, and Esc to reset. The diagram matches the code: conditions are checked before retrieval, the reviewer is plain code (not a model call), and the limits are ≤ 3 model calls, 1 tool call, 1 revision, and a 150-second deadline. Files: `static/architecture.js`, `static/architecture.css`. A static copy is in the root [README](../../../README.md#architecture).
- **A bookmarkable address for each page:** `/plan`, `/itinerary`, `/sources`, `/architecture` (`/` opens the plan). The browser's back and forward buttons work, and old `#/page` links still resolve. The server answers these paths with the app page, and unknown paths fall back to the plan.
- **In-page dropdowns and calendar** (`static/select-menu.js`, `static/date-picker.js`). Chrome draws native `<select>` and date pickers as separate OS windows, which opened on the wrong monitor in a two-screen setup. Destination, **Who's going?**, and both dates now open under their field inside the page. The native inputs stay underneath (hidden selects, visible date fields for typing), so validation and the app code are unchanged. They work by keyboard: arrows, Enter, Esc, type-ahead in lists, and Page Up/Down for months. The end-date calendar greys out days before the start date.
- The same Architecture page, page addresses (`make mockups`), and dropdowns are in the static HTML mockup.

Checks after these changes: `make ui-smoke OFFLINE=1` passes 13 of 13 (including `/architecture` and its walkthrough, with no inline handlers under the strict CSP), the unit tests pass 103 of 103, and the dropdowns and calendar were driven by mouse and keyboard in headless Chrome with no console errors. The dropdowns were deployed to Cloud Run (image `20261106-230443`). The calendar is in the code but hasn't been deployed yet, because the stack was then removed for the IAC-06 rehearsal.

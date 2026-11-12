# CL-12 — Streamlit story mode: the five acts

**Phase:** 4 · Experience  
**Type:** UI  
**Priority:** P0  
**Estimate:** 8–12 hours  
**Story points:** 8 (five interactive acts on real data, with a presenter flow)  
**Target day:** Sat 14 Nov

## User story

As the presenter, I want a guided, interactive app that tells the story one act at a time, so that a technical and a non-technical audience can both follow it and I can go deeper wherever they ask.

## Scope

- Streamlit app in the `app` container on http://127.0.0.1:8501. A **story navigator** (Act 1 → 5, then the POV scorecard) with a progress bar, next and back buttons, and keyboard-friendly navigation. Each act has a one-sentence headline, the main interaction, and a collapsed **"Go deeper"** section for technical questions.
- **Act 1 · The confident wrong answer:** the COO's question pre-filled; "Ask the agent" plays the naive run with tool calls appearing as they happen; the answer, then a **"What went wrong"** panel with one card per trap (the SQL line, the effect, the fix in later acts).
- **Act 2 · Move:** a connector panel per source (status, last sync, rows synced, MAR estimate) from `fivetran_log`; a **"Run incremental sync"** button that runs batch 2 and shows only the changed rows; the soft-deleted rows highlighted; the new `ZZ_CARRIER_ID` column appearing; history rows for an account's tier change.
- **Act 3 · Transform and Trust:** a lineage view from the dbt manifest (sources → staging → marts → metrics); test results; the **"Break it"** button that runs `make break TRAP=T1` and shows the failing test, then restores it; the metric definitions; the same query from DuckDB and Trino side by side (CL-08).
- **Act 4 · Context:** the same question; the governed run with each MCP tool call labelled by server (dbt MCP, metrics, freshness); the structured answer with definitions, lineage and freshness badges; a **side-by-side** comparison with Act 1 and both scores; a toggle to turn on the stale-Zendesk scenario and see the answer change.
- **Act 5 · Activate:** placeholder until CL-14.
- **Live and replay:** a clear mode badge; in live mode, a free-text box to ask other questions.
- Labelled throughout as synthetic data. Works at 1280-pixel and 1920-pixel widths for screen sharing; readable at 125% zoom.

**Out of scope:** login, multi-user state, mobile layout.

## Acceptance criteria

- [ ] All five acts work end to end in replay mode with no network.
- [ ] Each act loads in under 2 seconds (warm), apart from actions that deliberately run a job, which show progress.
- [ ] "Run incremental sync" and "Break it" run real jobs and update the screen from the warehouse, not from canned data.
- [ ] The side-by-side comparison shows both answers, both scores and the traps behind each naive mistake.
- [ ] A presenter can go from Act 1 to Act 5 using only the navigator in under 10 minutes following the talk track.
- [ ] UI tests cover each act's main path (Streamlit's testing API).

## Dependencies and deliverables

**Dependencies:** CL-05, CL-06, CL-11 (and CL-08 for the two-engine panel).  
**Deliverables:** `contextloop/ui/`, UI tests, `docs/mvp/evidence/CL-12-screens/`.

## Completion evidence

Screenshots of each act and the UI test output.

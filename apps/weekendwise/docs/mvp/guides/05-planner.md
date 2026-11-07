# Guide 05 — The itinerary planner (LangGraph)

**Related story:** [MVP-06](../stories/MVP-06-langgraph-planner-tool-reviewer.md)
**Code:** [weekendwise/planner.py](../../../weekendwise/planner.py), [weekendwise/review.py](../../../weekendwise/review.py), [weekendwise/tools.py](../../../weekendwise/tools.py)

## What it does

`Planner.plan(request)` turns a trip request into a cited, budgeted itinerary, or an honest "can't do that" response.

```
normalize ─┬─(invalid request)─────────────────────────────────────────► respond  (invalid_request)
           └─► conditions? ─► retrieve ─┬─(nothing relevant)────────────► respond  (needs_clarification)
                                        └─► draft ─► review ─┬─(issues, first time)─► draft (one revision)
                                                             └─────────────────────► respond  (complete)
```

| Step | What happens |
|---|---|
| **normalize** | Validates city (4 supported), dates (≤ 3 days), travelers (1–8), budget ($50–$10,000), interests. Invalid → errors, **no model or tool calls**. Decides whether to check conditions: only if the request mentions weather words (rain, indoor, heat, fog…), for the weekday named (e.g. "Saturday") or the first day. |
| **conditions** | Calls `check_local_conditions(city, demo_date)` **at most once**. Reads only the bundled fixture files; any city/date pair that isn't seeded fails closed (`rejected_unseeded_date`) and the plan continues with a caveat. No network, booking, payment, or writes. |
| **retrieve** | Up to 5 searches through the MVP-05 retriever, in priority order: the traveler's own words (constraints + notes), indoor options if conditions recommend it, budget, each interest (up to 3), getting around. When the cap is hit, getting around goes first, then the third interest. Keeps the 10 closest passages. No interests, or nothing relevant → asks a clarifying question, **no model call**. |
| **draft** | One Gemini call with strict JSON output (`DRAFT_SCHEMA`). Passages are labelled `S1…S10` and marked untrusted. Rules: cite every activity, estimates in USD, hard budget with honest over-budget flag and substitutions, respect simulated weather, never claim bookings, unanswerable requests listed, **designated-driver guidance for anything with alcohol**. Invalid JSON gets one repair attempt. |
| **review** | Deterministic code, not a model. Checks dates, citation labels, activity costs fit their budget lines, line items add up, over-budget flagged with substitutions, no outdoor-only plans on a day flagged indoor, no booking claims, drink-driving guidance. Any issue → **one** revision with the issues as feedback. |
| **respond** | Server recomputes the budget total and status itself. Activities whose citations don't check out are dropped and listed under uncertainties. Citations map to real chunk IDs and are returned separately. Adds caveats (simulated conditions; never drink and drive whenever alcohol appears). |

## Limits (enforced in code, covered by tests)

| Limit | Value | Setting |
|---|---|---|
| Tool calls | 1 | hard-coded |
| Retrieval searches | 5 | `PLANNER_MAX_RETRIEVAL_QUERIES` |
| Evidence passages | 10 | `PLANNER_MAX_EVIDENCE` |
| Gemini calls | 3 (draft, revision, JSON repair) | `PLANNER_MAX_MODEL_CALLS` |
| Revisions | 1 | hard-coded |
| Output tokens per call | 4,096 | `MAX_OUTPUT_TOKENS` |
| Wall-clock budget | 150 s, checked before every model call | `PLANNER_DEADLINE_SECONDS` |
| Graph steps | 20 | LangGraph `recursion_limit` |

## Response (what the UI receives)

`status` (`complete` · `invalid_request` · `needs_clarification` · `error`), `days[].activities[]` (time, title, description, area, category, estimated cost, `citations` = chunk IDs), `budget` (line items, server-computed total, `on-track`/`over-budget`, substitutions), `citations[]` (chunk, source, title, review date, excerpt, used for), `uncertainties`, `unansweredRequests`, `notes`, `caveats`, `toolCalls`, `review` (outcome, revision count, checks, first-draft issues), `trace` (user-safe step labels only, e.g. "Checked simulated local conditions"), and `usage` (model, tool, and search counts, elapsed ms).

## Try it

```bash
make test        # 72 offline tests, including planner bounds
make scenarios   # all 6 scripted trips, live, as weekendwise-run; writes docs/mvp/evidence/MVP-06-scenarios.md
make scenarios S=SCENARIO-06-NAPA-HOT-TASTING
```

A full run takes about 2 minutes and costs a few cents. Full responses go to `reports/scenarios-latest.json` (git-ignored).

## Known behaviour

- The model tends to pick the **low end** of each guide's price range, so estimates are optimistic. Budgets are still itemized and labelled as estimates.
- Totals vary between runs (scenario 1 ranged $470–$560 across four runs).
- In live runs every first draft has passed review, so the revision path is proven by unit tests rather than live runs.

## Streaming (used by the web app)

`Planner.plan_stream(request)` runs the same graph and yields `("step", {...})` as each node finishes, then `("result", response)`. The web server sends these to the browser as server-sent events, so the progress screen shows real steps. See [guide 06](06-web-app.md).

# Guide 06 — The WeekendWise web app

**Related stories:** [MVP-07](../stories/MVP-07-traveler-web-screens.md) · [MVP-03](../stories/MVP-03-cloud-run-deploy.md) · [MVP-09](../stories/MVP-09-observability-release-demo.md)
**Run it:** `make run`, then open http://localhost:8080 (each plan costs about 1 cent)

## What it is

The approved mockup's screens, now connected to the real planner. The browser only talks to this app's own server. Every Google Cloud call (Firestore search, Gemini, embeddings) happens on the server, as `weekendwise-run`.

```
browser ──HTTPS──► weekendwise.web.server (Starlette + Uvicorn)
                     ├─ GET  /, /plan, /itinerary, /sources, /architecture   the screens (one page)
                     ├─ GET  /api/config     cities, interests, sample trips, limits (from data/seed)
                     ├─ POST /api/plan       runs the LangGraph planner; streams progress, then the plan
                     ├─ GET  /health         process is up (no cloud calls; /healthz also works locally)
                     └─ GET  /readyz         Firestore answers a 1-document read
```

Why not Streamlit, as the story first said: the approved mockup is custom HTML and CSS. Serving it directly keeps the screens identical to what was approved, and the server stays plain Python. The story records this change.

## The four screens

| Screen | What's real now |
|---|---|
| Plan a trip | All four cities, dates (up to 3 days), party size, budget, interests, and an "Anything else?" box. **Try a sample** fills in one of the six scripted trips. The browser checks dates, budget, and interests before sending; the server checks everything again. |
| Putting it together | Live progress, streamed from the planner as each step finishes. A weather check only shows up when your request mentions weather. "Edit trip details" cancels and goes back. |
| My itinerary | Day tabs, cited activities with cost estimates, a budget card with the server's own total (and cheaper swaps when over budget), "why this fits", what couldn't be answered, and how the plan came together (searches, model calls, time). A banner appears if the reviewer revised the draft or still has concerns. |
| Sources & notes | One card per guide that was cited, with the passages used, its review date, and what it was used for. **Source** links on activities jump to the right card. Stale or conflicting sources and safety caveats are listed. |

The last plan is kept in the browser tab (session storage), so a refresh keeps it.

## Errors the traveler can see

| Situation | What they see |
|---|---|
| Bad input (dates, budget, no interest) | A message on the form; nothing is sent |
| Unsupported city, or server-side validation fails | "Please check your trip details" with the reasons |
| Nothing in the guides fits | "We need a little more to go on" with a question |
| Model or Firestore failure, or the planner's own limits | A short, plain message; never a stack trace or a credential |
| Over 6 plans in 10 minutes, or 30 a day on one instance | "Please wait a few minutes" or "try again tomorrow" |
| No answer within 3 minutes | "The planner took too long to answer" |

## Limits and security

- Request body at most 8 KB; free text is cut to 200/500 characters before it reaches the prompt.
- Per instance: 3 plans at once, 6 per person per 10 minutes, and 30 a day (`PLAN_MAX_CONCURRENT`, `PLAN_RATE_PER_CLIENT`, `PLAN_DAILY_LIMIT`). These are in-memory speed bumps, not a security boundary.
- A strict Content-Security-Policy: scripts only from the app itself, no inline handlers, and no calls to other sites. The UI smoke test checks the browser contacts nothing else.
- All model text is escaped before it's shown.

## Logs

Each request gets an ID (sent back as `X-Request-ID`). The server writes one JSON line per event, which Cloud Logging picks up. The fields are the stage, model ID, latency, token counts, retrieval result counts, tool count, status, and error category. Prompts, the traveler's notes, guide text, and model output are never logged. The [runbook](../runbook.md#logs) has the queries.

## Testing

```bash
make test                 # offline: server routes, streaming, limits, errors, logging (no cloud calls)
make ui-smoke OFFLINE=1   # free: pages, validation, architecture page, no outside calls (needs make run)
make ui-smoke             # + the 6 sample trips in Chrome at desktop and phone sizes (~6 cents)
```

`make ui-smoke` writes [evidence/MVP-07-ui-walkthrough.md](../evidence/MVP-07-ui-walkthrough.md) and screenshots in `reports/ui/`. It uses your installed Google Chrome; no browser download is needed.

## Files

| File | What |
|---|---|
| `weekendwise/web/server.py` | Routes, limits, streaming, health, security headers |
| `weekendwise/web/static/index.html`, `styles.css`, `architecture.*`, `favicon.svg` | The approved mockup's markup and styles |
| `weekendwise/web/static/app.js`, `app.css` | Talking to the server and rendering real plans |
| `weekendwise/observability.py` | JSON logging and timing wrappers |
| `scripts/ui_smoke.py` | Browser walkthrough |

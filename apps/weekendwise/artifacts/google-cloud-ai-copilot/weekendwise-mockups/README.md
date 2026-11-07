# WeekendWise local UI prototype

> **The live app is built.** `make run` serves these same screens connected to the real planner (Firestore + Gemini) at http://localhost:8080; see [guide 06](../../../docs/mvp/guides/06-web-app.md). This folder stays as the approved design reference.

This folder contains the four-screen, browser-only WeekendWise prototype. It is intentionally disconnected from Google Cloud, Vertex AI, Firestore, LangGraph, and any live travel service. The progress animation and itinerary are local sample behavior, not an AI response.

## Run locally

### Option A — open the file

Open `index.html` directly in a modern browser. No installation or credentials are required.

### Option B — local server with clean page paths (recommended)

From the repository root, run `make weekendwise-mockups`, then open `http://localhost:8000/plan`. From this app directory, run `make mockups`. The small static server (`scripts/serve_mockups.py`, Python standard library only) binds to `127.0.0.1` and answers page paths such as `/architecture` with `index.html`. It is not the future Streamlit/Python backend. Use `make mockups PORT=9000` from this app directory to pick another port.

Avoid running the generic Python static server without `--bind 127.0.0.1`: its default can listen on network interfaces and expose the files to other devices on your LAN. Do not expose a preview server to the internet or use it as a production server.

## Screens included

1. **Plan a trip:** destination, dates, party size, budget, and selectable interests.
2. **Agent progress:** simulated steps and a sample-data notice.
3. **Itinerary:** three day tabs, activities, sample budget, and local trip summary.
4. **Sources & notes:** source cards and an explicit explanation of prototype limitations.
5. **Architecture** (sidebar → *Under the hood*): a portrait service map of the target MVP on Google Cloud. Hover a service (or its ⓘ) for what it does; click to pin details. The walkthrough steps through a request (1–8) and behind-the-scenes flows (A–C); use ← / → keys while presenting and Esc to show the full diagram. Code lives in `architecture.js` and `architecture.css`.

The MVP supports San Francisco, Portland, Santa Cruz, and Napa Valley, but this mockup only renders the San Francisco sample itinerary; other destinations show a notice. Sample itineraries for every city are in `data/seed/sample_itineraries/`. The fixed sample estimate is $486; changing the input budget updates the budget status, not the underlying activity prices.

## Page addresses

Each page has its own bookmarkable address:

| Page | With `make mockups` | Opened as a file |
|---|---|---|
| Plan a trip | `http://localhost:8000/plan` (also `/`) | `index.html#/plan` |
| My itinerary | `http://localhost:8000/itinerary` | `index.html#/itinerary` |
| Sources & notes | `http://localhost:8000/sources` | `index.html#/sources` |
| Architecture | `http://localhost:8000/architecture` | `index.html#/architecture` |

Back/Forward move between pages, refresh keeps your place, and unknown addresses fall back to Plan a trip. Opening the file directly uses `#/` addresses because a file can't have sub-paths. Old `#/page` links still work on the server and are tidied to the clean path.

## Brand and assets

Evergreen teal, warm coral, and cream; no violet palette. The custom SVG favicon is `favicon.svg`.

## Next implementation boundary

This prototype validates screen layout and navigation only. Later work can replace the local progress/sample behavior with the Streamlit backend and wire one service at a time: Vertex AI embeddings, Firestore retrieval, Gemini generation, then the bounded LangGraph workflow and real evaluation. Conditions stay labeled as simulated until an approved data integration is implemented.

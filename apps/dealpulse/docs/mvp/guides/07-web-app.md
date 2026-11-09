# 07 — The web app

DealPulse's web app is a Streamlit app with five pages. Today it runs in **offline mode**: saved synthetic deals with real scores from the trained model, and hand-written sample briefs. It makes no AWS calls. Live services replace the saved data page by page (MVP-05 scoring, MVP-07 retrieval, MVP-08 briefs).

## Run it

```bash
make venv     # once: installs Streamlit and the rest from requirements*.txt
make run      # → http://localhost:8501/   (PORT=8600 for another port; binds to 127.0.0.1 only)
```

## Pages and addresses

| Page | Address | Notes |
|---|---|---|
| Pipeline | `/` | Streamlit serves the default page at the root. Click any deal (or tick its row) to open its brief. |
| Deal brief | `/deal?id=<opportunity>&as=<user>` | Deep links work; the viewer and deal are kept in the URL, so reloads keep them. |
| Sources | `/sources?id=…&as=…&cite=<record>` | Citation chips on the brief link here and highlight the record. |
| Model | `/model` | Model card from the evaluation report. |
| Architecture | `/architecture` | The interactive service map (same files as `dealpulse/ui/architecture/`). Click inside it, then use ← and →. |

**Viewing as** (sidebar) switches between managers, who see their team's deals, and account executives, who see only their own. It's a simulated sign-in. Access is checked before anything about a deal is shown: a rep opening a teammate's deal by URL gets "Deal not available".

## How it's built

```text
dealpulse/ui/
  app.py          entry point: page config, theme, navigation, sidebar ("viewing as")
  logic.py        no Streamlit: data provider, access rules, filters, KPIs, offline answers (unit-tested)
  state.py        viewer and deal kept in the URL (?as=…&id=…)
  theme.py        styles and small HTML helpers matching the approved mockup (values are escaped)
  views/          one script per page: pipeline, deal, sources, model, architecture
  architecture/   the interactive service map
data/fixtures/
  offline.json        saved deals, notes, scores, drivers, model report (built by scripts/build_mockup_data.py)
  sample_briefs.json  hand-written sample briefs; also generates the mockup's sample-briefs.js
.streamlit/config.toml  theme (navy sidebar, blue accent, IBM Plex / Newsreader fonts), no usage stats
```

The page scripts live in `views/`, not `pages/`: a folder named `pages/` makes Streamlit switch to its older automatic page list when someone opens a page URL directly.

## Data mode

`DEALPULSE_DATA=offline` is the default and the only mode so far. Setting anything else stops with a clear message until the live providers exist.

## Tests

```bash
make test           # includes tests/test_ui.py: 9 logic tests + 5 page tests with Streamlit's AppTest (no browser)
make mockup-smoke   # browser checks for the clickable mockup (the design reference)
```

The logic tests include a leak check: every citation in every sample brief points to that deal's own notes or to shared guidance.

## Known limits (offline mode)

- Briefs and answers exist for three deals only (Northbeam Logistics Group, Harborline Freight, Silverpine Retail Group); other deals show the no-brief state.
- "Ask about this deal" mirrors the guardrail's two blocks (judging employees, prompt attacks) with simple pattern checks. The real check is Bedrock Guardrails (IAC-05, MVP-08).
- The Copy button is Streamlit's copy icon on the combined Next Step / Description box.

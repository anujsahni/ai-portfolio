# DealPulse clickable UI mockup

The design reference for MVP-10: the five pages of the app as a browser-only prototype. It runs no AWS calls and writes nothing. Published as a Claude artifact: <https://claude.ai/artifact/HybQdgsSUP5qcRXXP2aZL9> (private to its owner until shared).

## Run locally

```bash
make mockups          # then open http://localhost:8000/#pipeline   (binds to 127.0.0.1 only)
```

Or open `index.html` directly in a browser. Fonts load from Google Fonts; everything else is local.

## Pages

| Page | Address | What it shows |
|---|---|---|
| Pipeline | `#pipeline` | KPI tiles (open pipeline, forecast by stage vs. by model, deals where the model disagrees), filters, and every open deal with stage probability next to model probability |
| Deal brief | `#deal` | Win probability and its drivers ("what you can act on" / all factors), how the brief was made, the cited brief, a draft Salesforce update with Copy, "Ask about this deal", latest notes |
| Sources | `#sources` | Every record the brief cites: this deal's notes and shared playbook/policy sections, with where each is cited |
| Model | `#model` | Model card: AUC and Brier vs. Salesforce's stage probability, calibration chart, what moves the score, what it uses, limits |
| Architecture | `#architecture` | The interactive service map (same code as `dealpulse/ui/architecture/`) |

The **Viewing as** selector in the sidebar switches between managers (see their team's deals) and account executives (see only their own). Opening a teammate's deal as a rep shows "Deal not available".

## Where the content comes from

| Content | Source |
|---|---|
| Accounts, deals, owners, notes | The synthetic CRM from `make data` (MVP-03) |
| Win probabilities and drivers | **The real trained model** (version 1, XGBoost on SageMaker), run locally on each open deal's features as of the snapshot date |
| Model page metrics | The real evaluation report from `make train` (MVP-04) |
| Deal briefs, Q&A answers | **Written by hand** for three deals (Northbeam Logistics Group, Harborline Freight, Silverpine Retail Group), citing real note IDs and playbook sections. In the live app Claude writes them (MVP-08). Labelled "Sample" on the page. |
| Guardrails demo | "Rank my reps…" and prompt-injection questions show the blocked message the real guardrail returns (IAC-05) |

## Rebuild the data

`sample-data.js`, `architecture.js` and `architecture.css` are generated; don't edit them here.

```bash
make data LOCAL=1                                                # synthetic CRM
python scripts/build_mockup_data.py features /tmp/rows.json      # open-deal features
# score /tmp/rows.json with the trained model: scripts/score_rows.py MODEL_DIR /tmp/rows.json /tmp/scores.json
#   (needs XGBoost 3.2; on macOS run it in a Linux container)
python scripts/build_mockup_data.py assemble /tmp/scores.json   # writes sample-data.js, copies the Architecture files
make mockup-smoke                                                # 19 browser checks
```

## What the mockup found

- The model leans heavily on stage. Harborline Freight (Negotiation, no executive engaged, two slips) scores 80%. The brief's evidence is what flags the risk, which is the design's intent: the score advises, the brief explains.
- For one deal the model scores an 18% discount as slightly positive, because "has a discount" also means "reached Proposal". MVP-05 should phrase discount drivers carefully or hide confounded ones.

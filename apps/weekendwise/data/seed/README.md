# WeekendWise Firestore seed data

Sample JSON for every collection the MVP uses, laid out the way it will be written to Firestore:

```
data/seed/<collection>/<documentId>.json
```

- **Folder name = collection ID. File name (without `.json`) = document ID. File contents = document fields.**
- Nothing here has been written to Firestore yet. A later import job (MVP-04) reads these folders and upserts them.
- All content is synthetic demo data. No real people, bookings, prices, or live conditions.

## Rebuild and validate

```bash
python3 scripts/build_seed_data.py          # regenerate generated folders + validate everything
python3 scripts/build_seed_data.py --check  # validate only
```

The script uses only the Python standard library and makes no network calls. Re-running it on unchanged input produces identical files.

Validation checks include: every itinerary citation resolves to an active, same-city chunk; budget line items add up and match the on-track/over-budget status; tool calls are allowlisted and point at a seeded conditions doc; and every source ID referenced by interests, budget categories, scenarios, and evaluation cases exists.

## Collections

| Collection | Docs | How it's made | Used by | Notes |
|---|---|---|---|---|
| `guide_sources` | 47 | Generated from `data/guides/*.md` | MVP-04, MVP-05 (citation metadata) | One per guide. Includes `cityId`, `checksum`, `active`, `version`, `lastReviewed`. |
| `guide_chunks` | 95 | Generated from `data/guides/*.md` | MVP-04, MVP-05 (vector search) | One per paragraph. ID `<sourceId>--cNN`. `embedding` is `null` until ingestion fills it. `corpusVersion` comes from the city. |
| `corpus_manifests` | 4 | Generated | MVP-04 (ingestion summary) | One per city corpus: `sf-demo-v1`, `pdx-demo-v1`, `sc-demo-v1`, `napa-demo-v1`. |
| `evaluation_cases` | 30 | Generated from `data/evaluation_cases.json` | MVP-08 | One per case, each with a `city`. Edit the source JSON, not these files. |
| `cities` | 4 | Hand-written | MVP-07 (destination field, city preview), MVP-05 (city filter) | All four are `supported: true`. Portland, Santa Cruz, and Napa Valley are also the mockup's "trending" suggestions. Each has region, areas, airports, distance from SF, getting around, highlights per interest, seasons, a demo budget range, tips, `corpusVersion`, and `plannerReadiness`. |
| `interests` | 6 | Hand-written | MVP-07 (interest chips), MVP-06 (query hints) | `relatedSourceIdsByCity` maps each city to its matching guides. Every interest has at least one guide in every city (enforced by the build script). |
| `budget_categories` | 4 | Hand-written | MVP-06 (budget summary), MVP-07 (budget card) | Stays, food & coffee, activities, local transit, each with `relatedSourceIdsByCity`. |
| `local_conditions` | 14 | Hand-written | MVP-06 (`check_local_conditions` tool) | ID `<cityId>__<YYYY-MM-DD>`. SF: May 16–18 and June 12–13, 2027. Other cities: May 14–16, 2027 (Portland rain Saturday, Santa Cruz fog Friday, Napa heat Saturday). All `simulated: true`. Unseeded dates must fail closed. |
| `app_config` | 1 | Hand-written | All server code | `supportedCityIds`, `corpusVersions` per city, retrieval top-k, call/token limits, tool allowlist, budget rules, form options, disclaimers. Model IDs stay `null` until MVP-02 confirms them. |
| `trip_scenarios` | 6 | Hand-written | MVP-06, MVP-07, MVP-09 (scripted demo) | Three San Francisco trips plus one each for Portland, Santa Cruz, and Napa Valley, with expected tool count, budget status, and review outcome. |
| `sample_itineraries` | 6 | Hand-written | MVP-07 (UI fixture), MVP-06 (expected output shape) | One per scenario. Planner response shape: days, activities, citations, budget, caveats, trace, review. |

### Corpus by city

| City | Guides | Chunks | Topics |
|---|---|---|---|
| San Francisco | 17 (16 active) | 35 | Neighborhoods, museums, waterfront, transit, food, lodging, live music, planning policies, plus 3 test fixtures |
| Portland | 10 | 20 | Pearl District/Powell's, eastside streets, Washington Park, food carts, art museum/Alberta, live music, TriMet, rainy-day planning, accessibility, budget |
| Santa Cruz | 10 | 20 | West Cliff/Natural Bridges, Boardwalk/Wharf, redwoods, downtown/MAH, Capitola, casual food, live music, fog/coastal planning, accessibility, budget + getting around |
| Napa Valley | 10 | 20 | Oxbow/downtown Napa, wine tasting (no-drink-driving rule), Yountville, Calistoga, Vine Trail, art, live music, hot-day planning, accessibility, budget + getting around |

Every city has its own weather-planning, accessibility, and budget guide, so city-filtered retrieval always returns the right planning rules for that city.

### The six scripted scenarios

| Scenario | What it shows |
|---|---|
| `SCENARIO-01-ART-COFFEE` | Preference-based plan, 2 travelers, $486 of $600, no tool call. Mirrors the mockup. |
| `SCENARIO-02-RAINY-SATURDAY` | One `check_local_conditions` call for 2027-05-15 returns simulated rain; Saturday swaps to an indoor museum. |
| `SCENARIO-03-TIGHT-BUDGET` | $335 vs. $300 budget → OVER BUDGET with substitutions, one reviewer revision, and an unanswered live-hours request. |
| `SCENARIO-04-PORTLAND-RAINY` | Tool call for Portland 2027-05-15 returns simulated rain; gardens move to Sunday. $470 of $650. |
| `SCENARIO-05-SANTA-CRUZ-COAST` | Coast, redwoods, food, and a show with a car. $640 of $750, no tool call. |
| `SCENARIO-06-NAPA-HOT-TASTING` | Tool call returns simulated heat; $1,100 vs. $900 → OVER BUDGET with swaps to $850, one revision, and a no-drink-driving caveat. |

### Test fixtures in the corpus

Three San Francisco guides exist only for retrieval and safety tests, and cross-city filtering is tested with real guides from other cities (marked with `testFixture`):

| Source ID | Purpose |
|---|---|
| `SF-STALE-FERRY-HOURS` | Stale (2024) note that conflicts with `SF-NEIGHBORHOOD-FERRY`. |
| `SF-ADVERSARIAL-INJECTION` | Contains prompt-injection text asking the model to book and fetch a URL. |
| `SF-RETIRED-CABLECAR` | `active: false`. Must never be returned. |
| `PDX-*` (any Portland guide) | Now real Portland content. A San Francisco query must still never return it (PLAN-016). |

## Loading into Firestore

`make seed` loads these folders into Firestore (MVP-04). See [how-to 00, Step 9](../../docs/mvp/guides/00-provision-with-terraform.md).

- **Loaded by default:** `app_config`, `cities`, `interests`, `budget_categories`, `local_conditions`, `guide_sources`, `guide_chunks`, `corpus_manifests`.
- **Only with `FIXTURES=1`:** `trip_scenarios`, `sample_itineraries`, `evaluation_cases`.
- **Document ID** = file name. Files are written as-is, plus `seedChecksum` and `seededBy`. Chunks also get `embedding` (a Firestore Vector), `embeddingModel`, `embeddingDimension`, `embeddingStatus: "ready"`, and `embedChecksum`.
- **Idempotent.** Unchanged documents aren't rewritten; unchanged chunks aren't re-embedded; documents removed from `data/seed/` are deleted only if `make seed` wrote them.
- **Dates** stay as ISO strings.
- **Identity:** writes as `weekendwise-ingest`; the Cloud Run runtime (`weekendwise-run`) can only read.
- Never store real traveler requests or chat history (out of MVP scope).

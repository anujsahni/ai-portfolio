# MVP-07 UI walkthrough — 2026-11-06T21:34:11+00:00

Driven by `scripts/ui_smoke.py` in headless Chrome against `http://localhost:8080` (desktop 1360×900, mobile 390×844). Screenshots: `reports/ui/` (git-ignored).

| Check | Result | Detail |
|---|---|---|
| plan page loads with the app's own favicon | ✅ |  |
| all four cities are selectable | ✅ | San Francisco, Napa Valley, Portland, Santa Cruz |
| inspiration card follows the city | ✅ |  |
| end-before-start is blocked in the browser | ✅ |  |
| 4-day trip is blocked in the browser | ✅ |  |
| too-small budget is blocked in the browser | ✅ |  |
| invalid input never reached the planner | ✅ | 0 calls |
| /itinerary renders | ✅ |  |
| /sources renders | ✅ |  |
| /architecture renders | ✅ |  |
| architecture walkthrough responds to clicks (no inline handlers) | ✅ |  |
| SCENARIO-01-ART-COFFEE: itinerary with sources | ✅ | 18.0s, 3 days, 6 activities, ON TRACK $470 of $600 |
| SCENARIO-01-ART-COFFEE: Source link opens the matching source card | ✅ |  |
| SCENARIO-01-ART-COFFEE: mobile layout has no sideways scrolling | ✅ | overflow 0px |
| SCENARIO-02-RAINY-SATURDAY: itinerary with sources | ✅ | 15.0s, 3 days, 4 activities, ON TRACK $380 of $700 |
| SCENARIO-02-RAINY-SATURDAY: Source link opens the matching source card | ✅ |  |
| SCENARIO-02-RAINY-SATURDAY: mobile layout has no sideways scrolling | ✅ | overflow 0px |
| SCENARIO-03-TIGHT-BUDGET: itinerary with sources | ✅ | 17.5s, 3 days, 7 activities, OVER BUDGET $195 of $150 |
| SCENARIO-03-TIGHT-BUDGET: Source link opens the matching source card | ✅ |  |
| SCENARIO-03-TIGHT-BUDGET: mobile layout has no sideways scrolling | ✅ | overflow 0px |
| SCENARIO-04-PORTLAND-RAINY: itinerary with sources | ✅ | 56.8s, 3 days, 7 activities, ON TRACK $537 of $650 |
| SCENARIO-04-PORTLAND-RAINY: Source link opens the matching source card | ✅ |  |
| SCENARIO-04-PORTLAND-RAINY: mobile layout has no sideways scrolling | ✅ | overflow 0px |
| SCENARIO-05-SANTA-CRUZ-COAST: itinerary with sources | ✅ | 14.5s, 3 days, 7 activities, ON TRACK $610 of $750 |
| SCENARIO-05-SANTA-CRUZ-COAST: Source link opens the matching source card | ✅ |  |
| SCENARIO-05-SANTA-CRUZ-COAST: mobile layout has no sideways scrolling | ✅ | overflow 0px |
| SCENARIO-06-NAPA-HOT-TASTING: itinerary with sources | ✅ | 16.0s, 3 days, 8 activities, ON TRACK $900 of $900 |
| SCENARIO-06-NAPA-HOT-TASTING: Source link opens the matching source card | ✅ |  |
| SCENARIO-06-NAPA-HOT-TASTING: mobile layout has no sideways scrolling | ✅ | overflow 0px |
| browser made no calls outside the app (no client-side Vertex AI) | ✅ |  |
| no browser console errors | ✅ |  |

**Live trips**

| Sample | Time | Budget | Conditions | Activities | Source links |
|---|---|---|---|---|---|
| SF art & coffee | 18.0 s | ON TRACK $470 of $600 | ☁ No conditions check requested | 6 | 7 |
| SF rainy Saturday | 15.0 s | ON TRACK $380 of $700 | ☁ Simulated conditions for May 15 · not a forecast | 4 | 6 |
| SF tight budget | 17.5 s | OVER BUDGET $195 of $150 | ☁ No conditions check requested | 7 | 9 |
| Portland rain | 56.8 s | ON TRACK $537 of $650 | ☁ Simulated conditions for May 15 · not a forecast | 7 | 8 |
| Santa Cruz coast | 14.5 s | ON TRACK $610 of $750 | ☁ No conditions check requested | 7 | 9 |
| Napa hot day | 16.0 s | ON TRACK $900 of $900 | ☁ Simulated conditions for May 15 · not a forecast | 8 | 12 |

# MVP-05 — Deal scoring and plain-language drivers

**Type:** ML serving  
**Priority:** P0  
**Estimate:** 3–5 hours  
**Story points:** 3 (endpoint client, batch scoring, driver wording and cold-start handling)  

## User story

As a sales manager, I want each deal's win probability with its top reasons in plain words so that I can tell at a glance why a deal looks risky.

## Scope

- `dealpulse/scoring.py`:
  - `score_deals(deals, as_of)` builds features with `features.py` and calls the SageMaker endpoint **once** for any number of deals (≤ 100 per call);
  - returns, per deal: probability, the Salesforce stage probability, the gap, and the top 3–5 drivers with direction;
  - 10-minute in-memory cache keyed by deal ID and snapshot version.
- `dealpulse/drivers.py`: maps feature contributions to short phrases with the actual value, e.g. "No executive meeting in 34 days ↓", "Close date pushed 3 times ↓", "Expansion of an existing customer ↑". Every feature has a phrase; contributions below a threshold are not shown.
- **Gap flag:** a deal is flagged when its forecast category is Commit or Best Case and the model probability is at least 25 points below the stage probability (thresholds in config).
- **Cold start:** detect a slow first call, retry once with a longer timeout, and return a "model warming up" status the UI can show.
- Endpoint errors (not deployed, access denied, timeout) return a clear status; the Pipeline page can still show CRM fields without scores.

**Out of scope:** the Pipeline page UI itself (MVP-10), LLM-written explanations of the score (MVP-08) and per-user score history.

## Acceptance criteria

- [ ] Scoring all ~60 open deals takes one endpoint call and under 3 seconds when warm.
- [ ] Each result includes probability, stage probability, gap, flag and 3–5 driver phrases with real values.
- [ ] Driver phrases cover every feature and are unit-tested against fixed contributions.
- [ ] The gap flag follows the configured rule and is unit-tested at the boundaries.
- [ ] A cold start shows a "warming up" status instead of an error; endpoint-missing and access-denied produce safe, specific messages.
- [ ] Scores for a fixed deal and date match the offline evaluation's prediction for the same row (within 0.001).

## Dependencies and deliverables

**Dependencies:** MVP-04 (an approved model deployed through IAC-05).  
**Deliverables:** `scoring.py`, `drivers.py`, config entries, unit tests, `make score DEAL=<id>` for quick checks.

## Completion evidence

Timed `make score` for one deal and for all open deals (cold and warm), and the list of flagged deals.

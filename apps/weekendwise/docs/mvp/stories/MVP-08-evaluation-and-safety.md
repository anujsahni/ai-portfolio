# MVP-08 — Evaluation, safety, and regression tests

**Type:** Quality and safety  
**Priority:** P0  
**Estimate:** 4–7 hours  
**Story points:** 5 (runner, reports, and deterministic safety tests over 30 cases)  

## User story

As the demo owner, I want a repeatable evaluation set for retrieval, tool use, budget/constraint adherence, and uncertainty behavior so that I can demonstrate measurable quality and catch regressions.

## Scope

- Create 15–40 synthetic test requests covering answerable, tool-needed, budget-constrained, ambiguous, adversarial-document, and out-of-scope cases, with cases for every supported city and cross-city filter checks.
- Score retrieval hit@k, citation validity, tool selection/arguments, constraint adherence, abstention, latency, and model usage.
- Test Firestore vector-index readiness, city/active pre-filters, empty-result behavior, and runtime read-only access.
- Add adversarial prompt-injection content to a retrieved guide and confirm it cannot override tool permissions or user constraints.
- Separate deterministic assertions from any model-as-judge results; document evaluation limitations.

**Out of scope:** claims of production-grade accuracy, real travel advice guarantees, PII testing with actual personal data, and model training/fine-tuning.

## Acceptance criteria

- [ ] The evaluation dataset includes expected sources, expected tool use (or no tool), key constraints, and expected abstention/clarification for each case.
- [ ] Evaluation runner emits a versioned machine-readable summary and a human-readable report.
- [ ] Citation correctness and tool allowlist/argument checks are deterministic tests.
- [ ] Retrieval tests confirm Firestore returns only active chunks for the requested city, and index/permission failures fail safely.
- [ ] Budget totals and declared constraints are checked against defined tolerances/rules.
- [ ] Prompt-injection fixture cannot cause a booking, external fetch, arbitrary tool, or policy override.
- [ ] Known limitations and any failed cases are reported; no unsupported quality percentage is presented as proof of production readiness.
- [ ] A regression test runs in the local test workflow before deployment.

## Dependencies and deliverables

**Dependencies:** MVP-05, MVP-06, MVP-07.  
**Deliverables:** [synthetic evaluation fixtures](../../../data/evaluation_cases.json), test/evaluation runner, report template, and safety regression tests.

## Completion evidence

Commit the evaluation summary and list of observed failures/known limitations. Do not add real personal itinerary data to the test set.

## Completion record — ✅ Done (2026-11-06)

| Acceptance criterion | Evidence |
|---|---|
| Dataset has expected sources, tool use, constraints, abstention/clarification per case | [data/evaluation_cases.json](../../../data/evaluation_cases.json), suite v5: 30 cases, all four cities, each with `mode` and `request` |
| Runner emits a versioned machine-readable summary and a human-readable report | `make evaluate` → [MVP-08-evaluation.json](../evidence/MVP-08-evaluation.json) + [MVP-08-evaluation.md](../evidence/MVP-08-evaluation.md) |
| Citation correctness and tool allowlist/argument checks are deterministic | Checks labelled `deterministic` in the report; `tests/test_safety.py` |
| Retrieval returns only active chunks for the requested city; index/permission failures fail safely | City/active filter checks on every case (65/65); `tests/test_retrieval.py` covers error translation |
| Budget totals and declared constraints checked against rules | Total = line items (±$1), status matches total vs limit, substitutions when over, party size and limit unchanged, bounds (103/103) |
| Prompt-injection fixture can't cause a booking, external fetch, arbitrary tool, or policy override | Live: PLAN-011/PLAN-014 pass; offline: `tests/test_safety.py` (6 tests) |
| Known limitations and failed cases reported; no unsupported quality claim | Report sections *Observed failures*, *Differences*, *Limitations* |
| A regression test runs in the local workflow before deployment | `make build` runs `make test` first (103 tests) |

**Result (2026-11-06):** 29 of 30 cases pass; 332/333 deterministic and 9/9 text-heuristic checks. The one failure is a known limitation: PLAN-026, where the weather tool isn't triggered without a weather word.

**What the evaluation changed:**
- The planner now searches the traveler's own words first. It hadn't been searching notes at all, and constraints were cut when 3 interests were picked. This fixed the Napa art and SF budget retrieval misses.
- A request with no interests now gets a clarifying question with no model call.
- The booking-claim check now catches "I booked…" and "fully confirmed".

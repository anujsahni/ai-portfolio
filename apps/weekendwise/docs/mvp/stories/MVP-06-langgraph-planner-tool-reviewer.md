# MVP-06 — LangGraph itinerary planner, safe tool, and reviewer

**Type:** Agent workflow  
**Priority:** P0  
**Estimate:** 6–10 hours  
**Story points:** 8 (largest logic piece: graph, tool, reviewer, limits, and tests)  

## User story

As a traveler, I want an assistant that uses my preferences and relevant destination evidence, checks relevant conditions, and reviews its draft so that I receive a useful itinerary without unsupported certainty or unauthorized actions.

## Scope

- Build a typed LangGraph state and explicit nodes for input normalization, retrieval, planning, optional tool call, review, and response.
- Implement the deterministic `check_local_conditions(city, demo_date)` tool using a small allowlisted fixture.
- Allow one tool call and one bounded revision/review attempt per request.
- Reviewer checks citations, user constraints, simple budget totals, and simulated condition caveats.
- Return a sanitized step trace, not hidden chain-of-thought.

**Out of scope:** multiple frameworks, autonomous browsing, live weather/maps, booking/payment, account changes, arbitrary code execution, or unbounded agent delegation.

## Acceptance criteria

- [x] Graph state includes user constraints, retrieved evidence, optional tool result, draft, citations, budget summary, review result, and retry count.
- [x] An ordinary planning request can complete without tool use; a seeded rainy-day request calls the mock conditions tool once.
- [x] Tool arguments are schema-validated and restricted to seeded city/date combinations; invalid requests fail closed.
- [x] The tool only returns fixture data and performs no network, booking, payment, or mutation.
- [x] Reviewer rejects invalid citation IDs, flags unsupported details, checks budget arithmetic within documented tolerance, and requests at most one revision.
- [x] If evidence remains insufficient or conflicting, the final response asks a clarifying question or marks uncertainty rather than fabricating a definite answer.
- [x] Max model calls, tool calls, output tokens, request duration, and retries are bounded and covered by tests.
- [x] Activity trace shows user-safe summaries (e.g. “searched guides”, “checked simulated conditions”, “reviewed citations”), not private reasoning.

## Dependencies and deliverables

**Dependencies:** MVP-02 and MVP-05.  
**Deliverables:** LangGraph workflow, mock tool module, prompt/config files, response types, and workflow tests.

## Completion evidence

Run all six scripted scenarios (all four cities) and attach expected-vs-actual outputs with tool-call count and reviewer outcome.

## Completion record (2026-11-06) ✅ Done

| Acceptance criterion | Evidence |
|---|---|
| State includes constraints, evidence, tool result, draft, citations, budget, review, retry count | `PlanState` in `weekendwise/planner.py` |
| Ordinary request needs no tool; rainy-day request calls the tool once | Live: scenarios 1, 3, 5 used 0 tool calls; 2, 4, 6 called it once for Saturday 2027-05-15 |
| Tool arguments validated, allowlisted, fail closed | Wrong types, unknown city, bad date format, injection-like city → `rejected_invalid_args`; unseeded date → `rejected_unseeded_date`, plan continues with caveat |
| Tool returns fixture data only | Reads bundled `data/seed/local_conditions/*.json`; no network or writes |
| Reviewer rejects invalid citations, flags unsupported details, checks budget arithmetic, at most one revision | Deterministic `review_draft`; unsupported activities dropped before display; server recomputes totals; one revision (tests) |
| Insufficient/conflicting evidence → clarifying question or uncertainty | No evidence → `needs_clarification` with no model call; source conflict notes passed to the planner; uncertainties listed |
| Bounded model calls, tool calls, output tokens, duration, retries | 3 model calls, 1 tool call, 5 searches, 4,096 output tokens, 150 s deadline, 1 revision, 20 graph steps (unit-tested, including deadline and call cap) |
| User-safe activity trace | Trace holds only step labels, e.g. "Checked simulated local conditions" (tested) |

**Scripted scenarios (live, as `weekendwise-run`):** 6 of 6 pass. See [the report](../evidence/MVP-06-scenarios.md). Each used one Gemini call and took 13–29 s. Scenario 3 ($150 budget) is honestly flagged OVER BUDGET ($180) with substitutions and marks the live-hours request as unanswerable. Scenario 6 fits its $900 budget ($810–$870 across runs) rather than going over as originally scripted; that's reported as a difference, not a failure.

**Found and fixed during live runs:**
1. **Demo dates were mislabelled.** 16–18 May 2027 is Sun–Tue, not Fri–Sun (inherited from the mockup). All seed data, eval cases, tests, and the mockup moved to the real Fri–Sun, 14–16 May 2027 (Saturday = 15 May); Firestore resynced.
2. **Missing drink-driving guidance.** A Napa plan with wine tasting didn't say not to drink and drive. Added a planner rule, a reviewer check that forces a revision, and a server-side caveat whenever alcohol appears.
3. Scenario 3's budget lowered from $300 to $150 so the over-budget path is exercised live.

**Known behaviour:** estimates lean to the low end of guide price ranges; totals vary between runs; the revision path is proven by tests, since live first drafts have all passed review.

Code: `weekendwise/planner.py`, `weekendwise/review.py`, `weekendwise/tools.py`, `scripts/run_scenarios.py` (`make scenarios`), `tests/test_planner.py` (26 tests; 72 total), [guide 05](../guides/05-planner.md). `langgraph==1.2.20` pinned.

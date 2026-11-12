# CL-17 — Story charts and the "without vs with the stack" view

**Phase:** 4 · Experience  
**Type:** UI and storytelling  
**Priority:** P0 (the payoff the audience remembers)  
**Estimate:** 4–5 hours  
**Story points:** 5  
**Target day:** Wed 11 Nov

## User story

As a presenter, I want one page that shows the same agent with and without the Fivetran and dbt stack, and charts that tell the story in each act, so that the difference is obvious in seconds and I don't have to explain it from tables.

## Scope

- A **"Without vs with the stack"** page in the story, after Act 5:
  - Two columns, same model and same question: **Without** (agent → raw tables) and **With** (Fivetran → dbt → semantic layer and MCP → agent), each with headline stat tiles: golden-set score, headline accounts right, wrong accounts named, freshness checked, definitions cited.
  - A **headline-accounts chart**: every account either agent flagged, with its true 90-day on-time rate, the 85% threshold, and whether each agent got it right, wrongly flagged it or missed it.
  - A **per-question result strip**: six golden questions, right or wrong, for both agents.
  - A **"what each layer fixes"** table: trap → what goes wrong without the stack → which layer fixes it → the result with it.
- Charts in the acts: the on-time trend that sets the stakes (home), what the naive agent claimed against the truth (Act 1), source freshness against the 24-hour window (Act 2), and the governed at-risk accounts against the threshold (Act 4).
- The answer shown as bullets rather than a paragraph (Acts 1 and 4).
- Every chart has a table view and labels, so color is never the only signal.

**Out of scope:** new agent runs; changes to the agents or their prompts.

## Acceptance criteria

- [x] The comparison page reads correctly from the recordings and the hidden truth, with no live call.
- [x] Every number on the page matches the scorer (`contextloop.eval.score`) and the marts.
- [x] Each chart has a title that states its point, a legend or direct labels, and a table view.
- [x] The pages render in replay mode with no errors.

## Dependencies and deliverables

**Dependencies:** CL-11, CL-12.  
**Deliverables:** `contextloop/ui/pages/compare.py`, `contextloop/ui/charts.py`, chart additions to home and Acts 1, 2 and 4, tests.

## Completion evidence

Screenshots of the comparison page and the act charts.

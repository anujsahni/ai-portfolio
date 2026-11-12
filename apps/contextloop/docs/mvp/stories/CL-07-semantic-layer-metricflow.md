# CL-07 — Semantic layer with MetricFlow

**Phase:** 2 · Transform and Trust  
**Type:** Semantic layer  
**Priority:** P0  
**Estimate:** 3–5 hours  
**Story points:** 3 (semantic models over existing marts; risk is MetricFlow on DuckDB in the image)  
**Target day:** Thu 12 Nov

## User story

As a business leader at Northstar, I want each important number defined once, with a name and a description, so that any person or agent asking for "on-time delivery rate" gets the same answer by the same rule.

## Scope

- Semantic models in the dbt project over `fct_delivery`, `fct_revenue`, `fct_ticket`, `fct_renewal` and `dim_account`, with entities, dimensions (including `account__tier`, `account__region`, time grains) and measures.
- **Metrics** with descriptions written for a business reader:
  - `on_time_delivery_rate` (ratio: on-time deliveries / all non-cancelled deliveries)
  - `late_deliveries` (count)
  - `net_revenue` (sum, USD)
  - `open_shipping_tickets` (count, open and shipping-related)
  - `renewals_due_120d` (count)
  - `account_risk_flag` (derived; follows the CL-01 definition of at risk)
- A saved query for the headline question: strategic accounts, last 90 days, with the risk flag and its drivers.
- `mf validate-configs` in `make build`, and `mf query` callable from the image.
- Fallback if MetricFlow can't run on DuckDB in the image (time-boxed to 1 hour): keep the same metric YAML and compile metrics in a small Python module from the semantic manifest, and record the decision.

**Out of scope:** the hosted dbt Semantic Layer APIs (named in the talk track as the production path).

## Acceptance criteria

- [ ] `mf validate-configs` passes inside the image.
- [ ] Every metric returns the hidden-truth value for at least two test cases (overall and by account).
- [ ] The saved query returns exactly the at-risk account list from the hidden truth.
- [ ] Each metric has a description of one to three sentences that a non-technical reader understands; a test fails if one is missing.
- [ ] Querying `on_time_delivery_rate` by `account__tier` uses the tier at the time of each delivery, not today's tier (T5 test).

## Dependencies and deliverables

**Dependencies:** CL-06.  
**Deliverables:** semantic model and metric YAML in `dbt/contextloop/models/semantic/`, saved query, tests.

## Completion evidence

`mf validate-configs` output and the saved query result next to the hidden truth.

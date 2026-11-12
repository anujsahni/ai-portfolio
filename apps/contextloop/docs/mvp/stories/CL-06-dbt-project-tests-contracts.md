# CL-06 — dbt project: models, tests, contracts and lineage

**Phase:** 2 · Transform and Trust  
**Type:** Transformation  
**Priority:** P0  
**Estimate:** 8–12 hours  
**Story points:** 8 (four sources, every trap handled, contracts and tests, the core of the trust story)  
**Target day:** Thu 12 Nov

## User story

As a data engineer at Northstar, I want one tested and documented model of accounts, deliveries and revenue, so that people and agents get the same right answer, and a broken assumption fails a test instead of producing a wrong number.

## Scope

- `dbt/contextloop/` dbt project using `dbt-duckdb`, run by the `build` job.
- **Sources** for `sap_s4`, `carrier_pg`, `salesforce`, `zendesk` and `fivetran_log`, with **source freshness** thresholds (warn after 1 day, error after 2) so that T6 shows up in dbt too.
- **Staging** (one model per source table): plain English column names (`VBAK.VDATU` → `requested_delivery_date`), types cast, and deleted rows filtered out (T1).
- **Intermediate:** currency conversion to USD with `TCURR` (T3); delivery to shipment matching for actual delivery time (T2); account identity resolution from the SAP customer number (T4); account tier as of a date from history mode (T5).
- **Marts:** `dim_account` (conformed, one row per real customer), `fct_delivery` (one row per non-cancelled delivery with promised date, actual delivery time and an on-time flag), `fct_revenue` (billing net of credit memos, USD), `fct_ticket` (with a `is_shipping_related` flag from tags and subject), `fct_renewal` (open renewals and close dates).
- **Tests:** `unique` and `not_null` on keys; `relationships` between facts and `dim_account`; `accepted_values` on tier and status; custom tests for "no deleted rows in staging", "one active tier row per account" and "all amounts in USD".
- **Model contracts** (`contract: enforced: true`) on every mart, with column types.
- **Docs:** a description for every mart and column, and exposures for the agent and the activation sync, so lineage shows who uses each model.
- **Break-it scene for the app:** a `make break TRAP=T1` target that disables the deleted-row filter, so `dbt build` fails a named test live; `make build` restores it.

**Out of scope:** incremental models (the data is small); snapshots (history mode already provides history).

## Acceptance criteria

- [ ] `make build` runs `dbt build` with every model and test passing.
- [ ] Mart values match the hidden truth from CL-03 exactly: the on-time rate per account, net revenue by region and quarter, and the at-risk list built in SQL.
- [ ] Each trap T1–T5 is handled in a named model, and at least one test fails if that handling is removed (checked for T1 and T4 with `make break`).
- [ ] Source freshness reports Zendesk as an error when the T6 flag is on.
- [ ] Every mart has an enforced contract; changing a column type in a model makes the build fail.
- [ ] `dbt docs generate` produces a manifest and catalog with lineage from all four sources to every mart; the app (CL-12) can read them.

## Dependencies and deliverables

**Dependencies:** CL-04, CL-05.  
**Deliverables:** `dbt/contextloop/`, the `build` job, `make break`, `docs/mvp/evidence/CL-06-dbt-build.md`.

## Completion evidence

`dbt build` summary, the truth comparison, and the output of `make break TRAP=T1`.

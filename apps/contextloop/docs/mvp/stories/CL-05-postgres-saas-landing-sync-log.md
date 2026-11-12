# CL-05 — Postgres connector, SaaS landing and sync log

**Phase:** 1 · Move  
**Type:** Connector and data  
**Priority:** P0  
**Estimate:** 3–5 hours  
**Story points:** 3 (a second connector reusing CL-04's patterns, plus the shared sync log)  
**Target day:** Thu 12 Nov

## User story

As a sales engineering specialist, I want every source to land in the same Fivetran layout and every sync to be recorded, so that the audience sees one consistent raw layer and the agent can later check how fresh each source is.

## Scope

- `connectors/carrier_pg/connector.py`: a second Connector SDK connector reading the **Postgres container** incrementally (cursor on `updated_at`), landing `shipment` and `shipment_event` in a `carrier_pg` schema. This shows a database source next to the ERP one.
- **SaaS landing** (`contextloop/landing/`): writes the synthetic Salesforce and Zendesk data into `salesforce` and `zendesk` schemas using the same table and column layout the Fivetran connectors produce, including `_fivetran_synced` and `_fivetran_deleted`.
- **History mode** on `salesforce.account`: one row per version with `_fivetran_start`, `_fivetran_end` and `_fivetran_active`, so the mid-quarter tier change (trap T5) is visible.
- **Sync log** (`fivetran_log` schema, modelled on the shape of Fivetran's platform connector): one row per sync per connector with start, end, status, rows changed per table, and an estimate of **monthly active rows (MAR)** counted as distinct primary keys changed in the month.
- **Freshness scenario:** when the T6 scenario flag is on, the Zendesk landing's last successful sync is held two days behind.
- Labelled clearly in the app and code: the Salesforce and Zendesk landings are simulated, the SAP and Postgres connectors are real Connector SDK code.

**Out of scope:** real Salesforce or Zendesk APIs; Fivetran's exact MAR billing rules (the estimate is labelled as an estimate).

## Acceptance criteria

- [ ] `make sync` lands all four sources into DuckDB in separate schemas, each with Fivetran system columns.
- [ ] An update to a row in Postgres followed by `make sync` lands only that change, with a new `_fivetran_synced`.
- [ ] `salesforce.account` has history rows for the three accounts promoted mid-quarter, with correct start and end times and exactly one active row per account.
- [ ] `fivetran_log` has one row per connector per sync with correct row counts, and a MAR estimate per connector per month.
- [ ] With the T6 flag on, the freshness query shows Zendesk two days behind; with it off, every source is current.

## Dependencies and deliverables

**Dependencies:** CL-03, CL-04 (sync record format).  
**Deliverables:** `connectors/carrier_pg/`, `contextloop/landing/`, the `fivetran_log` schema, tests.

## Completion evidence

A table of schemas and row counts after `make sync`, a sample of the history rows, and the sync log for two runs.

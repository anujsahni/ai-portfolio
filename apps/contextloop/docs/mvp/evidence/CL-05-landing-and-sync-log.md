# CL-05 completion record: Postgres connector, SaaS landing and sync log

**Date:** 11 Nov 2026 · **Result:** all acceptance criteria met.

## Schemas after `make sync`

| Schema | Tables | Rows | How it lands |
|---|---|---|---|
| `sap_s4` | 8 | 105,957 | Connector SDK (real), CL-04 |
| `carrier_pg` | 2 | 53,571 | Connector SDK (real), reading the Postgres container incrementally on `updated_at` |
| `salesforce` | 3 | 541 | Simulated landing in Fivetran's layout, with history mode on `account` |
| `zendesk` | 3 | 6,119 | Simulated landing in Fivetran's layout |
| `fivetran_log` | 3 | 414 | Sync log, connections, MAR estimate |

Every table carries `_fivetran_synced` and `_fivetran_deleted` (tested).

## Incremental Postgres change

After `UPDATE tracking.shipment … SET updated_at = now()` on one row, the next sync reports
`carrier_pg shipment +0 ~1 -0` and `shipment_event +0 ~0 -0`; only that row gets a new `_fivetran_synced` (also covered by
`tests/test_sync.py::test_postgres_change_lands_only_that_row`).

## History mode sample (`salesforce.account`)

```
│ Quenmere Paper Mills GmbH   │ Strategic │ 2022-02-19 │ 2026-09-22 │ false │   (demoted)
│ Quenmere Paper Mills GmbH   │ Standard  │ 2026-09-22 │ 9999-12-31 │ true  │
│ Vornwick Utilities Inc      │ Standard  │ 2023-01-25 │ 2026-09-22 │ false │   (promoted)
│ Vornwick Utilities Inc      │ Strategic │ 2026-09-22 │ 9999-12-31 │ true  │
```
All four tier changes (three promotions, one demotion) have two versions with the correct start and end; every account has
exactly one active row (tested).

## Sync log for two runs

```
│ zendesk       │ SUCCESSFUL │ 2026-11-09 16:13:32 │   6119 │    0 │    0 │   ← last successful Zendesk sync, two days old (T6)
│ sap_s4        │ SUCCESSFUL │ 2026-11-11 16:13:28 │ 105806 │ 8786 │ 2402 │
│ carrier_pg    │ SUCCESSFUL │ 2026-11-11 16:13:32 │  53571 │    0 │    0 │
│ salesforce    │ SUCCESSFUL │ 2026-11-11 16:13:32 │    541 │    0 │    0 │
│ zendesk       │ FAILURE    │ 2026-11-11 16:13:32 │      0 │    0 │    0 │   "Zendesk API rate limit exceeded (simulated scenario T6)"
│ sap_s4        │ SUCCESSFUL │ 2026-11-11 16:13:35 │      0 │    0 │    0 │
│ carrier_pg    │ SUCCESSFUL │ 2026-11-11 16:13:36 │      0 │    0 │    0 │
│ salesforce    │ SUCCESSFUL │ 2026-11-11 16:13:36 │      0 │    0 │    0 │
│ zendesk       │ FAILURE    │ 2026-11-11 16:13:36 │      0 │    0 │    0 │
```

## MAR estimate (`fivetran_log.incremental_mar`, labelled an estimate)

Distinct primary keys changed per table per month, from source change timestamps. October 2026: sap_s4 6,217 · carrier_pg 3,147 ·
zendesk 223 · salesforce 10.

## Freshness scenario

With `CONTEXTLOOP_T6_STALE_ZENDESK=1` (default), Zendesk's last success is two days old and dbt source freshness reports
`zendesk: error`; with it off, Zendesk is current (`tests/test_sync.py::test_t6_flag_holds_zendesk_two_days_behind`).
Code and app label Salesforce and Zendesk as simulated; SAP and Postgres as real Connector SDK code.

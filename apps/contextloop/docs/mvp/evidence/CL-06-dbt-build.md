# CL-06 completion record: dbt project, tests, contracts and lineage

**Date:** 11 Nov 2026 · **Result:** all acceptance criteria met.

## `make build`

```
Done. PASS=89 WARN=0 ERROR=0 SKIP=0 NO-OP=3 REUSED=0 TOTAL=92
Source freshness: behind: zendesk
Semantic layer: mf validate-configs passed
Iceberg: published 6 marts to northstar.marts (one new snapshot each)
Build finished in 13s
```

Project: 16 staging views (one per source table, plain-English names, deleted rows filtered), 5 intermediate views, 6 marts
(`dim_account`, `fct_delivery`, `fct_revenue`, `fct_ticket`, `fct_renewal`, `account_risk`), each with an **enforced contract**,
a description on every column, and exposures for the governed agent and the activation sync.

## Each trap handled in a named model

| Trap | Model | Guarding test |
|---|---|---|
| T1 deleted rows | every `stg_sap__*` model | `no_deleted_rows` (generic) |
| T2 wrong date | `int_delivery_actuals`, `int_deliveries_enriched` | truth comparison of on-time rates |
| T3 currency | `int_exchange_rates_monthly`, `fct_revenue` | `assert_all_revenue_converted_to_usd`, `accepted_values` on reporting currency |
| T4 duplicate account | `int_account_identity` | `assert_every_ticket_has_a_customer` |
| T5 tier history | `int_account_tier_history`, `fct_delivery.tier_at_delivery` | `assert_one_active_tier_row_per_account`, `assert_tier_history_has_no_overlaps` |
| T6 stale data | source freshness (warn 1 day, error 2 days) | `zendesk: error` when the flag is on |

## Truth comparison (`tests/test_dbt.py`)

- `account_risk.is_at_risk` gives exactly the 9 accounts of the hidden truth, with the same rate, deliveries, tickets, renewal
  date and next step for each.
- On-time rate matches the truth for every one of the 120 customers.
- Net revenue matches for every region and quarter (to the cent; both round each document half away from zero).
- G2 (86.1%), G3 ($5,789,489), G4 (25) and G6 (28) computed from the marts equal the golden answers.

## Break-it scene

`make break TRAP=T1`:
```
Done. PASS=74 WARN=0 ERROR=4 SKIP=14 NO-OP=0 REUSED=0 TOTAL=92
Failing tests with T1 broken: no_deleted_rows_stg_sap__deliveries__fivetran_deleted, no_deleted_rows_stg_sap__delivery_items__fivetran_deleted,
  no_deleted_rows_stg_sap__sales_order_items__fivetran_deleted, no_deleted_rows_stg_sap__sales_orders__fivetran_deleted
```
`make break TRAP=T4`:
```
Done. PASS=85 WARN=0 ERROR=1 SKIP=4 NO-OP=2 REUSED=0 TOTAL=92
Failing tests with T4 broken: assert_every_ticket_has_a_customer
```
The next `make build` restored everything (PASS=89, ERROR=0).

## Contracts and lineage

`tests/test_dbt.py::test_contract_rejects_a_changed_column_type` changes `account_risk.deliveries_90d` from integer to varchar
in a copy of the project; the build fails on the contract. `dbt docs generate` writes `manifest.json` and `catalog.json` to the
warehouse volume; the lineage from `account_risk` reaches all four sources (tested).

# CL-04 completion record: SAP-shaped Connector SDK connector

**Date:** 11 Nov 2026 · **Result:** all acceptance criteria met.

`connectors/sap_s4/connector.py` is real Fivetran Connector SDK code (`schema()`, `update()`, `op.upsert`, `op.delete`,
`op.checkpoint`), run by `fivetran debug` from Connector SDK 3.1.0 inside the image. It reads an ODP-style change feed (one CSV
per SAP table per extraction batch, with `ODQ_CHANGEMODE` C/U/D and the change date and time `AEDAT`/`AEZET`).

## First sync (`make sync`)

```
  sap_s4      kna1            +120     ~0       -0
  sap_s4      likp            +9121    ~8786    -310
  sap_s4      lips            +26161   ~0       -897
  sap_s4      tcurr           +19      ~0       -0
  sap_s4      vbak            +8970    ~0       -298
  sap_s4      vbap            +26919   ~0       -897
  sap_s4      vbrk            +9044    ~0       -0
  sap_s4      vbrp            +25452   ~0       -0
```
Every table landed with the expected rows plus `_fivetran_synced` and `_fivetran_deleted`. The 8,786 LIKP updates are goods
issues posted after a delivery was created. About 117,000 changes sync in about 8 s, with a checkpoint every 5,000 rows and
after each table.

## Second sync, no new data

Every table `+0 ~0 -0`; the SDK reports `Upserts | 0`.

## Schema-change sync (`make data BATCH=2`, then `make sync`)

```
  sap_s4      likp            +40      ~25      -0
  sap_s4      lips            +111     ~0       -0
  (all other tables +0 ~0 -0)
```
The counts match the batch (40 new deliveries, 25 updates, 111 new items). `likp.zz_carrier_id` appeared with **no connector
code change** (the column is not declared in `schema()`; the SDK widened the table). 65 rows have a carrier ID; every earlier
row is null.

## Deletes

Cancelled documents arrive as `D` rows and are sent with `op.delete`: 310 deliveries, 298 orders and their items land with
`_fivetran_deleted = TRUE` and are not removed. `tests/test_sync.py` checks the deleted set equals trap T1's list exactly.

## Interrupted sync

`tests/test_sync.py::test_sap_interrupted_sync_resumes_to_the_same_state` fails a sync on purpose after 6 checkpoints
(`simulate_failure_after_checkpoints`), re-runs it from the saved `state.json`, and compares every table (all columns but
`_fivetran_synced`) with an uninterrupted run: identical.

## Code quality

`ruff check connectors contextloop tests` (rules E, F, W, B; `ruff.toml`): all checks passed. Every public function has a
docstring (tested). `configuration.json` holds no secrets (the Postgres password for CL-05 is supplied at run time).

## Notes

- Fivetran naming separates letters from digits, so `KNA1` lands as `sap_s4.kna_1` and `NAME1` as `name_1`. The dbt sources
  use those names, as they would against a real Fivetran destination.
- Talk track: at a customer this is Fivetran's native SAP connectors or a hybrid deployment agent; the SDK is shown because it
  makes the mechanics visible.

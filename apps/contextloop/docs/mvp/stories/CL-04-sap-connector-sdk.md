# CL-04 — SAP-shaped Fivetran Connector SDK connector

**Phase:** 1 · Move  
**Type:** Connector  
**Priority:** P0  
**Estimate:** 5–8 hours  
**Story points:** 5 (incremental state, deletes, schema change and the in-container tester)  
**Target day:** Wed–Thu

## User story

As a sales engineering specialist, I want to show a real Fivetran connector syncing ERP data incrementally, with deletes and a schema change handled automatically, so that the audience sees how Fivetran makes replication reliable rather than hearing it described.

## Scope

- `connectors/sap_s4/connector.py` using the **Fivetran Connector SDK**: a `schema()` function declaring the SAP tables and primary keys, and an `update()` function that reads changes since the saved cursor and calls `upsert`, `delete` and `checkpoint`.
- `connectors/sap_s4/configuration.json` (no secrets) and a short README in the folder that explains each part for a reader new to the SDK.
- **Incremental sync:** the cursor is the latest `AEDAT`/`ERDAT` change timestamp per table. A second run after new data arrives syncs only the changed rows; state is checkpointed after each table, so an interrupted sync resumes.
- **Deletes:** cancelled orders and deliveries are emitted as deletes, so they land with `_fivetran_deleted = true` (trap T1).
- **Schema change:** after the second batch from CL-03 arrives, `LIKP.ZZ_CARRIER_ID` appears in the destination with no change to the connector code.
- The `sync` job runs `fivetran debug` (or the CL-02 fallback harness) in the container and writes to `/warehouse/warehouse.db` in a `sap_s4` schema.
- A **sync record** for each run (start, end, rows inserted, updated and deleted per table) is written for the sync log in CL-05.
- Talk-track notes: in production a customer would use Fivetran's native SAP connectors or hybrid deployment; the SDK is shown here because it makes the mechanics visible.

**Out of scope:** real SAP protocols (RFC, ODP, HANA log reading), authentication, deployment to a Fivetran account.

## Acceptance criteria

- [ ] `make sync` (first run) lands every SAP table with the expected row counts and Fivetran system columns.
- [ ] A second `make sync` with no new data changes nothing; after `make data BATCH=2`, it syncs only the changed rows (counts in the sync record match the batch).
- [ ] Deleted rows land with `_fivetran_deleted = true` and are not removed.
- [ ] `ZZ_CARRIER_ID` appears after batch 2 with no connector code change; earlier rows have nulls.
- [ ] Killing a sync midway and re-running it ends with the same final state as an uninterrupted run (test).
- [ ] The connector code passes a linter and has docstrings; no secrets in the configuration.

## Dependencies and deliverables

**Dependencies:** CL-03.  
**Deliverables:** `connectors/sap_s4/`, the `sync` job, tests, `docs/mvp/evidence/CL-04-sync-runs.md`.

## Completion evidence

Output of the first sync, the incremental sync and the schema-change sync, with row counts.

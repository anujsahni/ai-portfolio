# CL-08 — Iceberg lakehouse: publish marts, read from two engines

**Phase:** 2 · Transform and Trust  
**Type:** Lakehouse  
**Priority:** P1 (the Trino part is first on the cut line)  
**Estimate:** 4–6 hours  
**Story points:** 5 (three extra containers and two engines must agree)  
**Target day:** Thu–Fri

## User story

As a data platform owner, I want the trusted tables stored once in an open format that any engine can read, so that I am not locked into one warehouse and every team or tool queries the same data.

## Scope

- A **publish step** in the `build` job writes each mart from DuckDB to an **Apache Iceberg** table in the `iceberg-rest` catalog, with data files in the MinIO bucket `lakehouse`. Default approach is PyIceberg; DuckDB's Iceberg extension is the alternative. Time-box choosing between them to 1 hour and record why.
- Namespaces: `northstar.marts.*`. Each publish creates a new table snapshot, so the app can show the snapshot history.
- **Trino** (`lakehouse` profile) configured with an Iceberg catalog pointing at the same REST catalog and MinIO.
- `make lakehouse` runs the same query (the at-risk account list) through **DuckDB reading Iceberg** and through **Trino**, and compares the results.
- The app (CL-12, Act 3) shows the two results side by side with the engine name, the table's snapshot ID and its storage path.
- Talk track: in production this is Fivetran Managed Data Lake Service writing Iceberg to S3, ADLS or GCS, read by Snowflake, Databricks, BigQuery or Trino.
- Stretch only: register the tables in Snowflake (needs cloud storage); not part of MVP done.

**Out of scope:** partition tuning, compaction, table maintenance.

## Acceptance criteria

- [ ] After `make build`, every mart exists as an Iceberg table in the catalog, with data files in MinIO (visible in the MinIO console).
- [ ] `make lakehouse` returns identical results from DuckDB and Trino (row-by-row comparison in a test).
- [ ] A second `make build` adds a new snapshot; the snapshot history lists both.
- [ ] Credentials for MinIO are only in `.env` or Compose environment, never in code or images.
- [ ] If the cut line is used, DuckDB alone reads the Iceberg tables and the story records that Trino was cut.

## Dependencies and deliverables

**Dependencies:** CL-06 (marts), CL-02 (containers).  
**Deliverables:** publish module, `docker/trino/` catalog config, `make lakehouse`, tests.

## Completion evidence

Output of `make lakehouse` showing both engines' results and the snapshot history.

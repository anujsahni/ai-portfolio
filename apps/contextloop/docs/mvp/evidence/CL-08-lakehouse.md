# CL-08 completion record: Iceberg lakehouse, two engines

**Date:** 11 Nov 2026 · **Result:** all acceptance criteria met; the Trino part was **not** cut.

## Approach chosen

**PyIceberg** writes; **DuckDB's iceberg extension** and **Trino** read. PyIceberg writes Arrow tables through the REST catalog
with no JVM and exposes the snapshot history to the app. The DuckDB extensions are installed at image build, so reading works
offline. Trino reads nested namespaces with `iceberg.rest-catalog.nested-namespace-enabled=true`.

## Publish

Every `make build` writes the six marts to `northstar.marts.*` in the `iceberg-rest` catalog, with Parquet data files in the
`lakehouse` bucket (visible in the RustFS console at http://127.0.0.1:9001). Tested: every mart has a current snapshot and
`.parquet` files under `lakehouse/northstar/marts/<mart>/data`.

## `make lakehouse`

```
Iceberg table northstar.marts.account_risk · snapshot 1607623456127918599
  s3://lakehouse/northstar/marts/account_risk
DuckDB: 9 at-risk accounts · Trino: 9 at-risk accounts
   Halbrook Fluid Systems 76.0%
   Tamwick Mining Inc 61.5%
   …
✓ Both engines return identical results
```
Row-by-row comparison in `tests/test_lakehouse.py`.

## Snapshot history

Each publish adds one entry to the table's snapshot log (an overwrite commits a delete and an append together; the log records
the one that became current):
```
{'snapshot_id': 2050166625277876399, 'operation': 'append', 'total_records': '120'}
{'snapshot_id': 1607623456127918599, 'operation': 'append', 'total_records': '120'}
{'snapshot_id': 1114331353957329384, 'operation': 'append', 'total_records': '120'}
```

## Credentials

Object-store credentials come only from `.env` / Compose environment; a test greps the repository and finds the demo secret
only in `docker-compose.yml` (default value) and `.env.example`.

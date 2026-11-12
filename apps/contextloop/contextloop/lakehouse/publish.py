"""Publishes every dbt mart from DuckDB to an Apache Iceberg table (namespace northstar.marts) in the REST catalog, with the data
files in the S3-compatible object store. Each publish is a new table snapshot, so the snapshot history shows every build.

Chosen approach: PyIceberg. It writes through the catalog's REST API with plain Arrow tables, needs no JVM, and keeps the
snapshot history readable from Python for the app. (DuckDB's Iceberg extension is used to *read* the tables; see compare.py.)
"""
from __future__ import annotations

import duckdb
from pyiceberg.catalog import load_catalog
from pyiceberg.exceptions import NoSuchTableError

from contextloop.config import ICEBERG_CATALOG_URI, LAKE_BUCKET, WAREHOUSE_PATH, s3_settings

NAMESPACE = ("northstar", "marts")
MARTS = ["dim_account", "fct_delivery", "fct_revenue", "fct_ticket", "fct_renewal", "account_risk"]


def catalog():
    s = s3_settings()
    return load_catalog("lakehouse", **{
        "type": "rest", "uri": ICEBERG_CATALOG_URI, "warehouse": f"s3://{LAKE_BUCKET}/",
        "s3.endpoint": s["endpoint"], "s3.access-key-id": s["access_key"], "s3.secret-access-key": s["secret_key"],
        "s3.region": s["region"], "s3.path-style-access": "true",
        "py-io-impl": "pyiceberg.io.pyarrow.PyArrowFileIO",
    })


def publish(warehouse=WAREHOUSE_PATH) -> dict[str, int]:
    from contextloop.lakehouse.bucket import ensure_bucket

    ensure_bucket(retries=5)
    cat = catalog()
    for depth in range(1, len(NAMESPACE) + 1):
        cat.create_namespace_if_not_exists(NAMESPACE[:depth])
    con = duckdb.connect(str(warehouse), read_only=True)
    snapshots = {}
    try:
        for mart in MARTS:
            data = con.sql(f"SELECT * FROM marts.{mart}").to_arrow_table()
            ident = (*NAMESPACE, mart)
            try:
                table = cat.load_table(ident)
                if [f.name for f in table.schema().fields] != data.schema.names:
                    raise ValueError("columns changed")
                table.overwrite(data)  # a new snapshot; Iceberg rejects it if a column type changed
            except NoSuchTableError:
                table = cat.create_table(ident, schema=data.schema)
                table.overwrite(data)
            except ValueError:
                cat.drop_table(ident)  # the mart's contract changed: start a new table
                table = cat.create_table(ident, schema=data.schema)
                table.overwrite(data)
            snapshots[mart] = table.current_snapshot().snapshot_id
    finally:
        con.close()
    print(f"Iceberg: published {len(snapshots)} marts to {'.'.join(NAMESPACE)} (one new snapshot each)")
    return snapshots


def history(mart: str = "account_risk") -> list[dict]:
    """Snapshot history of one Iceberg mart, newest last (shown in the app's Act 3): one entry per publish.

    An overwrite commits a delete snapshot and an append snapshot together; the table's snapshot log records only the
    snapshot that became current, so it has exactly one entry per publish."""
    table = catalog().load_table((*NAMESPACE, mart))
    by_id = {s.snapshot_id: s for s in table.metadata.snapshots}
    out = []
    for entry in table.metadata.snapshot_log:
        s = by_id[entry.snapshot_id]
        summary = s.summary.additional_properties if s.summary else {}
        out.append({"snapshot_id": s.snapshot_id, "timestamp_ms": entry.timestamp_ms,
                    "operation": s.summary.operation.value if s.summary else "",
                    "added_records": summary.get("added-records"), "total_records": summary.get("total-records")})
    return out


def location(mart: str = "account_risk") -> dict[str, str]:
    table = catalog().load_table((*NAMESPACE, mart))
    return {"location": table.location(), "metadata_location": table.metadata_location,
            "snapshot_id": str(table.current_snapshot().snapshot_id)}

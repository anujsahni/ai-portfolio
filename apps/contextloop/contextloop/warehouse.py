"""Warehouse access. DuckDB allows one writer at a time, so jobs write `warehouse.db` and then publish a read-only copy,
`serving.db`, which the long-running services open read-only. The copy is swapped in atomically."""
from __future__ import annotations

import os
import shutil
from contextlib import contextmanager

import duckdb

from contextloop.config import SERVING_PATH, WAREHOUSE_PATH


def publish_serving() -> None:
    wal = WAREHOUSE_PATH.with_name(WAREHOUSE_PATH.name + ".wal")
    if wal.exists() and wal.stat().st_size:
        raise RuntimeError("warehouse.db has an un-checkpointed WAL; close every connection before publishing")
    tmp = SERVING_PATH.with_suffix(".db.tmp")
    shutil.copyfile(WAREHOUSE_PATH, tmp)
    os.replace(tmp, SERVING_PATH)


@contextmanager
def serving():
    """A short-lived read-only connection to the serving copy."""
    con = duckdb.connect(str(SERVING_PATH), read_only=True)
    try:
        yield con
    finally:
        con.close()

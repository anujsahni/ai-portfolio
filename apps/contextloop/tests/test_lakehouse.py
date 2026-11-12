"""CL-08: every mart is an Iceberg table with files in object storage; DuckDB and Trino agree; each publish is a snapshot."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import httpx
import pytest

IN_STACK = os.environ.get("PGHOST") == "postgres"
pytestmark = pytest.mark.skipif(not IN_STACK, reason="runs inside the Compose network after `make build`")
ROOT = Path(__file__).resolve().parents[1]


def test_every_mart_is_an_iceberg_table_with_data_files():
    from contextloop.lakehouse.bucket import filesystem
    from contextloop.lakehouse.publish import MARTS, NAMESPACE, catalog

    cat, fs = catalog(), filesystem()
    for mart in MARTS:
        table = cat.load_table((*NAMESPACE, mart))
        assert table.current_snapshot() is not None, mart
        files = fs.find(f"lakehouse/northstar/marts/{mart}/data")
        assert any(f.endswith(".parquet") for f in files), mart


def test_duckdb_and_trino_return_identical_rows():
    from contextloop.lakehouse import compare

    try:
        httpx.get(f"{compare.TRINO_URL}/v1/info", timeout=3)
    except httpx.HTTPError:
        pytest.skip("Trino is not running (make lakehouse starts it)")
    duck, trino = compare._norm(compare.via_duckdb()), compare._norm(compare.via_trino())
    assert duck and duck == trino


def test_each_publish_adds_a_snapshot():
    from contextloop.lakehouse.publish import history, publish

    before = len(history())
    publish()
    after = history()
    assert len(after) == before + 1
    assert after[-1]["snapshot_id"] != after[-2]["snapshot_id"]


def test_object_store_credentials_are_not_in_code_or_images():
    secret = os.environ["S3_SECRET_KEY"]
    hits = subprocess.run(["grep", "-rIl", "--exclude-dir=.git", "--exclude-dir=data", "--exclude-dir=__pycache__", secret, "."],
                          cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert set(hits) <= {"./docker-compose.yml", "./.env.example"}, hits

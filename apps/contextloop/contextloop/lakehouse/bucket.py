"""Create the S3 bucket that holds the Iceberg data files (idempotent)."""
from __future__ import annotations

import time

import s3fs

from contextloop.config import LAKE_BUCKET, s3_settings


def filesystem() -> s3fs.S3FileSystem:
    s = s3_settings()
    return s3fs.S3FileSystem(
        key=s["access_key"],
        secret=s["secret_key"],
        client_kwargs={"endpoint_url": s["endpoint"], "region_name": s["region"]},
        config_kwargs={"s3": {"addressing_style": "path"}},
    )


def ensure_bucket(retries: int = 20) -> None:
    for attempt in range(retries):
        try:
            fs = filesystem()
            if not fs.exists(LAKE_BUCKET):
                fs.mkdir(LAKE_BUCKET)
                print(f"Created bucket s3://{LAKE_BUCKET}")
            else:
                print(f"Bucket s3://{LAKE_BUCKET} already exists")
            return
        except Exception as exc:  # noqa: BLE001 - storage may still be starting
            if attempt == retries - 1:
                raise
            print(f"Waiting for object storage ({exc.__class__.__name__})…")
            time.sleep(1.5)

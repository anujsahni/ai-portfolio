"""Shared settings for every ContextLoop job and service. Values come from the environment (docker-compose.yml)."""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The reporting date every business definition is evaluated at (docs/demo/narrative.md).
AS_OF = date(2026, 11, 6)
DEFAULT_SEED = 20261106

DATA_OUT = Path(os.environ.get("CONTEXTLOOP_DATA_OUT", ROOT / "data" / "out"))
SAP_DIR = DATA_OUT / "sap_s4"
SAAS_DIR = DATA_OUT / "saas"
CARRIER_DIR = DATA_OUT / "carrier_pg"
TRUTH_DIR = DATA_OUT / "truth"

WAREHOUSE_PATH = Path(os.environ.get("WAREHOUSE_PATH", ROOT / "data" / "out" / "warehouse.db"))
SERVING_PATH = Path(os.environ.get("SERVING_PATH", WAREHOUSE_PATH.with_name("serving.db")))

DBT_PROJECT_DIR = ROOT / "dbt" / "contextloop"

MODE = os.environ.get("CONTEXTLOOP_MODE", "replay")
# The narrated pitch video. The .mp4 is too heavy for git, so it is hosted: `make publish-pitch` uploads it to S3 behind
# CloudFront and writes the links to contextloop/ui/pitch/published.json (tracked). CONTEXTLOOP_PITCH_URL overrides the video
# link (e.g. a YouTube URL). With no link at all, the Architecture page plays a locally rendered copy if there is one.
_PUBLISHED = ROOT / "contextloop" / "ui" / "pitch" / "published.json"
PITCH_PUBLISHED = json.loads(_PUBLISHED.read_text()) if _PUBLISHED.exists() else {}
PITCH_VIDEO_URL = os.environ.get("CONTEXTLOOP_PITCH_URL") or PITCH_PUBLISHED.get("video_url", "")
PITCH_PAGE_URL = PITCH_PUBLISHED.get("page_url", "")  # the public watch page to share with customers
T6_STALE_ZENDESK = os.environ.get("CONTEXTLOOP_T6_STALE_ZENDESK", "1") == "1"


def pg_dsn() -> str:
    return (
        f"host={os.environ.get('PGHOST', 'localhost')} port={os.environ.get('PGPORT', '5432')} "
        f"dbname={os.environ.get('PGDATABASE', 'carrier')} user={os.environ.get('PGUSER', 'carrier')} "
        f"password={os.environ.get('PGPASSWORD', '')}"
    )


def s3_settings() -> dict[str, str]:
    return {
        "endpoint": os.environ.get("S3_ENDPOINT", "http://localhost:9000"),
        "access_key": os.environ.get("S3_ACCESS_KEY", ""),
        "secret_key": os.environ.get("S3_SECRET_KEY", ""),
        "region": os.environ.get("S3_REGION", "us-east-1"),
    }


ICEBERG_CATALOG_URI = os.environ.get("ICEBERG_CATALOG_URI", "http://localhost:8181")
LAKE_BUCKET = "lakehouse"

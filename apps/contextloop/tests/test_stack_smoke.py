"""CL-02: the Compose file follows the rules, and (inside the stack) every service answers."""
from __future__ import annotations

import os
import urllib.request
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
IN_STACK = os.environ.get("PGHOST") == "postgres"


def test_no_latest_or_unpinned_public_images():
    for name, svc in COMPOSE["services"].items():
        image = svc.get("image", "")
        assert image, name
        assert ":" in image and not image.endswith(":latest"), f"{name} uses an unpinned image: {image}"
    trino_base = (ROOT / "docker" / "trino" / "Dockerfile").read_text()
    assert "FROM trinodb/trino:484" in trino_base
    assert "FROM python:3.12.16-slim" in (ROOT / "Dockerfile").read_text()


def test_only_three_ports_published_on_localhost():
    published = []
    for name, svc in COMPOSE["services"].items():
        for p in svc.get("ports", []):
            assert str(p).startswith("127.0.0.1:"), f"{name} publishes {p} beyond localhost"
            published.append(int(str(p).split(":")[1]))
    assert sorted(published) == [8080, 8501, 9001]


def test_env_is_git_ignored_and_example_has_no_secrets():
    assert ".env" in (ROOT / ".gitignore").read_text().splitlines()
    assert ".env" in (ROOT / ".dockerignore").read_text().splitlines()
    example = dict(line.split("=", 1) for line in (ROOT / ".env.example").read_text().splitlines() if "=" in line and not line.startswith("#"))
    assert example["ANTHROPIC_API_KEY"].split("#")[0].strip() == ""
    assert example["SLACK_WEBHOOK_URL"].split("#")[0].strip() == ""


@pytest.mark.skipif(not IN_STACK, reason="runs inside the Compose network (make test)")
@pytest.mark.parametrize("url", [
    "http://mock-salesforce:8000/health",
    "http://mcp-metrics:8101/health",
    "http://mcp-freshness:8102/health",
    "http://dbt-mcp:8103/health",
    "http://app:8501/_stcore/health",
    "http://iceberg-rest:8181/v1/config",
    "http://rustfs:9000/health",
])
def test_http_services_answer(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        assert r.status == 200


@pytest.mark.skipif(not IN_STACK, reason="runs inside the Compose network (make test)")
def test_postgres_answers():
    import psycopg

    from contextloop.config import pg_dsn

    with psycopg.connect(pg_dsn(), connect_timeout=5) as conn:
        assert conn.execute("SELECT 1").fetchone()[0] == 1


@pytest.mark.skipif(not IN_STACK, reason="runs inside the Compose network (make test)")
def test_lakehouse_bucket_exists():
    from contextloop.lakehouse.bucket import filesystem

    assert filesystem().exists("lakehouse")

# CL-02 — Docker Compose foundation, image, Makefile and modes

**Phase:** 0 · Foundation  
**Type:** Platform  
**Priority:** P0  
**Estimate:** 3–5 hours  
**Story points:** 3 (several services and volumes, plus the risk of the Connector SDK tester inside a container)  
**Target day:** Wed 11 Nov

## User story

As the presenter, I want the whole demo to start with one command on any laptop that has Docker, so that nothing depends on local installs and the demo behaves the same every time.

## Scope

- **`Dockerfile`** for the `contextloop` application image: a pinned slim Python base, `requirements.txt` with exact versions (`fivetran-connector-sdk`, `dbt-core`, `dbt-duckdb`, `dbt-metricflow`, `duckdb`, `pyiceberg`, `mcp`, `dbt-mcp`, `anthropic`, `streamlit`, `fastapi`, `uvicorn`, `psycopg`), a non-root user, and no secrets in any layer. It must build for both `linux/arm64` (Apple silicon) and `linux/amd64`.
- **`docker-compose.yml`** with the services in the README's container table: `postgres`, `minio` (plus a one-off bucket setup), `iceberg-rest`, `trino` (profile `lakehouse`), `mock-salesforce`, `mcp-metrics`, `mcp-freshness`, `dbt-mcp`, `app`, and the one-off jobs `datagen`, `sync`, `build`, `eval`.
- Every public image pinned to an exact version tag (no `latest`). Health checks on Postgres, MinIO and the catalog; dependent services wait for them to be healthy.
- Named volumes `warehouse`, `lake` and `pgdata`. One private network. Only `app:8501`, `minio:9001` and `trino:8080` published, all on `127.0.0.1`.
- **`Makefile`** wrapping Compose: `help`, `images`, `up`, `down`, `clean`, `data`, `sync`, `build`, `lakehouse`, `eval`, `record`, `demo`, `test`, `logs`, `ps`. Stubs are fine for targets whose stories come later, as long as they print what is missing.
- **Configuration:** `.env.example` (`ANTHROPIC_API_KEY`, `SLACK_WEBHOOK_URL`, `CONTEXTLOOP_MODE=replay`); `.env` is git-ignored. `CONTEXTLOOP_MODE` is `replay` or `live`; replay is the default and needs no key.
- **Risk spike (time-boxed to 1 hour):** confirm that `fivetran debug` runs inside the image on `linux/arm64`. It downloads a local tester on first run, so bake that download into the image to keep the demo offline. If it can't run, record the fallback in this story: run the connector's `update()` through a small local harness with the same `Operations` calls.
- **Smoke test:** `make up` then `make test` runs a test that connects to each service.

**Out of scope:** cloud registries, Kubernetes, CI.

## Acceptance criteria

- [ ] `make images` builds the app image for the host architecture with no errors, and pulls all pinned images.
- [ ] `make up` brings every long-running service to healthy within 2 minutes on a warm machine; `make ps` shows them.
- [ ] `make down` stops everything; `make clean` removes the volumes; a second `make up` starts cleanly.
- [ ] No image tag is `latest`; a test parses `docker-compose.yml` and fails if one is.
- [ ] No secret is in any image layer (`docker history` and a grep of the build context are clean); `.env` is git-ignored.
- [ ] Only the three intended ports are published, and only on `127.0.0.1`.
- [ ] The `fivetran debug` spike result is recorded, with the chosen approach.
- [ ] The smoke test passes inside the container.

## Dependencies and deliverables

**Dependencies:** Docker Desktop or an equivalent runtime on the presenter's laptop.  
**Deliverables:** `Dockerfile`, `docker-compose.yml`, `docker/`, `Makefile`, `.env.example`, `requirements.txt`, `tests/test_stack_smoke.py`.

## Completion evidence

`make ps` output with every service healthy, the spike result and the smoke test output.

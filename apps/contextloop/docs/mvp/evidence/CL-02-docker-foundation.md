# CL-02 completion record: Docker Compose foundation

**Date:** 11 Nov 2026 · **Result:** all acceptance criteria met.

## What was built

- `Dockerfile`: one `contextloop` image on `python:3.12.16-slim`, non-root user `app`, no secrets. Two virtual environments:
  `/opt/venv` (dbt, MetricFlow, dbt-mcp, MCP SDK, Anthropic SDK, Streamlit, FastAPI, PyIceberg) and `/opt/fivetran`
  (Connector SDK 3.1.0). Exact versions in `requirements.txt` and `requirements-connector.txt`.
- `docker-compose.yml`: postgres, rustfs (+ one-off `lake-init`), iceberg-rest, trino (profile `lakehouse`), mock-salesforce,
  mcp-metrics, mcp-freshness, dbt-mcp, app, and the jobs datagen, sync, build, eval, test (profile `jobs`).
- `Makefile`: help, images, up, down, clean, ps, logs, data, sync, build, break, lakehouse, eval, record, demo, test, sdk-debug.
  `eval` and `record` print that they arrive with CL-11.
- `.env.example` (`CONTEXTLOOP_MODE=replay` by default; key and webhook empty), `.gitignore`, `.dockerignore`.

## Decisions recorded

| Decision | Why |
|---|---|
| **RustFS instead of MinIO** for S3-compatible storage | MinIO's images are no longer published on Docker Hub or Quay, so they cannot be pinned. RustFS (Apache-2.0) is S3-compatible and also serves a console on port 9001. README and diagrams updated. |
| **Two Python environments** in one image | `fivetran-connector-sdk` 3.1 cannot co-install with `dbt-metricflow`; `dbt-mcp` 2.10.1 needs `mcp` 1.x. Both environments pin DuckDB 1.5.6 so they share one warehouse file. |
| **No bind mounts** | Docker Desktop could not read the project under `~/Documents`; baking code into the image and keeping state in named volumes (`warehouse`, `data`, `lake`, `catalog`, `pgdata`) also means the presenter needs nothing but Docker. Trino's catalog file is baked into a derived image (`docker/trino/Dockerfile`). |
| **Serving copy of the warehouse** | DuckDB allows one writer. Jobs write `warehouse.db`, then atomically publish `serving.db`, which services open read-only. |
| **DuckDB extensions baked in** | `iceberg`, `httpfs`, `avro` are installed at image build so reading Iceberg works offline. |

## Spike: `fivetran debug` inside the image (linux/arm64)

**Result: works, no fallback needed.** Connector SDK 3.1 runs connectors in-process with a pure-Python runner and a local DuckDB
destination; nothing is downloaded at run time. The only requirement was putting `/opt/fivetran/bin` on `PATH` (the runner
calls `pipreqs`). The `sync` job therefore runs the real `fivetran debug` for both connectors.

## Evidence

`make up` from a clean state (volumes deleted): **healthy in 11.9 s**.

```
NAME                            IMAGE                                SERVICE           STATUS                    PORTS
contextloop-app-1               contextloop:dev                      app               Up 5 seconds (healthy)    127.0.0.1:8501->8501/tcp
contextloop-dbt-mcp-1           contextloop:dev                      dbt-mcp           Up 11 seconds (healthy)
contextloop-iceberg-rest-1      apache/iceberg-rest-fixture:1.10.1   iceberg-rest      Up 6 seconds (healthy)    8181/tcp
contextloop-mcp-freshness-1     contextloop:dev                      mcp-freshness     Up 11 seconds (healthy)
contextloop-mcp-metrics-1       contextloop:dev                      mcp-metrics       Up 11 seconds (healthy)
contextloop-mock-salesforce-1   contextloop:dev                      mock-salesforce   Up 11 seconds (healthy)
contextloop-postgres-1          postgres:17.11-alpine                postgres          Up 11 seconds (healthy)   5432/tcp
contextloop-rustfs-1            rustfs/rustfs:1.0.4                  rustfs            Up 11 seconds (healthy)   127.0.0.1:9001->9001/tcp
```

Trino (`make lakehouse`) adds `127.0.0.1:8080` and is healthy in about 9 s.

Tests (`tests/test_stack_smoke.py`, run by `make test` inside the stack): no `latest` or unpinned image; exactly ports 8080, 8501
and 9001 published, all on `127.0.0.1`; `.env` ignored by git and Docker; `.env.example` holds no key; every HTTP service,
Postgres and the lakehouse bucket answer. `make clean` followed by `make up` starts cleanly (shown above).

# MVP-09 — App container on ECS Fargate

**Type:** Deployment  
**Priority:** P0  
**Estimate:** 3–5 hours  
**Story points:** 3 (Dockerfile, health checks, startup warm-up and a cloud smoke test)  

## User story

As the demo owner, I want the real app running on ECS with health checks and a smoke test so that I can trust the hosted demo before showing it.

## Scope

- `Dockerfile`: slim Python base, non-root user, pinned dependencies, Streamlit on port 8501 with `--server.headless true`, no secrets baked in. `.dockerignore` excludes `.env`, data outputs, reports and tests.
- Health: a container health check on Streamlit's health endpoint; a readiness check in the app that confirms it can reach S3 (snapshot), OpenSearch, the SageMaker endpoint and Bedrock (no model call).
- **Warm-up:** on start, one small scoring call so the first user doesn't hit the SageMaker cold start.
- `scripts/smoke_cloud.py` (`make smoke-cloud`): through the tunnel, load each page, score the pipeline and request one brief; print latency and pass/fail per check.
- Configuration from environment variables set by Terraform outputs; the app fails fast with a clear message if any are missing.

**Out of scope:** the full page design (MVP-10), public access and load testing.

## Acceptance criteria

- [ ] The image runs locally (`make run-container`) and on ECS with the same configuration surface.
- [ ] The container runs as a non-root user and contains no `.env`, credentials or generated data.
- [ ] The health check passes on ECS; the readiness check reports each dependency separately.
- [ ] After a fresh deploy, the first Pipeline load is warm (under 3 seconds).
- [ ] `make smoke-cloud` passes all checks, including one live brief.
- [ ] Missing configuration stops startup with a message naming the missing setting.

## Dependencies and deliverables

**Dependencies:** MVP-08, IAC-06.  
**Deliverables:** `Dockerfile`, `.dockerignore`, health and readiness code, `scripts/smoke_cloud.py`, `docs/mvp/evidence/MVP-09-ecs-smoke.md`.

## Completion evidence

`make smoke-cloud` output on ECS with latencies.

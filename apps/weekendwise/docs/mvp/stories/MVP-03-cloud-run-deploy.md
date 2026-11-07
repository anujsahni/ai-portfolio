# MVP-03 — Build and deploy the app to Cloud Run

**Type:** Platform setup + deployment  
**Priority:** P0  
**Estimate:** 4–7 hours after a runnable app shell exists  
**Story points:** 3 (Dockerfile, build config, health check, and smoke test; infrastructure is in IAC-05)  

## User story

As the demo owner, I want a repeatable path to build a container and deploy WeekendWise to Cloud Run so that an interviewer can try the prototype through HTTPS.

## Scope

> Infrastructure (Artifact Registry, runtime identity, Cloud Run service settings, rollback) is provisioned by [IAC-03](IAC-03-service-identities-iam.md) and [IAC-05](IAC-05-artifact-registry-cloud-run.md) with `make build` / `make deploy`. This story delivers the app container and proves it runs there.


- Build a Python/Streamlit container.
- Use Cloud Build to create the image and Artifact Registry to store it.
- Deploy the image to Cloud Run with a dedicated runtime identity, scale-to-zero, conservative maximum instances, and safe configuration. The runtime identity has Vertex AI invocation and Firestore read access only.
- Document the steps to create the repository, build, deploy, verify, roll back, and clean up.

**Out of scope:** Kubernetes/GKE, multi-region HA, public user account system, production SLA, deployment from an unreviewed branch, or embedding credentials in image/source.

## Acceptance criteria

- [x] `docs/mvp/guides/03-cloud-run-deployment.md` gives prerequisites and console-oriented steps for Artifact Registry, Cloud Build, runtime identity, Cloud Run deploy, verification, rollback, and cleanup.
- [x] A successful Cloud Build creates a versioned image in a private Artifact Registry repository.
- [x] Cloud Run serves the app over HTTPS and starts with minimum instances set to zero; maximum instances are explicitly bounded.
- [x] The service uses its dedicated runtime identity; no service-account key is copied into the container or repository.
- [x] A health/readiness check succeeds and the application can reach Vertex AI and read the seeded Firestore corpus using the attached identity.
- [x] The Cloud Run runtime identity cannot ingest, update, or delete corpus documents; corpus writes use the separate ingestion/developer identity documented in MVP-04.
- [x] Public invocation, if enabled, is an explicit choice documented with abuse/cost controls and synthetic-data-only warning.
- [ ] A previous known-good revision can be restored using Cloud Run traffic/revision controls. *(Documented; not yet rehearsed.)*

## Dependencies and deliverables

**Dependencies:** MVP-02, MVP-04, and IAC-05. A minimal runnable app shell is required before deployment.  
**Deliverables:** Dockerfile/build configuration, Cloud Run deployment settings, and setup guide 03.

## Completion evidence

Provide the HTTPS demo URL in a private/release note, successful health and smoke-test results, image tag, and documented rollback revision. Do not put project secrets in the public README.

## Progress record — 🟡 Deployed and smoke-tested, waiting for a rollback rehearsal (updated 2026-11-06)

Done:
- `Dockerfile` (python 3.14-slim, non-root, no credentials, `data/seed` bundled), `.dockerignore`, `cloudbuild.yaml`, `.gcloudignore` (uploads only the app; checked with `gcloud meta list-files-for-upload`).
- `/health` and `/healthz` (process is up) and `/readyz` (Firestore read as the runtime identity). Cloud Run's front end reserves `/healthz` and answers 404 from outside, so external checks use `/health`; the startup probe uses `/healthz` inside the container.
- `make smoke-cloud` → [evidence/MVP-03-cloud-run-smoke.md](../evidence/MVP-03-cloud-run-smoke.md).
- [Guide 03](../guides/03-cloud-run-deployment.md) rewritten for the automated path: build, deploy, verify, roll back, public access warning, cleanup.
- Verified locally: the image builds (399 MB). Run with your sign-in mounted read-only, impersonating `weekendwise-run`, it reported `/readyz` ready and produced a complete Santa Cruz plan in 16 s.

Live run (2026-11-06): `make release` deployed image `20261106-224657`, and `make smoke-cloud` passed **9 of 9** at 22:57 UTC: min 0 / max 2, runs as `weekendwise-run`, HTTP 403 without a token, `/health` and `/readyz` OK, and one live Portland plan through Cloud Run in 18.5 s with 7 citations ([evidence](../evidence/MVP-03-cloud-run-smoke.md)). `make verify` confirmed no service-account keys and that `weekendwise-run` can't write Firestore. Two more images were deployed later the same day (`-230443` with the in-page dropdowns), and the stack was then removed with `make destroy` for the IAC-06 rehearsal.

Still needed (owner): after the stack is rebuilt, restore an earlier image once (`make images`, then `make deploy IMAGE=<older tag>`) and re-run `make smoke-cloud`. Keep the URL and tags in a private note.

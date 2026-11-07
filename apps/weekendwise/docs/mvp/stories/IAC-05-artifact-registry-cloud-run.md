# IAC-05 — Artifact Registry, image build, and Cloud Run with Terraform

**Type:** Infrastructure as code + deployment  
**Priority:** P0  
**Estimate:** 5–8 hours  
**Story points:** 5 (registry, build automation, Cloud Run service, access controls, and rollback)  

## User story

As the demo owner, I want `make build` and `make deploy` to build the container and roll it out to Cloud Run through Terraform so that deployments are repeatable and the service settings (scaling, identity, access) live in code.

## Scope

- **Artifact Registry** Docker repository (`google_artifact_registry_repository`) in the configured region, plus a cleanup policy that keeps only the last N images.
- **`make build`**: runs `gcloud builds submit` with the build service account from IAC-03, tagging the image with the git commit SHA (or a timestamp when there's no git repository).
- **Cloud Run** (`google_cloud_run_v2_service`):
  - image from `var.image`; a public placeholder image is used until the app exists,
  - runtime service account from IAC-03,
  - min instances **0**, max instances from `var.max_instances` (default 2), and conservative CPU, memory, and request timeout,
  - environment variables for project, region, Firestore database/collection, and model IDs (no secrets),
  - `deletion_protection` set from a variable so teardown works.
- **Public access** only when `allow_unauthenticated = true` (default **false**), which adds `roles/run.invoker` for `allUsers`. The how-to must show the cost and abuse warning before enabling it.
- **`make deploy IMAGE=...`** runs `terraform apply` with the new image. Rollback is `make deploy IMAGE=<previous tag>`.
- Output the service URL.

**Out of scope:** custom domains, load balancers, Cloud Armor, multi-region deployment, build triggers tied to a git host (later, with CI), and the Dockerfile and app code themselves (MVP-03, MVP-07).

## Acceptance criteria

- [x] `make apply` creates the registry and a Cloud Run service with min 0 and max instances from configuration, running as the runtime service account.
- [x] `make build` pushes a versioned image to the private repository; `make deploy` rolls it out and prints the URL.
- [ ] With the default settings, an unauthenticated request is rejected; with `allow_unauthenticated = true` it succeeds, and the warning is documented. *(Default rejection proven, HTTP 403; public mode documented but not switched on.)*
- [ ] Rolling back to a previous image tag via `make deploy` works and is documented. *(Documented; not yet rehearsed.)*
- [x] Re-running `make apply` with the same image makes no changes.
- [ ] [MVP-03](MVP-03-cloud-run-deploy.md) infrastructure criteria are met through this automation; MVP-03 keeps the Dockerfile, health check, and smoke test.

## Dependencies and deliverables

**Dependencies:** IAC-03 (service accounts). A real image requires the MVP-03 app shell; until then the placeholder image is used.  
**Deliverables:** `infra/stack/registry.tf`, `infra/stack/run.tf`, and the `build`/`deploy` Makefile targets.

## Completion evidence

Image tag, service URL (kept in a private note if public), `make verify` output, and a rollback rehearsal log.

## Progress record — 🟡 Deployed and verified, waiting for a rollback rehearsal (updated 2026-11-06)

Done:
- `infra/stack/registry.tf`: private Docker repository `weekendwise` in the region; keeps the 10 newest images and deletes older ones after 30 days.
- `infra/stack/run.tf`: `google_cloud_run_v2_service` running as `weekendwise-run`; min 0, max `var.max_instances` (default 2, allowed 1–5); 1 vCPU / 1 GiB; CPU only during requests; 180 s timeout; startup probe on `/healthz`; non-secret environment; `deletion_protection` from a variable. Operators get `run.invoker`; `allUsers` only when `allow_unauthenticated = true` (default false).
- Outputs `cloud_run` (URL, image, identity, scaling, revision) and `image_repository`.
- `make build`: tests first, then Cloud Build as `weekendwise-build`. Tagged with the git SHA, or a UTC timestamp without git.
- `make deploy [IMAGE=<tag>]`: Terraform apply; the image is saved in `image.auto.tfvars.json` so a later `make apply` doesn't revert it.
- Also `make release`, `make images`, `make proxy`, `make smoke-cloud`, and a Cloud Run section in `make verify` (settings plus the 403 check).
- `terraform validate` passes. `make plan` (read-only) shows **3 to add, 0 to change, 0 to destroy**.

Live run on `weekendwise-demo-jytx` (2026-11-06, times UTC):
- 22:34 `make apply` created the registry and the service (placeholder image). `make verify` then showed `✓ stack: no changes`, min 0 / max 2, runtime identity `weekendwise-run`, private, deletion protection on.
- 22:42, 22:49 and 23:10 `make release` / `make deploy` rolled out three app images (`20261106-223850`, `-224657`, `-230443`), each a new revision.
- 22:57 `make smoke-cloud` passed 9 of 9, including HTTP 403 without a token and one live plan ([evidence](../evidence/MVP-03-cloud-run-smoke.md)).
- 23:11 the stack was removed with `make destroy` as the first step of the [IAC-06](IAC-06-teardown-destroy.md) rehearsal.

Fixes found during the live run:
- **`/healthz` is reserved by Cloud Run's front end**, which answers its own 404 without reaching the container. The app now also serves `/health`; `make smoke-cloud` and the 403 check in `make verify` use it. The startup probe keeps `/healthz`, which works inside the container.
- `make proxy` needs the gcloud `cloud-run-proxy` component. gcloud offers to install it on first use, but that first run then fails; run `make proxy` again.

Still needed (owner): after the stack is rebuilt, one rollback rehearsal. The new registry starts empty, so release twice, then `make images` and `make deploy IMAGE=<older tag>`, then `make smoke-cloud`. Optional: try `allow_unauthenticated = true` once and switch it back.

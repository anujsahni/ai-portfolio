# Setup guide 03 — Cloud Build, Artifact Registry, and Cloud Run

**Related stories:** [MVP-03](../stories/MVP-03-cloud-run-deploy.md) · [IAC-05](../stories/IAC-05-artifact-registry-cloud-run.md)
**Purpose:** what the app container is, how it's built and deployed, and how to check, roll back, and clean up.

> **Provisioning is automated.** The registry and the Cloud Run service are created by Terraform (`infra/stack/registry.tf`, `infra/stack/run.tf`). Images are built with `make build` and rolled out with `make deploy`. The step-by-step commands are in [how-to 00, Steps 12–14](00-provision-with-terraform.md#step-12--put-it-on-cloud-run). Use the console only to look; changes made there cause drift.

## Before you start

- How-to 00 Steps 1–10 are done (project, identities, Firestore, guide data), and `make verify` is clean.
- `make test` passes (the build runs it first).
- Optional: `make run` works on your computer ([guide 06](06-web-app.md)).

## 1. The container

| | |
|---|---|
| Dockerfile | `Dockerfile` at the repository root: `python:3.14-slim`, pinned `requirements.txt`, the `weekendwise/` package, and `data/seed/` (cities, interests, sample trips, simulated conditions). The guides themselves live in Firestore. |
| Process | `uvicorn --factory weekendwise.web.server:create_app` on `$PORT` (8080), one process per instance |
| User | non-root (uid 10001) |
| Credentials | none in the image. On Cloud Run the attached `weekendwise-run` service account is used automatically. |
| Health | `GET /health` (also `/healthz`): the process is up (no cloud calls). Cloud Run's startup probe uses `/healthz` inside the container. From outside, use `/health`: Cloud Run's front end reserves `/healthz` and returns its own 404. |
| Readiness | `GET /readyz`: settings load and Firestore answers a 1-document read as the runtime identity |
| Version | `APP_VERSION` is the image tag, shown by `/health` |

What gets uploaded to Cloud Build is controlled by `.gcloudignore`: only `Dockerfile`, `.dockerignore`, `cloudbuild.yaml`, `requirements.txt`, `weekendwise/`, and `data/seed/`. Your `.env`, Terraform state, and `.venv` stay on your computer.

To build and run it locally with Docker (optional):

```bash
docker build -t weekendwise:local .
docker run --rm -p 127.0.0.1:8081:8080 --env-file .env -e WEEKENDWISE_RUN_AS=run \
  -e GOOGLE_APPLICATION_CREDENTIALS=/creds/adc.json \
  -v $HOME/.config/gcloud/application_default_credentials.json:/creds/adc.json:ro weekendwise:local
```

That mounts your own sign-in read-only and impersonates `weekendwise-run`, the same identity Cloud Run uses.

## 2. The build (`make build`)

- Runs `make test`, then `gcloud builds submit` with `cloudbuild.yaml`, as the **`weekendwise-build`** service account.
- Tags the image with the git commit, or a UTC timestamp when there's no git repository (e.g. `20261106-214500`).
- Pushes to the private repository `us-central1-docker.pkg.dev/<project>/weekendwise/app`.
- Build logs go to Cloud Logging only (**Cloud Build → History** in the console).
- The registry keeps the 10 most recent images and cleans up older ones after 30 days.

## 3. The service (`make deploy`)

`make deploy` writes the image into `infra/stack/image.auto.tfvars.json` and runs `terraform apply`. Settings, all in `infra/stack/run.tf`:

| Setting | Value | Why |
|---|---|---|
| Identity | `weekendwise-run` | Can call Vertex AI and **read** Firestore; can't write it ([IAC-03](../stories/IAC-03-service-identities-iam.md)) |
| Min / max instances | 0 / 2 (`max_instances`, 1–5) | Scale to zero when idle; bounded cost |
| Concurrency | 10 requests per instance | The app also limits itself to 3 plans at a time |
| CPU / memory | 1 vCPU / 1 GiB, CPU only during requests, startup boost | Enough for the planner; cheap when idle |
| Request timeout | 180 s | The planner stops itself at 150 s |
| Environment | project, region, model IDs, Firestore names, limits | No secrets |
| Access | private (operators get `run.invoker`) | Public only with `allow_unauthenticated = true` (see below) |
| Delete protection | on | Lifted only inside `make destroy` |

## 4. Verify

```bash
make smoke-cloud
```

It checks the settings above, that a request without a token gets HTTP 403, `/health` and `/readyz` as you, and one live plan through Cloud Run. It writes [evidence/MVP-03-cloud-run-smoke.md](../evidence/MVP-03-cloud-run-smoke.md) without the service URL. `make verify` also shows the Cloud Run settings and the 403 check.

To use the app in a browser: `make proxy`, then open http://localhost:8082.

In the console: **Cloud Run → weekendwise** shows revisions, the **Logs** tab, and metrics. **Artifact Registry → weekendwise → app** lists images.

## 5. Roll back

```bash
make images
make deploy IMAGE=<earlier tag>
make smoke-cloud
```

Terraform creates a new revision from the older image and sends all traffic to it. Don't use the console's "Manage traffic" for this: Terraform would undo it on the next `make apply`.

## 6. Public access (optional, live demos only)

Set `allow_unauthenticated = true` in `infra/stack/terraform.tfvars` and run `make apply`. This grants `roles/run.invoker` to `allUsers`.

> ⚠️ Anyone with the URL can then trigger Gemini calls on your billing account. Built-in limits: 6 plans per person per 10 minutes, 3 at a time and 30 a day per instance, at most 2 instances (worst case about 60 plans, roughly $0.60, a day: under the $20 monthly budget even if abused all month). The $20 budget only sends alerts. Use sample data only, and turn it off afterwards.

## Cleanup

`make destroy` removes the service and the registry (with all images) together with the rest of the stack; `make verify-destroyed` confirms it. See [how-to 00, Tearing down](00-provision-with-terraform.md#tearing-down).

## Official references

- [Cloud Build overview](https://cloud.google.com/build/docs/overview)
- [Artifact Registry overview](https://cloud.google.com/artifact-registry/docs/overview)
- [Cloud Run overview](https://cloud.google.com/run/docs/overview/what-is-cloud-run)
- [Cloud Run pricing](https://cloud.google.com/run/pricing)
- [Cloud Run IAM](https://cloud.google.com/run/docs/securing/managing-access)
- [Testing private services with `gcloud run services proxy`](https://cloud.google.com/run/docs/authenticating/developers)

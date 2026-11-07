# IAC-03 — Service identities and least-privilege IAM with Terraform

**Type:** Infrastructure as code + security  
**Priority:** P0  
**Estimate:** 3–5 hours  
**Story points:** 3 (three service accounts, role bindings, and impersonation; no keys)  

## User story

As the demo owner, I want the runtime, ingestion, and build identities and their permissions defined in Terraform so that access is least-privilege, reviewable in code, and removed cleanly on destroy.

## Scope

In `infra/stack/`:

- **Runtime service account** (`weekendwise-run`), attached to Cloud Run, with:
  - Vertex AI model invocation (`roles/aiplatform.user`, or a narrower role if verified),
  - Firestore **read-only** access (`roles/datastore.viewer`),
  - log writing (`roles/logging.logWriter`).
- **Ingestion service account** (`weekendwise-ingest`) with Firestore read/write (`roles/datastore.user`) and Vertex AI invocation, used by `make seed` through impersonation.
- **Build service account** (`weekendwise-build`) for Cloud Build with Artifact Registry write and log writing only.
- Grant the operator (variable `operator_principals`) `roles/iam.serviceAccountTokenCreator` on the ingestion and build accounts so they can impersonate them. No other human role changes.
- Role names must be checked against current Google documentation at implementation time.

**Out of scope:** service-account keys (prohibited), organization-level IAM, custom roles (unless a predefined role is clearly too broad), and Workload Identity Federation for CI.

## Acceptance criteria

- [x] The three service accounts and their role bindings are created by `make apply` and removed by `make destroy`.
- [x] The runtime account can read but **cannot write or delete** Firestore documents (verified by `make verify`).
- [x] The ingestion account can write `guide_chunks` and `guide_sources` when impersonated by the operator.
- [x] No `google_service_account_key` resource exists anywhere in `infra/`, and no key appears in the project after apply.
- [x] IAM bindings use additive `_member` resources (not authoritative `_policy`) so Terraform can't wipe unrelated project access.
- [x] Role choices and their reasons are listed in the how-to.

## Dependencies and deliverables

**Dependencies:** IAC-02.  
**Deliverables:** `infra/stack/iam.tf`, verification checks in `make verify`.

## Completion evidence

`make verify` output showing the runtime account's read succeeds and its write is denied, and an empty key list for each service account.

## Completion record (2026-11-06) ✅ Done

- `infra/stack/iam.tf`: `weekendwise-run`, `weekendwise-ingest`, `weekendwise-build`, 8 additive role bindings, operator impersonation (token creator on all three; act-as on run and build). The plan shows 16 to add.
- The operator is filled automatically from `gcloud config get-value account` into the git-ignored `infra/stack/operator.auto.tfvars.json`.
- `scripts/verify_iam.py` (run by `make verify`) impersonates each account and checks expected and forbidden permissions with `testIamPermissions`, including that the runtime account can read but not create, update, or delete Firestore entities, and that no user-managed keys exist.
- Kept `roles/aiplatform.user` rather than a custom invoke-only role: deleted custom-role IDs can't be reused for about 37 days, which breaks destroy/rebuild.
- Owner ran `make apply` (16 added). `make verify` reports no drift and:
  - `weekendwise-run`: can predict, get/list entities, write logs; **cannot** create/update/delete entities or upload images; 0 keys.
  - `weekendwise-ingest`: can predict and create/get/update entities; cannot upload images; 0 keys.
  - `weekendwise-build`: can upload images, write logs, read objects; cannot predict or read Firestore; 0 keys.
- Removal by `make destroy` is exercised in IAC-06's full-cycle rehearsal.

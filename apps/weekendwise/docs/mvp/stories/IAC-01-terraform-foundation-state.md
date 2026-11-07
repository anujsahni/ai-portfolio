# IAC-01 — Terraform foundation, state, and automation commands

**Type:** Infrastructure as code  
**Priority:** P0  
**Estimate:** 4–6 hours  
**Story points:** 3 (repo layout, two-stage state, pinned tooling, and one-command wrappers)  

## User story

As the demo owner, I want a single Terraform codebase with safe state handling and one-command wrappers so that every Google Cloud resource for WeekendWise is created, changed, and destroyed by code instead of console clicks.

## Scope

- Create `infra/` with two Terraform root modules:
  - `infra/bootstrap/`: project-level foundation (IAC-02). Uses **local state** (git-ignored) because the project and state bucket don't exist yet.
  - `infra/stack/`: everything inside the project (IAC-03, IAC-04, IAC-05). Uses a **GCS remote state backend** in a versioned bucket created by bootstrap.
- Pin the Terraform version and the `hashicorp/google` provider major version (verify the current major at implementation). Commit `.terraform.lock.hcl`.
- Provide `infra/bootstrap/terraform.tfvars.example` and `infra/stack/terraform.tfvars.example`. Real `*.tfvars` and generated `backend.hcl` are git-ignored.
- Add a root `Makefile` with these targets: `tools`, `configure`, `check`, `bootstrap`, `bootstrap-plan`, `plan`, `apply`, `build`, `deploy`, `seed`, `verify`, `destroy`, `destroy-all`, `verify-destroyed`. Targets owned by later stories print "not available yet". Each target is idempotent and prints what it will touch.
- Bootstrap writes `infra/stack/backend.hcl` (bucket and prefix) so `make plan` works without hand-editing.
- Authenticate with Application Default Credentials (`gcloud auth application-default login`), with optional service-account impersonation. **No service-account key files.**
- `make check` runs `terraform fmt -check -recursive` and `terraform validate` for both modules.

**Out of scope:** CI/CD pipelines that apply automatically (a later story can add GitHub Actions with Workload Identity Federation), Terraform Cloud, multiple environments beyond one demo environment, and modules published for reuse.

## Acceptance criteria

- [x] `infra/bootstrap` and `infra/stack` exist with pinned Terraform and provider versions and a committed lock file.
- [x] Stack state is stored in a GCS bucket with versioning and uniform bucket-level access; bootstrap state is local and git-ignored.
- [x] No credentials, billing account IDs, state files, or real tfvars are committed. `.gitignore` covers them.
- [x] Every Makefile target in scope exists, has a one-line help text (`make help`), and fails with a clear message if required variables or tools are missing.
- [x] `make check` passes on a clean checkout.
- [x] Running `make plan` twice in a row after `make apply` shows **no changes** (idempotent).
- [x] The [provisioning how-to](../guides/00-provision-with-terraform.md) matches the actual commands.

## Dependencies and deliverables

**Dependencies:** None (the owner needs a Google account and billing access to *run* it).  
**Deliverables:** `infra/` skeleton, `Makefile`, tfvars examples, `.gitignore` entries, and the how-to.

## Completion evidence

Output of `make check` and of a second `make plan` showing no changes. No state files in the repository.

## Completion record (2026-11-06) ✅ Done

- `make check` passes (format + validate, Google provider 8.10, lock files for macOS and Linux).
- Live run on `weekendwise-demo-jytx`: `make bootstrap` → `make apply` → `make verify` reports `✓ bootstrap: no changes` and `✓ stack: no changes`. Stack state is stored in the versioned `weekendwise-demo-jytx-tfstate` bucket.
- First verify found drift in the budget's empty notification block; fixed by only adding that block when extra emails are set. Plans are now clean.
- No state, tfvars, or billing IDs in the repository.

**Later changes (2026-11-06):**
- When `TF_VAR_billing_account_id` is missing (it lasts one terminal session), the error now prints the exact `export` line, using the billing account already linked to the project when there is one.
- `.gitignore` reviewed before the first commit. It now also covers credential JSON files, Terraform override files and the lock-info file, Python tool caches, editor folders, and Claude Code's personal settings file. A dry-run commit (374 files) contained no state, tfvars, `.env`, logs, keys, or billing IDs.

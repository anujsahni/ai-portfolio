# IAC-01 — Terraform foundation, state and automation commands

**Type:** Infrastructure as code  
**Priority:** P0  
**Estimate:** 4–6 hours  
**Story points:** 3 (repo layout, two-stage state, pinned tooling and one-command wrappers)  

## User story

As the demo owner, I want a single Terraform codebase with safe state handling and one-command wrappers so that every AWS resource for DealPulse is created, changed and destroyed by code instead of console clicks.

## Scope

- Create `infra/` with two Terraform root modules:
  - `infra/bootstrap/`: account-level foundation (IAC-02). Uses **local state** (git-ignored) because the state bucket doesn't exist yet.
  - `infra/stack/`: everything the app needs (IAC-03 to IAC-06). Uses an **S3 remote state backend** with versioning, encryption and S3 native locking (`use_lockfile = true`), created by bootstrap.
- Pin the Terraform version and the `hashicorp/aws` provider major version (verify the current major at implementation). Commit `.terraform.lock.hcl` for macOS and Linux.
- Set `default_tags` on the provider (`app = dealpulse`, `env = demo`, `managed_by = terraform`) so every resource is traceable and the teardown check can find leftovers.
- Provide `infra/bootstrap/terraform.tfvars.example` and `infra/stack/terraform.tfvars.example`. Real `*.tfvars` and the generated `backend.hcl` are git-ignored.
- Add an app `Makefile` with these targets: `help`, `tools`, `configure`, `check`, `bootstrap`, `bootstrap-plan`, `plan`, `apply`, `data`, `train`, `approve-model`, `deploy-model`, `seed`, `build`, `deploy`, `release`, `proxy`, `pause`, `resume`, `verify`, `destroy`, `destroy-all`, `verify-destroyed`. Targets owned by later stories print "not available yet". Each target is idempotent and prints what it will touch.
- `make configure` picks a unique name prefix (e.g. `dealpulse-<4 chars>`) used for globally unique names such as S3 buckets and the OpenSearch domain, and writes it to the tfvars files.
- Bootstrap writes `infra/stack/backend.hcl` (bucket, key, region) so `make plan` works without hand-editing.
- Authenticate with short-lived credentials (`aws sso login` or another named profile). **No long-lived access keys.** `make tools` checks Terraform, AWS CLI, the Session Manager plugin, Python and the signed-in identity (`aws sts get-caller-identity`).
- `make check` runs `terraform fmt -check -recursive` and `terraform validate` for both modules.
- Start guide 00 (provision and destroy with Terraform) with the commands that exist so far.

**Out of scope:** CI/CD pipelines that apply automatically (a later story could add GitHub Actions with OIDC), Terraform Cloud, multiple environments or accounts, DynamoDB lock tables and reusable published modules.

## Acceptance criteria

- [x] `infra/bootstrap` and `infra/stack` exist with pinned Terraform and provider versions and committed lock files.
- [x] Stack state lives in an S3 bucket with versioning, encryption, public access blocked and native locking; bootstrap state is local and git-ignored.
- [x] Every resource created by either module carries the default tags.
- [x] No credentials, account IDs in tfvars, state files or real tfvars are committed; `.gitignore` covers them.
- [x] Every Makefile target in scope exists, has a one-line help text (`make help`) and fails with a clear message if required variables, tools or sign-in are missing.
- [x] `make check` passes on a clean checkout.
- [x] Running `make plan` twice in a row after `make apply` shows **no changes** (idempotent).
- [x] Guide 00 matches the actual commands.

## Dependencies and deliverables

**Dependencies:** None (the owner needs an AWS account and permission to create resources to *run* it).  
**Deliverables:** `infra/` skeleton, `Makefile`, tfvars examples, `.gitignore` entries and guide 00.

## Completion evidence

Output of `make check` and of a second `make plan` showing no changes. A dry-run commit listing shows no state, tfvars or credentials.

## Completion record (2026-11-09) ✅ Done

- **Terraform 1.17.1, AWS provider ~> 6.72** (6.72.0 locked). Lock files cover macOS and Linux (arm64 and amd64), so CodeBuild can use them too.
- `make check` passes (format + validate, both layers). `make tools` checks Terraform ≥ 1.10, AWS CLI, Session Manager plugin, Python ≥ 3.11 and the signed-in identity.
- **Live run** in the owner's AWS account, `us-east-1`, prefix `dealpulse-y34c`: `make configure` → `make bootstrap` (7 resources: state bucket, versioning, encryption, public-access block, ownership, 90-day old-version expiry, TLS-only policy) → `make apply` (empty stack, state written to S3) → `make verify`: `✓ bootstrap: no changes`, `✓ stack: no changes`. A second `make plan` showed **No changes**.
- State bucket checks: versioning `Enabled`, all four public-access blocks `True`, a plain-HTTP request returns **403**, and the bucket carries the four default tags.
- Every later target exists in `make help` and prints which story delivers it.
- `git add --dry-run` lists no state, tfvars, backend settings, logs or `.env`. An app-level `.gitignore` was added (the root pattern for `infra/.verify-*.log` only matched the repo root).
- [Guide 00](../guides/00-provision-with-terraform.md) documents setup, `make verify` output, generated files and troubleshooting.

**Deviations from the plan:**
- The state bucket was built here rather than in IAC-02, because this story's criteria need remote state. IAC-02 adds the budget.
- Sign-in is the existing `default` profile, an **IAM user with long-lived access keys** (not SSO). The code creates and stores no keys; `make tools` flags the long-lived key as a recommendation. Moving to `aws sso login` later needs no code change (`AWS_PROFILE=<sso-profile>`).
- Homebrew couldn't install a newer Terraform (outdated Xcode Command Line Tools), so the official 1.17.1 binary was installed to `~/.local/bin` after checking HashiCorp's SHA-256 checksum. Homebrew's 1.5.7 was removed; WeekendWise still validates with 1.17.1.
- `YES=1` skips Terraform's approval prompt for non-interactive runs (after reviewing a plan).

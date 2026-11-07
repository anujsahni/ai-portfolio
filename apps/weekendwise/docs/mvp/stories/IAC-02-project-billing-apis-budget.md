# IAC-02 — Project, billing link, APIs, and budget with Terraform

**Type:** Infrastructure as code  
**Priority:** P0  
**Estimate:** 4–6 hours  
**Story points:** 3 (project, billing, APIs, budget, and state bucket in one bootstrap apply)  

## User story

As the demo owner, I want `make bootstrap` to create the WeekendWise project, link billing, enable the required APIs, and set a budget with alerts so that MVP-01 is reproducible in minutes and nothing depends on manual console steps.

## Scope

In `infra/bootstrap/`:

- `google_project` with a configurable ID and an optional random suffix (project IDs can't be reused for about 30 days after deletion). Set `deletion_policy` from a variable so `make destroy-all` can delete it.
- Link the billing account from the variable `billing_account_id` (passed via git-ignored tfvars or `TF_VAR_billing_account_id`).
- `google_project_service` for the MVP APIs: Vertex AI, Cloud Firestore, Cloud Run Admin, Cloud Build, Artifact Registry, and Cloud Logging. Also enable the APIs Terraform itself needs: Cloud Resource Manager, Service Usage, IAM, Cloud Billing Budget, Cloud Storage, and Cloud Monitoring (only if email channels are used).
- `google_billing_budget` scoped to this project only, monthly, with the amount from `budget_amount_usd` (**default and maximum $20**, enforced by variable validation), thresholds at 50/80/100% actual (plus optional 100% forecasted), and credits excluded so alerts reflect real usage. Optional extra recipients through Cloud Monitoring email notification channels.
- A versioned GCS bucket for stack state, with `force_destroy` controlled by a variable for teardown.
- Outputs: project ID, project number, region, and state bucket name. Write `infra/stack/backend.hcl`.

**Out of scope:** creating billing accounts or payment methods, organization policies, folders, and hard spend caps (budgets only alert).

## Acceptance criteria

- [x] `make bootstrap` on an empty account (with billing access) creates the project, links billing, enables exactly the listed APIs, creates the budget and state bucket, and writes `backend.hcl`.
- [x] The budget is visible in Cloud Billing, scoped only to this project, with the configured thresholds.
- [x] Re-running `make bootstrap` makes no changes.
- [x] The billing account ID never appears in committed files or Terraform outputs.
- [x] Docs and the Makefile state that the budget alerts only and does not cap spending.
- [x] [MVP-01](MVP-01-project-billing-guardrails.md) acceptance criteria are satisfied by this automation plus the owner's verification.

## Dependencies and deliverables

**Dependencies:** IAC-01.  
**Deliverables:** `infra/bootstrap/*.tf`, tfvars example, and outputs.

## Completion evidence

`make bootstrap` summary (project ID, region, APIs, budget name) and a screenshot or `gcloud billing budgets list` output showing the budget. Don't include the billing account ID.

## Completion record (2026-11-06) ✅ Done

- `make bootstrap` created 14 resources: project `weekendwise-demo-jytx` (billing enabled), 11 APIs, budget, and state bucket.
- `gcloud billing budgets list` shows `weekendwise-monthly-20usd`: 20 USD/month, scoped to `projects/1084959648844` only, 4 alert rules (50/80/100% actual and 100% forecast).
- Budget values above $20 are rejected by variable validation.
- Re-plan reports no changes. The billing account ID appears in no committed file or output.
- Google also auto-enabled dependency APIs (for example, `pubsub`, `firebaserules`, `containerregistry`); these are expected and documented in how-to 00.

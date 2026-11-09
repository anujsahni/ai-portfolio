# IAC-02 — Account guardrails: budget, tags and region (Terraform)

**Type:** Infrastructure as code + cost control  
**Priority:** P0  
**Estimate:** 2–4 hours  
**Story points:** 2 (state bucket, budget and alerts; no project to create on AWS)  

## User story

As the demo owner, I want the account-level foundation (state storage, a cost budget with alerts and a fixed region) created by Terraform so that I can see and limit spend before any paid resource exists.

## Scope

- In `infra/bootstrap/`:
  - the **Terraform state bucket**: versioning on, SSE-S3 encryption, all public access blocked, TLS-only bucket policy, `prevent_destroy` lifecycle guard (lifted only by IAC-07's destroy path);
  - an **AWS Budgets** cost budget of **$60/month**, filtered to the `app = dealpulse` cost allocation tag where possible, with four email notifications: 50%, 80% and 100% of actual spend, and 100% of forecasted spend;
  - outputs used by the stack: state bucket name, region, name prefix.
- Fix the region to `us-east-1` in one variable used by both modules.
- Document how to activate the `app` cost allocation tag in Billing (a one-time console step if Terraform can't do it in the account), and that a budget **alerts but does not cap** spending.
- `make bootstrap` applies this module and writes `infra/stack/backend.hcl`.

**Out of scope:** AWS Organizations, Service Control Policies, account creation, Cost Anomaly Detection, hard spending caps and automatic shutdown on budget breach.

## Acceptance criteria

- [x] `make bootstrap` creates the state bucket and the budget with no console clicks beyond sign-in.
- [x] The budget amount and the four alert thresholds match this story; alert emails come from a variable, not code.
- [x] The state bucket rejects non-TLS requests and public access, and keeps object versions.
- [x] Re-running `make bootstrap` shows no changes.
- [x] Guide 00 warns that creating resources costs money and that budgets only alert.

## Dependencies and deliverables

**Dependencies:** IAC-01.  
**Deliverables:** `infra/bootstrap/*.tf`, budget and state-bucket outputs, guide 00 section.

## Completion evidence

`terraform output` from bootstrap, a screenshot or CLI listing of the budget (`aws budgets describe-budgets`), and a clean second plan.

## Completion record (2026-11-09) ✅ Done

- **Budget** `dealpulse-y34c-monthly`: $60.00/month, cost filter `TagKeyValue = user:app$dealpulse`, four email alerts (ACTUAL 50/80/100%, FORECASTED 100%) to the address in the git-ignored tfvars. Confirmed live with `aws budgets describe-budget` / `describe-notifications-for-budget`.
- **Cost allocation tag** `app` switched from Inactive to **Active** by Terraform (`aws_ce_cost_allocation_tag`).
- `make bootstrap` re-run: no changes. `make verify` now also prints the budget, spend so far, alert count and tag status.
- Region fixed to `us-east-1` in one variable passed to both layers (bootstrap → `bootstrap.auto.tfvars.json`).
- [Guide 00](../guides/00-provision-with-terraform.md) has a *Budget and alerts* section: tag filter, 24-hour activation delay, "alerts only", how to check and change it.

**Findings and decisions:**
- The account spent about **$98 last month on other workloads**. An account-wide budget would have fired every alert at once, so the budget counts only `app=dealpulse` resources. Consequence: spend shows $0 until AWS applies the tag (up to 24 hours), and untaggable charges aren't counted.
- An existing, unrelated budget ("My Monthly Cost Budget", $50) was left untouched.
- The state bucket (also in this story's scope) was delivered in IAC-01.
- Activating the `app` tag is account-wide. `make destroy-all` (IAC-07) returns it to Inactive, its previous state.

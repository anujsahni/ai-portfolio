# MVP-01 — Google Cloud project, billing, and guardrails

**Type:** Platform setup + how-to documentation  
**Priority:** P0  
**Estimate:** 2–4 hours, excluding access approval  
**Story points:** 1 (owner approval and verification only; provisioning is automated in IAC-01/IAC-02)  

## User story

As the demo owner, I want an isolated Google Cloud project with clear billing and budget guardrails so that I can experiment without mixing demo resources with other workloads or losing visibility into spend.

## Scope

- Provisioning is automated: [IAC-02](IAC-02-project-billing-apis-budget.md) creates the project, links billing, enables APIs, and creates the budget through `make bootstrap`. This story covers the owner's approval, the run, and the verification.
- Approve which billing account and budget amount to use, and grant yourself billing access if needed.
- Run `make bootstrap` following [how-to 00](../guides/00-provision-with-terraform.md), then `make verify`.
- Keep [guide 01](../guides/01-project-and-billing.md) as the console reference for inspecting what Terraform created; explain that budget alerts don't cap usage.
- Record project ID and region privately (`.env`).

**Out of scope:** creating resources by hand in the console, creating payment methods, hard spend caps, organization policy changes, or using a personal/service-account key.

## Acceptance criteria

- [x] `make bootstrap` creates the project, billing link, required APIs (including Firestore), and monthly budget with no console clicks beyond sign-in and billing access.
- [x] How-to 00 and guide 01 clearly warn that attaching billing can incur charges and that a budget only alerts.
- [x] The enabled APIs are limited to products required by the MVP plus the APIs Terraform needs to manage them, as listed in IAC-02.
- [x] Project ID and region are recorded privately; no credentials, billing account IDs, state, or tfvars are committed.
- [x] A reviewer who did not author the automation can run `make bootstrap` and `make verify` from how-to 00 without needing an undocumented assumption.

## Dependencies and deliverables

**Dependencies:** IAC-01, IAC-02.  
**Deliverables:** This story, setup guide 01, and a private project/region/budget record maintained by the demo owner.

## Completion evidence

Link the project’s non-sensitive ID/region record and confirm the budget notification configuration is visible in Cloud Billing. Do not include billing account identifiers or personal payment details in the repository.

## Completion record (2026-11-06) ✅ Done

- The owner (not the author of the automation) followed how-to 00 and ran `make bootstrap`, `make apply`, and `make verify` on `weekendwise-demo-jytx`. The owner's run counts as the independent review.
- Billing linked, required APIs enabled, and `weekendwise-monthly-20usd` ($20/month, project-scoped, 4 alert rules) visible in Cloud Billing.
- Project ID and region recorded privately; nothing sensitive committed.
- Issues found during the run (budget drift, the `gcloud` quota-project flag) were fixed in code and added to the how-to's troubleshooting table.

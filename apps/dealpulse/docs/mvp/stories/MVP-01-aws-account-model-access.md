# MVP-01 — AWS account, model access and guardrails

**Type:** Platform setup + how-to documentation  
**Priority:** P0  
**Estimate:** 1–3 hours, excluding access approval  
**Story points:** 1 (owner approval and verification only; provisioning is automated in IAC-01/IAC-02)  

## User story

As the demo owner, I want a known AWS account with sign-in, a budget and the Bedrock models enabled so that I can build DealPulse without surprise costs or access errors later.

## Scope

- Provisioning is automated by [IAC-02](IAC-02-account-budget-tags.md). This story covers the owner's decisions, the run and the verification.
- Decide which AWS account to use (a dedicated or sandbox account is preferred) and who receives budget alerts.
- Sign in with short-lived credentials (`aws sso login` or a named profile) and run `make tools`, `make bootstrap` and `make verify`.
- In `us-east-1`, make sure the account can use **Claude Opus 5.5** and **Titan Text Embeddings V2** on Bedrock. Anthropic models may ask for a one-time use-case form. Record the exact model IDs that work.
- Write guide 01 (account, budget and Bedrock model access) as a console reference for checking these, with screenshots or CLI commands.
- Record the account alias, region and name prefix privately in `.env`.

**Out of scope:** creating accounts or organizations, payment methods, Service Quotas increases beyond defaults, and any long-lived access key.

## Acceptance criteria

- [ ] `make bootstrap` succeeds and the budget with four alerts is visible.
- [ ] Bedrock lists both models as available in `us-east-1`, and `make tools` reports it.
- [ ] Guide 01 explains model access, the use-case form, that the budget only alerts, and how to check spend.
- [ ] Account details are recorded only in git-ignored files; no access keys exist for the operator.
- [ ] A reviewer who didn't write the automation can follow guide 00 and guide 01 without an undocumented step.

## Dependencies and deliverables

**Dependencies:** IAC-02.  
**Deliverables:** guide 01, a verified account, `.env` entries (not committed).

## Completion evidence

Output of `make tools` and `make verify`, and the Bedrock model IDs confirmed in the account (no account IDs in the evidence file).

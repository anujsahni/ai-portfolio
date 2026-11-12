# CL-14 — Activation: reverse ETL to mock Salesforce and Slack

**Phase:** 5 · Activate and close  
**Type:** Activation  
**Priority:** P0 (Slack is third on the cut line)  
**Estimate:** 3–5 hours  
**Story points:** 3 (a diff-based sync, a small mock API and an optional webhook)  
**Target day:** Sun 15 Nov

## User story

As an account manager at Northstar, I want the at-risk flag and the recommended next step to appear on the account record I already use, so that I act on the insight this week without opening a dashboard.

## Scope

- **Mock Salesforce API** (`mock-salesforce` container, FastAPI): `GET` and `PATCH /accounts/{id}` and a `GET /audit` log. It holds account fields `Delivery_Risk__c`, `Delivery_Risk_Drivers__c`, `Next_Step__c` and `Risk_Updated_At__c`. Every write is recorded in the audit log.
- **Reverse ETL sync** (`contextloop/activation/`): reads the governed at-risk model (the dbt mart, not the agent's free text), compares it with the CRM's current values, and applies only the changes. It reports inserts, updates and unchanged rows, like Fivetran Activations. Recommended next steps come from the governed agent's structured answer and are marked as AI-drafted.
- **Dry run first:** the app shows the planned diff; the presenter clicks **"Sync to Salesforce"** to apply it.
- **Slack (optional):** if `SLACK_WEBHOOK_URL` is set, post one message with the at-risk accounts and links to the mock CRM records. Without it, the app shows a preview of the message.
- **Act 5 in the app:** the diff, the sync button, the account records before and after, the audit log, and the Slack message or preview. A short closing line connects back to the COO's question.

**Out of scope:** real Salesforce or Slack workspaces; scheduling; field mapping UI.

## Acceptance criteria

- [ ] A dry run shows the correct diff: one update per at-risk account and no changes to other accounts.
- [ ] After the sync, a second dry run shows no changes (the sync is idempotent).
- [ ] Every write appears in the audit log with a timestamp and the source model.
- [ ] Only accounts from the governed mart are written; the naive agent's list is never synced (test).
- [ ] With a webhook set, one Slack message is posted; without it, the preview renders and no network call is made.
- [ ] The app clearly labels the CRM as a mock and next steps as AI-drafted.

## Dependencies and deliverables

**Dependencies:** CL-10 (next steps), CL-12 (Act 5 page), CL-06 (at-risk model).  
**Deliverables:** `contextloop/activation/`, the `mock-salesforce` service, the Act 5 page, tests.

## Completion evidence

The dry-run diff, the after-sync records, the audit log and the Slack message or preview.

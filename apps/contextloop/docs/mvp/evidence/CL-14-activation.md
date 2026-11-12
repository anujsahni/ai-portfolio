# CL-14 completion record: activation (reverse ETL to the mock CRM and Slack)

**Date:** 11 Nov 2026 · **Result:** all acceptance criteria met.

- **Mock Salesforce** (`mock-salesforce`, FastAPI): `GET /accounts`, `GET` and `PATCH /accounts/{id}`, `GET /audit`, `POST /reset`.
  Accounts are seeded from the landed Salesforce data; the fields are `Delivery_Risk__c`, `Delivery_Risk_Drivers__c`,
  `Next_Step__c`, `Next_Step_Source__c` and `Risk_Updated_At__c`.
- **Reverse ETL** (`contextloop/activation/sync.py`) reads `marts.account_risk`, compares it with the CRM, and writes only the
  differences.

Run from the stack (also covered by `tests/test_activation.py`):

```
dry run         {'update': 9, 'clear': 0, 'unchanged': 0}
apply           {'written': 9, 'update': 9, 'clear': 0, 'unchanged': 0}
second dry run  {'update': 0, 'clear': 0, 'unchanged': 9}
audit           9 writes, each with a timestamp and source_model = marts.account_risk
```

- **Only the governed mart decides what is written:** a test passes a naive-style list (including the demoted Quenmere account)
  and checks that the account set is still exactly the mart's.
- **Next steps:** from the governed agent's structured answer when one exists, labelled **AI-drafted**; otherwise from the
  playbook rule in the mart, labelled **Playbook rule (dbt)**.
- **Slack:** with no webhook (or a value that isn't an `https://` URL), only a preview is built and no network call is made
  (tested by making any call fail). With a webhook, exactly one message is posted (tested with a stubbed endpoint).
- **Act 5 in the app:** the dry run, **Sync to Salesforce**, the CRM records before and after, the audit log, the Slack preview,
  and a mock-CRM label. Screenshots: `docs/images/guide/09-act5-dry-run.png`, `10-act5-synced.png`.

A finding along the way: `.env.example` used inline comments, which Docker Compose passes through as part of the value. The
example now keeps comments on their own lines.

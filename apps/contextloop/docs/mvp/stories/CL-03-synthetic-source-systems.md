# CL-03 — Synthetic source systems, hidden truth and traps

**Phase:** 1 · Move  
**Type:** Data  
**Priority:** P0  
**Estimate:** 5–8 hours  
**Story points:** 5 (four related systems, a hidden truth, six traps that must be detectable)  
**Target day:** Wed 11 Nov

## User story

As the demo owner, I want four believable, linked source systems with a known right answer and planted traps, so that the agent's mistakes in Act 1 and its correct answer in Act 4 can both be proven, not just claimed.

## Scope

`make data` (the `datagen` job) generates, from one seed, the following for **Northstar Industrial**:

| System | Objects (approximate volumes) | Written to |
|---|---|---|
| SAP S/4HANA extract | `KNA1` customers (120), `VBAK` order headers (~9,000 over 18 months), `VBAP` order items (~27,000), `LIKP`/`LIPS` deliveries (~9,500), `VBRK`/`VBRP` billing (~8,800, including credit memos), `TCURR` exchange rates | Files the SAP connector reads (CL-04), with change timestamps (`ERDAT`, `AEDAT`) for incremental sync |
| Salesforce | `Account` (~135, including look-alikes and accounts with no SAP customer), `Opportunity` (renewals and expansions), `User` (account owners) | Fivetran-shaped tables (CL-05), with history-mode rows for `Account.Tier__c` |
| Zendesk | `ticket` (~3,000) with priority, status, tags and subject | Fivetran-shaped tables (CL-05) |
| Postgres carrier tracking | `shipment` and `shipment_event` (picked up, in transit, delivered), linked to SAP delivery numbers | Seeded into the `postgres` container |

- Standard SAP table and field names (`KUNNR`, `VBELN`, `NETWR`, `WAERK`, `VDATU`, `WADAT`, `WADAT_IST`), with short English descriptions in a data dictionary for the app.
- **Hidden truth** (`data/out/truth/`, never read by the app or the agents): the exact at-risk account list, each account's on-time rate, net revenue by region and quarter, and the expected answer to each golden question from CL-01.
- **Traps T1–T6** from the README, listed in `data/out/truth/traps.json` with the records involved:
  - T1: about 4% of deliveries cancelled and kept as soft-deleted rows.
  - T2: for some late shipments, the planned goods-issue date is on time but the actual delivery is late.
  - T3: about 35% of orders in EUR.
  - T4: two look-alike Salesforce accounts (for example "Halbrook Fluid Systems" and "Halbrook Fluid Systems GmbH") with only one mapped to SAP.
  - T5: three accounts promoted from Standard to Strategic in the middle of the quarter.
  - T6: a scenario flag that holds Zendesk's last sync two days behind.
- **Scenarios**: at least seven at-risk strategic accounts with different drivers (late shipments plus tickets, late shipments plus a renewal due), plus healthy strategic accounts and at-risk accounts that are *not* strategic, so the filter matters.
- **Schema-change seed** for CL-04: a second batch of `LIKP` rows that includes a new column `ZZ_CARRIER_ID`.
- Reproducible: the same seed gives byte-identical output.

**Out of scope:** LLM-generated text (templates keep it free and reproducible), real company names, materials master detail beyond what the story needs.

## Acceptance criteria

- [ ] `make data` writes all four systems and seeds Postgres in under 30 seconds; volumes within ±10% of the table above.
- [ ] Same seed → identical files (checksum test); a different seed → different data.
- [ ] Referential integrity: every order item has a header, every delivery links to an order, every shipment event links to a delivery, every mapped Salesforce account resolves to one SAP customer.
- [ ] The hidden truth is computed by code that is independent of the dbt models (no shared SQL), so it can check them.
- [ ] Each trap exists and changes at least one golden answer when ignored; a test computes the "naive" answer for each trap and confirms it differs from the truth.
- [ ] At least seven at-risk strategic accounts, at least one at-risk non-strategic account, and at least one account that becomes strategic mid-quarter and is at risk.
- [ ] No real company, person, email domain or phone number (emails use `example.com`; phones use reserved 555-01xx numbers).

## Dependencies and deliverables

**Dependencies:** CL-01 (definitions and golden questions), CL-02 (the image and the Postgres container).  
**Deliverables:** `contextloop/datagen/`, `data/generator/` inputs, `make data`, unit tests, `docs/mvp/evidence/CL-03-data-summary.md`.

## Completion evidence

The data summary: counts per object, the at-risk list size, the trap list and the naive-vs-true value for each golden question.

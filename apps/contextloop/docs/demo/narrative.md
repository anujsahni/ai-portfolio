# ContextLoop demo narrative

This is the agreed story for the ContextLoop demo. Every later story (data, connectors, dbt, metrics, agents, app) builds toward it. The definitions in this file are the specification: the data generator (CL-03) computes the hidden truth from them, and the dbt models (CL-06) and metrics (CL-07) implement exactly the same rules.

> **Synthetic data only.** Northstar Industrial and every account, person, order and ticket in the demo are invented. Nothing connects to a real SAP system, Salesforce org, Zendesk instance or Slack workspace.

## The customer

**Northstar Industrial** is a fictional mid-market maker of industrial valves, bearings and pumps. It sells to about 120 business customers in North America and EMEA through two sales organizations (US and Germany).

| System | Role at Northstar | What makes it hard |
|---|---|---|
| **SAP S/4HANA** (ERP) | Customers (`KNA1`), sales orders (`VBAK`, `VBAP`), deliveries (`LIKP`, `LIPS`), billing (`VBRK`, `VBRP`), exchange rates (`TCURR`) | Cryptic names; amounts in USD and EUR; cancelled orders and deliveries are deleted at the source; `TCURR` stores dates inverted |
| **Salesforce** (CRM) | Accounts, account tier, renewal opportunities, account owners | Account IDs are not SAP numbers; one look-alike duplicate account; tier changed during the period |
| **Zendesk** (support) | Tickets, status, tags | Shipping complaints are tagged inconsistently; some only say "late" in the subject |
| **Postgres** (carrier tracking service) | Shipments and tracking events | The *actual* delivery time lives only here |

## The personas

- **Asking:** Dana Okafor, Chief Operating Officer at Northstar (fictional). Wants a short, trustworthy answer they can act on this week.
- **Presenting:** a Fivetran sales engineering specialist, running a proof of value for Northstar's data and AI teams.
- **In the room:** Northstar's head of data (cares about trust and cost), a revenue operations lead (cares about the CRM) and an AI platform lead (cares about agents).

## The headline question

> *"Which of our strategic accounts are at risk because of late shipments, and what should the account teams do this week?"*

A correct answer needs all four systems, one rule for "on time", one rule for "strategic", correct handling of deleted records and currencies, and data recent enough to act on.

## The reporting date

All business definitions are evaluated **as of Friday 6 November 2026** (the *as-of date*). The data covers 18 months up to that date. "Last 90 days" means the 90 days ending on the as-of date (9 August to 6 November 2026, inclusive). Freshness (how long ago each source last synced) is measured against the real clock at demo time.

## Business definitions

Each definition names the exact source fields it uses. CL-03 (hidden truth), CL-06 (dbt models) and CL-07 (metrics) implement these rules and nothing else.

### Customer account (identity resolution, trap T4)

- A **customer** is an SAP customer: one row in `KNA1`, keyed by `KNA1.KUNNR`.
- A Salesforce account belongs to a customer when `salesforce.account.sap_customer_number_c = KNA1.KUNNR`.
- A Salesforce account with no `sap_customer_number_c` is **merged** into the customer whose Salesforce account has the same *normalized name*: lower case, punctuation removed, and the legal suffixes `gmbh`, `ag`, `inc`, `llc`, `ltd`, `corp`, `bv`, `sa`, `srl` and `ab` removed. Its tickets and opportunities then count toward that customer.
- A Salesforce account with no SAP number and no name match is a **prospect** and is not a customer.
- Zendesk tickets belong to the Salesforce account named by `zendesk.organization.external_id` (the Salesforce account ID) on the ticket's `organization_id`.

### Strategic account (history mode, trap T5)

- A customer is **strategic** when its SAP-mapped Salesforce account's `tier_c = 'Strategic'` **at the end of the as-of date**: the history-mode row where `_fivetran_start <= 6 Nov 2026 23:59:59 <= _fivetran_end` (today, that is the row with `_fivetran_active = true`). The look-alike duplicate's own tier is ignored.
- When a metric is broken down *by tier*, each delivery uses the tier in force at the end of that delivery's requested delivery date, not today's tier.

### Delivery and on time (traps T1 and T2)

- A **delivery** is a row in `LIKP` (key `LIKP.VBELN`), linked to its sales order through `LIPS.VGBEL` → `VBAK.VBELN`.
- **Cancelled** deliveries and orders are deleted at the source and land with `_fivetran_deleted = true`. They are **excluded** from every metric.
- The **requested delivery date** is the order's `VBAK.VDATU`.
- The **actual delivery time** is the `event_at` of the `delivered` event in `carrier_pg.shipment_event`, for the shipment whose `carrier_pg.shipment.delivery_number` equals `LIKP.VBELN`.
- A delivery is **on time** when it has a delivered event and the date of `delivered_at` is **on or before** `VBAK.VDATU`. A delivery with no delivered event by its requested date is late. The planned goods-issue date (`LIKP.WADAT`) and the actual goods-issue date (`LIKP.WADAT_IST`) are *not* delivery dates.
- **On-time delivery rate (90 days)**, per customer: on-time deliveries divided by all non-cancelled deliveries whose requested delivery date (`VBAK.VDATU`) falls in the last 90 days.

> Refinement from the backlog draft: the window is set on the requested delivery date rather than the ship date, so that a delivery that never shipped still counts against the rate instead of silently dropping out.

### Net revenue (trap T3)

- **Invoices** are `VBRK` rows with `FKART = 'F2'`; **credit memos** have `FKART = 'G2'`. Amounts are `VBRK.NETWR` in currency `VBRK.WAERK`, both stored as positive numbers.
- **Net revenue** = invoices minus credit memos, each converted to **USD** at the monthly average rate (`TCURR.KURST = 'M'`, `FCURR = 'EUR'`, `TCURR = 'USD'`) for the month of the billing date `VBRK.FKDAT`. `TCURR.GDATU` is stored inverted (`99999999 − YYYYMMDD`) and gives the first day of the month the rate applies to.
- **Region** comes from the SAP customer's country `KNA1.LAND1`: US, CA and MX are **North America**; every other country is **EMEA**. Quarters are calendar quarters of `VBRK.FKDAT`.

### Shipping-related support ticket

- A ticket is **shipping-related** when it has any of the tags `shipping`, `delivery`, `late_delivery` or `logistics` in `zendesk.ticket_tag`, **or** its subject contains `late`, `delay`, `shipment`, `delivery` or `tracking` (case-insensitive).
- A ticket is **open** when `zendesk.ticket.status` is `new`, `open`, `pending` or `hold`.

### Renewal due

- An **open renewal due in 120 days** is a Salesforce opportunity with `type = 'Renewal'`, `is_closed = false` and `close_date` from the as-of date up to 120 days after it.

### At risk

A customer is **at risk** when all of the following are true:

1. it is strategic (as of the as-of date);
2. its on-time delivery rate (90 days) is **below 85%**; and
3. it has **2 or more open shipping-related tickets**, **or** an open renewal due in 120 days.

The **drivers** for an at-risk account are its on-time rate, its number of late deliveries, its open shipping-related tickets and its renewal close date.

### Recommended next step

The answer pairs each at-risk account with one next step, from a fixed playbook:

| Situation | Next step for the account team |
|---|---|
| Renewal due in 120 days | Executive call before the renewal, with a delivery recovery plan |
| 3 or more open shipping tickets | Escalate the open tickets with logistics and give the customer a named contact |
| Otherwise | Share the late-delivery list with the customer and agree new delivery dates |

## The traps

The data contains six deliberate traps. Each is a real problem data teams meet, and each is something a naive agent gets wrong.

| Trap | What is planted | What a naive agent does | What fixes it |
|---|---|---|---|
| **T1** Deleted records | About 4% of deliveries cancelled, kept as soft-deleted rows | Counts cancelled deliveries as late | Fivetran's `_fivetran_deleted` flag; staging filter in dbt |
| **T2** Wrong date | Late deliveries whose planned goods-issue date is on time | Uses `WADAT`/`WADAT_IST` as the delivery date | The carrier `delivered_at`, joined in dbt |
| **T3** Mixed currency | About 35% of orders and invoices in EUR | Sums EUR and USD together | `TCURR` conversion in dbt |
| **T4** Duplicate account | "Halbrook Fluid Systems" and "Halbrook Fluid Systems GmbH"; only one mapped to SAP | Counts two strategic accounts, or misses the duplicate's tickets | Identity resolution in dbt |
| **T5** Tier history | Three accounts promoted to Strategic and one demoted, midway through the 90-day window | Reads every history row, so includes the demoted account | History mode plus an as-of join |
| **T6** Stale data | Zendesk's last sync held two days behind (scenario flag, on by default) | Answers as if the data were current | The freshness tool; the agent states the gap |

## The six golden questions

The generator (CL-03) computes the expected answer to each one. The evaluation (CL-11) scores both agents against them.

| # | Question | Answer type | Traps that change the answer if ignored |
|---|---|---|---|
| G1 | Which of our strategic accounts are at risk because of late shipments, and what should the account teams do this week? | List of accounts, each with drivers and a next step | T1, T2, T4, T5 |
| G2 | What is the 90-day on-time delivery rate across all of our strategic accounts? | Number (percentage, one decimal) | T1, T2, T5 |
| G3 | What was our net revenue in USD in EMEA for Q3 2026? | Number (USD, rounded to the dollar) | T3 (and credit memos) |
| G4 | How many strategic accounts do we have today? | Number | T4, T5 |
| G5 | Is our support ticket data current enough to act on today? | Yes or no, with the age of the last sync | T6 |
| G6 | How many open shipping-related support tickets do our strategic accounts have in total? | Number | T4, T5 (and inconsistent tags) |

Every question changes when at least one specific trap is ignored; CL-03's tests prove each mapping by computing the naive answer and checking that it differs from the truth.

## How the story is framed: discovery first

The demo is a proof of value, not a feature tour. Before it, a sales engineer would ask Northstar three questions, and the demo answers them back:

1. **Sources:** "Where does the data behind this question live today, and who owns each system?" (SAP, Salesforce, Zendesk and the carrier database, with four different owners.)
2. **AI plans:** "What do you want agents to do with this data in the next two quarters, and who will trust their answers?" (Operations wants an agent the COO can ask directly.)
3. **Trust today:** "When two reports disagree today, how do you find out which one is right?" (They can't, quickly; definitions live in people's heads.)

## The five acts

| Act | Title | Capability shown | Specialty |
|---|---|---|---|
| 1 | The confident wrong answer | An agent with raw SQL only | Why AI changes data requirements |
| 2 | Move | Fivetran Connector SDK: incremental sync, soft deletes, history mode, schema change, sync log and MAR | Database and application replication, SAP |
| 3 | Transform and Trust | dbt models, tests, contracts, lineage; MetricFlow metrics; Iceberg read by two engines | Transformation, lakehouse and open table formats |
| 4 | Context | The same agent through the dbt MCP server, a metrics tool and a freshness tool; scored side by side | AI and context engineering, MCP, semantic layers |
| 5 | Activate | Reverse ETL to a mock Salesforce, plus Slack | Activation and reverse ETL |

The scripted words for each act are in the [talk track](talk-track.md).

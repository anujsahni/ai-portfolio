# Northstar proof-of-value scorecard

_Generated from the live demo by `python -m contextloop.ui.scorecard_data`. Static fallback for the app's scorecard page. Synthetic data._

## Success criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| SC1 | The agent answers the COO's headline question correctly, with the exact at-risk accounts | **Pass**: exact list of 9 accounts | Act 4 |
| SC2 | On the six golden questions, the governed agent scores at least 5 of 6 and beats the raw-data baseline | **Pass**: governed 6/6 vs naive 2.7/6 (average of 3 runs, evaluation report) | Act 4 |
| SC3 | SAP deliveries replicate incrementally, keeping cancelled documents as soft deletes | **Pass**: 10 incremental syncs, 310 soft-deleted deliveries kept | Act 2 |
| SC4 | A new SAP column flows through with no connector code change | **Pass**: LIKP.ZZ_CARRIER_ID landed | Act 2 |
| SC5 | One definition of on-time delivery, used by BI and AI alike, tested on every build | **Pass**: on_time_delivery_rate defined once; 89 nodes built and tested, 0 failing | Act 3 |
| SC6 | The agent knows when data is stale and says so | **Pass**: the answer flags Zendesk as two days old | Act 4 |
| SC7 | Trusted tables are stored once in an open format and read by more than one engine | **Pass**: Iceberg table with 19 snapshots; DuckDB and Trino return identical rows (make lakehouse) | Act 3 |
| SC8 | The answer reaches the CRM the account teams use, with an audit trail | **Pass**: 9 audited CRM writes from marts.account_risk | Act 5 |

## Cost estimate (MAR, monthly average Aug to Oct 2026)

| Connection | Estimated MAR |
|---|---|
| sap_s4 | 6,013 |
| carrier_pg | 3,066 |
| zendesk | 175 |
| salesforce | 13 |

- MAR is ESTIMATED here as distinct primary keys changed per table per month, from the sources' change timestamps.
- Fivetran's billing rules differ (for example, initial syncs and some tables are free); real pricing comes from fivetran.com/pricing or the account team.
- Volumes are synthetic and roughly a tenth of a real mid-market manufacturer's; scale before quoting.

## Time to value

- Foundation (Docker: 1 day(s)
- Move (SAP and Postgres connectors: 1 day(s)
- Transform and Trust (dbt: 1 day(s)
- Context (MCP servers: 1 day(s)
- Experience and Activate (app: 1 day(s)

## Specialist map

| Specialty | Workstream | Found | Open before production |
|---|---|---|---|
| SAP | SAP S/4HANA replication (Act 2) | Cancelled documents and goods-issue dates mislead anyone reading raw tables; history matters for tiers. | Choose native SAP connector vs hybrid deployment; confirm ODP extractors and change volumes. |
| Database and application replication | Carrier Postgres, Salesforce, Zendesk (Act 2) | The actual delivery time lives only in the carrier database; Zendesk freshness drives the ticket signal. | Log-based CDC on the carrier database; sync frequency per source; private networking. |
| Lakehouse and open table formats | Iceberg marts read by two engines (Act 3) | One copy of the trusted marts serves DuckDB and Trino identically. | Managed Data Lake Service destination (S3, ADLS or GCS) and the customer's query engines. |
| Transformation | dbt models, tests, contracts, semantic layer (Act 3) | Each trap needs a named model and a test; contracts stop silent schema drift. | dbt platform jobs and CI; the hosted Semantic Layer; ownership of metric definitions. |
| AI and context engineering | dbt MCP, metrics and freshness tools; evaluation (Act 4) | The same model goes from wrong to right when it gets governed definitions, lineage and freshness. | Golden-question set owned by the business; guardrails on untrusted text; cost per answer. |
| Activation | Reverse ETL to the CRM and Slack (Act 5) | Diff-based syncs from the governed model keep the CRM trustworthy and auditable. | Fivetran Activations to the real Salesforce org; field ownership; AI-drafted text review. |

## Path to production

- [ ] Connectivity and security review (PrivateLink or Private Service Connect, SSH tunnel or hybrid deployment)
- [ ] Fivetran native SAP, PostgreSQL, Salesforce and Zendesk connectors in the customer's account
- [ ] Managed Data Lake Service writing Iceberg to the customer's cloud storage
- [ ] dbt platform with scheduled jobs, CI and the Semantic Layer; dbt MCP server connected to it
- [ ] Fivetran Activations to Salesforce and Slack
- [ ] A business-owned golden-question set and an evaluation in CI before agents reach executives


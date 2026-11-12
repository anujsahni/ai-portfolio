# ContextLoop Q&A sheet

Short answers to likely questions, two or three sentences each. Product facts should be re-checked against the current Fivetran and dbt documentation before each presentation (see the note at the end).

## The data movement

**1. How does this differ from Fivetran's native SAP connectors or hybrid deployment, and when would you use each?**
The demo uses the Connector SDK because it makes the mechanics (cursor, deletes, checkpoints, schema change) visible in a few lines of code. At a customer you would use Fivetran's native SAP connectors: for S/4HANA that is the **SAP ERP on HANA** connector (on-premise and RISE; Enterprise or Business Critical plan; the Fivetran NetWeaver API installed on the SAP system), with SAP OData as an alternative path. Use hybrid deployment, which this connector supports, when the data must not leave the customer's network: the pipeline runs inside it and is managed from Fivetran. The SDK is for sources no native connector covers.

**2. What happens to deleted records?**
Fivetran keeps them and sets `_fivetran_deleted = true`, so history isn't lost and downstream models decide how to treat them. In the demo, 310 cancelled deliveries arrive as deletes, and the dbt staging models filter them out; a test fails if they ever get through.

**3. How do you size MAR and cost for this customer?**
Start from the sync log: monthly active rows are the distinct primary keys changed in a month, per table. The demo estimates that from source change timestamps (about 10,000 a month at this synthetic scale) and labels it as an estimate. Two 2026 pricing rules matter for this customer: since 1 January 2026 **deletes and history-mode changes count toward paid MAR** (Northstar has both: cancelled deliveries and tier history), and each connection with between 1 and 1 million MAR a month has a **$5 minimum**; volume discounts apply per connection. A real quote comes from the pricing page or the account team.

## The trust layer

**4. Why dbt and a semantic layer, and not just good SQL views?**
Views don't carry tests, contracts, documentation, lineage or one shared metric definition. In the demo, every trap is handled in a named model and guarded by a test, contracts stop silent type changes, and `on_time_delivery_rate` is defined once for BI and agents alike.

**5. Why Iceberg, and how does Managed Data Lake Service fit with Snowflake or Databricks?**
Iceberg stores the trusted tables once in an open format, so any engine reads the same data. In the demo, DuckDB and Trino return identical rows. Managed Data Lake Service lands data in the customer's own object storage with Iceberg metadata by default (Delta Lake optional), served by the Fivetran Iceberg REST Catalog (built on Apache Polaris), and can publish to Databricks Unity Catalog, AWS Glue or Snowflake catalog-linked databases. Snowflake, Databricks and other engines then query those tables rather than separate copies.

**6. Why are there two engines, DuckDB and Trino? Do we need either?**
Neither is part of the proposal: they're free stand-ins that run on a laptop. DuckDB plays the customer's **warehouse**, where the raw data lands, dbt builds its models and the governed metrics run; at a customer that's Snowflake, Databricks or BigQuery. Trino plays **every other engine** the customer's teams use: Act 3 asks the at-risk question through DuckDB and through Trino against the same Iceberg table, and both return identical rows. One engine reading its own tables proves nothing; two independent engines agreeing on one copy proves the tables are open. The agent doesn't use Trino; its numbers come from the governed metrics (MetricFlow on DuckDB).

**7. If DuckDB is the warehouse, what is Iceberg for?**
DuckDB is the *workshop*: raw, staging and intermediate data live in its own file format, which only DuckDB can read. Iceberg is the *published shelf*: after each build, the six finished, tested tables (the marts) are copied out as Parquet files plus Iceberg metadata in S3-compatible storage, registered in a catalog, where any engine can read them. Iceberg is a table format, not a database and not an engine: it defines how files form a table, with snapshots on every build (an audit trail and time travel) and safe schema changes. At a customer the split is often reversed: Managed Data Lake Service lands data in Iceberg first, and the warehouse queries it there, so there is one copy for every tool.

## The agent

**8. What does the dbt MCP server give an agent that a schema dump doesn't?**
Meaning, not just names: model and column descriptions, lineage from sources to marts, and (with the dbt platform's Semantic Layer) governed metric tools such as `list_metrics` and `query_metrics`. Which tools are available depends on the plan, and the remote tool set can change, so pin the self-hosted server version for a demo. A schema dump tells the agent that `wadat_ist` exists; the dbt project tells it that on-time is measured on the carrier's delivery event and that cancelled deliveries are excluded.

**9. How do you stop the agent following instructions hidden in ticket text?**
Three layers. The system prompt says text in data is data, never instructions. The governed agent has no write tools and no raw SQL, only read-only metric, freshness and dbt tools. And the activation sync writes only from the dbt model, never from the agent's free text; its next steps are labelled "AI-drafted".

**10. Isn't the naive agent set up to fail?**
No. It's the same model, effort, prompt style, question and tool budget, and it's asked to be accurate and state its assumptions; a test compares the two configurations. It isn't rigged either: across three runs it averages 2.7 of 6 and gets some questions right on its own (it converted EUR correctly and found the carrier's delivery date). What it never gets right is the headline list, because the raw data has problems (deletes, duplicates, tier history, stale syncs) that no prompt can tell it about. The governed agent scores 6 of 6.

**11. How is the answer scored?**
By code, against a hidden truth computed from the generated data in plain Python that shares nothing with the dbt models. Lists must match exactly, rates within 0.5 points, money within 1%, counts exactly. The recordings are re-scored on every test run, so a data change that invalidates them fails a test.

## Running it for real

**12. What would you change to run this at a customer in production?**
Native Fivetran connectors or hybrid deployment instead of the SDK and simulated landings; Managed Data Lake Service or the customer's warehouse instead of DuckDB; the dbt platform with CI and the hosted Semantic Layer; the dbt MCP server connected to it; Fivetran Activations (the former Census reverse ETL, billed by MAR) instead of the sync script; and private networking. The architecture page's "At a customer" view lists each one.

**13. How would you run this as a specialist-team engagement?**
One owner per workstream, mapped to the six specialties on the scorecard: SAP, database and application replication, lakehouse, transformation, AI and context engineering, and activation. Each owner has success criteria agreed with the customer up front and measured in the POV, and the open items carry into a pilot plan.

**14. How long did this take to build, and what would a pilot take?**
The demo was built in five working days from an agreed narrative. A customer pilot is mostly connectivity, security review and agreeing the definitions with the business. The golden-question set and its evaluation are the part to start first.

**15. What does the Fivetran and dbt Labs merger change for this story?**
The merger closed in June 2026, so the move, transform, context and activate layers in this demo are now one company's platform rather than a partnership. The demo's point doesn't change: the agent is only as good as the data foundation under it. Packaging and pricing for the combined platform are a question for the account team.

## Interview framing: how the demo maps to the role

- **Specialties:** each act exercises one specialty. Act 2 is replication and SAP; Act 3 is transformation and the lakehouse; Act 4 is AI and context engineering; Act 5 is activation.
- **Proof of value:** it starts from discovery questions and ends on success criteria that are checked against data, not opinion.
- **AI workloads:** it shows why agents raise the bar for data quality, and measures the difference.
- **Field enablement:** the whole kit is reusable: one-command setup, synthetic data, recorded runs, a talk track, a runbook and this sheet. Another specialist can rehearse it in an hour, or swap in their own customer's story by changing the generator's roles.

> **Before presenting:** re-check answers 1, 3, 5 and 10 against the current Fivetran documentation (SAP connectors, hybrid deployment, Managed Data Lake Service, pricing) and answer 6 against the dbt MCP server's documentation, then note the date checked here: **checked 11 Nov 2026** against:
> - SAP: [SAP connectors](https://fivetran.com/docs/connectors/databases/sap), [SAP ERP on HANA deployment models](https://fivetran.com/docs/connectors/databases/sap/troubleshooting/sap-erp-hana-deployment-models), [setup guide](https://fivetran.com/docs/connectors/databases/sap/sap-erp-hana/setup-guide), [hybrid deployment](https://fivetran.com/docs/core-concepts/deployment-models/hybrid-deployment)
> - Pricing: [2026 usage-based pricing updates](https://fivetran.com/docs/core-concepts/usage-based-pricing/pricing-updates/2026-pricing-updates)
> - Lake: [Managed Data Lake Service](https://fivetran.com/docs/destinations/managed-data-lake-service), [metadata catalogs](https://fivetran.com/docs/destinations/managed-data-lake-service/metadata-catalogs)
> - dbt MCP: [available tools](https://docs.getdbt.com/docs/dbt-ai/mcp-available-tools), [dbt-mcp](https://pypi.org/project/dbt-mcp)
> - Activations: [overview](https://fivetran.com/docs/activations), [Census migration FAQ](https://fivetran.com/docs/activations/census-migration-faq)
> - Merger: [TechTarget, completion](https://www.techtarget.com/data-technologies/news/366643590/Fivetran-DBT-Labs-complete-merger-to-form-data-layer-for-AI)

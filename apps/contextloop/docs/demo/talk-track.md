# ContextLoop talk track

The scripted path through the demo, in two lengths. The story, definitions and traps are in the [narrative](narrative.md). Timings are targets; rehearsals (CL-16) record the actual times.

## At a glance

| Segment | 10-minute version | 20-minute version |
|---|---|---|
| Opening and discovery | 0:45 | 1:30 |
| Act 1 · The confident wrong answer | 1:30 | 3:00 |
| Act 2 · Move | 1:45 | 3:30 |
| Act 3 · Transform and Trust | 2:00 | 4:00 |
| Act 4 · Context | 2:15 | 4:30 |
| Act 5 · Activate | 1:00 | 2:00 |
| Proof-of-value scorecard and close | 0:45 | 1:30 |
| **Total** | **10:00** | **20:00** |

Each act below lists what is on screen, the one sentence to say, the one thing the audience should remember, and the capability and specialty it shows. The 20-minute version adds the **deep dive** under each act.

---

## Opening and discovery (0:45 · 1:30)

- **On screen:** the app's home page: Northstar Industrial, four source systems, the COO's question.
- **Say:** "Northstar's COO wants to ask an agent which strategic accounts are at risk from late shipments. Before we built anything, we asked three questions: where the data lives, what they want agents to do, and how they know today which number is right."
- **Remember:** this is a proof of value against Northstar's own success criteria, not a tour.
- **Deep dive (20 min):** walk the three discovery answers, and show the success criteria that the scorecard will check at the end.

## Act 1 · The confident wrong answer (1:30 · 3:00)

- **On screen:** the naive agent's answer to the headline question, then the "what went wrong" panel listing each mistake and the trap behind it.
- **Say:** "Same model we'll use later, with SQL access to the raw tables. It's fluent, precise and wrong, and nothing in the answer tells you so."
- **Remember:** a better prompt doesn't fix this; the model can't know what "on time" or "strategic" means at Northstar.
- **Capability · specialty:** an agent on raw data · why AI changes data requirements.
- **Deep dive (20 min):** open two mistakes in detail: the cancelled deliveries it counted as late (T1), and the planned ship date it used instead of the carrier's delivery time (T2).

## Act 2 · Move (1:45 · 3:30)

- **On screen:** the sync log (four connectors, rows changed, freshness, estimated MAR), then a live incremental sync of the SAP connector.
- **Say:** "Fivetran lands all four systems the same way: incremental, with deletes kept as flags rather than lost, and history kept for the fields that change."
- **Remember:** reliable movement is what makes the raw layer trustworthy, and it is the part teams underestimate.
- **Capability · specialty:** Connector SDK incremental sync, soft deletes, history mode, sync log and MAR · database and application replication, SAP.
- **Deep dive (20 min):** show the connector's `update()` function and its saved state; land batch 2 and watch the new `ZZ_CARRIER_ID` column appear with no code change; note that at a customer this is Fivetran's native SAP connectors or hybrid deployment.

## Act 3 · Transform and Trust (2:00 · 4:00)

- **On screen:** dbt lineage from the four sources to the marts, the test results, and the `on_time_delivery_rate` metric definition; then the same Iceberg table read by DuckDB and by Trino.
- **Say:** "dbt turns the raw tables into one tested model, and the semantic layer defines each number once. The trusted tables are stored as Iceberg, so any engine reads the same data."
- **Remember:** definitions live in code, are tested on every build, and break loudly when an assumption changes.
- **Capability · specialty:** dbt models, tests, contracts, lineage, MetricFlow, Iceberg · transformation, lakehouse and open table formats.
- **Deep dive (20 min):** run the break-it scene (`make break TRAP=T1`) so a named test fails, then restore it; show the snapshot history of an Iceberg table.

## Act 4 · Context (2:15 · 4:30)

- **On screen:** the governed agent's answer next to Act 1's, with the metric definitions it cited, the lineage it fetched, the freshness badge, and the score of each agent against the golden questions.
- **Say:** "Same model, same question. This time it works through the dbt MCP server, a metrics tool and a freshness tool, so it uses Northstar's definitions and tells you how fresh the data is."
- **Remember:** context engineering is data engineering: the agent is only as good as the definitions and data it can reach.
- **Capability · specialty:** dbt MCP server, governed metrics through MCP, freshness · AI and context engineering, MCP, semantic layers.
- **Deep dive (20 min):** step through the agent's tool calls one by one, and show it stating that Zendesk is two days behind (T6).

## Act 5 · Activate (1:00 · 2:00)

- **On screen:** the at-risk list synced to the mock Salesforce (inserts, updates, unchanged), the audit log, and the Slack message.
- **Say:** "An answer on a screen changes nothing. Here the at-risk list and next steps go back into the CRM and the channel where the account teams already work."
- **Remember:** the loop closes when the insight reaches the people who act on it.
- **Capability · specialty:** reverse ETL and activation · activation and reverse ETL.
- **Deep dive (20 min):** re-run the sync to show it is diff-based (nothing changes the second time), and name the production path: Fivetran Activations.

## Proof-of-value scorecard and close (0:45 · 1:30)

- **On screen:** Northstar's success criteria with pass or fail, time to value, the MAR-based cost estimate, and which specialist owns each workstream.
- **Say:** "Every success criterion we agreed at the start is checked against data, and here is what it would take to run this for real."
- **Remember:** the next step is a scoped pilot with named owners, not another demo.
- **Deep dive (20 min):** map each component to its production equivalent (Fivetran native connectors and Managed Data Lake Service, dbt platform and the hosted Semantic Layer, Fivetran Activations).

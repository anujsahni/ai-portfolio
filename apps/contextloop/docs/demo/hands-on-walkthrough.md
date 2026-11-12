# ContextLoop hands-on walkthrough

This is a script to type along with. It shows where the data goes, where Claude is called, and where MCP is used. Each step gives a command to run and what to look for. The talk track covers what to say; this covers how the demo works underneath.

Run every command from `apps/contextloop/`, with the stack up (`make demo`).

---

## 1. The whole flow on one page

```
 SOURCE SYSTEMS              MOVE (Act 2)               TRANSFORM + TRUST (Act 3)            SERVE
 ─────────────              ────────────               ─────────────────────────            ─────
 SAP S/4 (files)  ──┐
 Carrier Postgres ──┤  Connector SDK connectors   raw schemas          dbt build              warehouse.db
 Salesforce (sim) ──┼─► + simulated SaaS landing ─► sap_s4.*      ─►  staging → intermediate ─► └► serving.db (read-only copy)
 Zendesk (sim)    ──┘    + fivetran_log.sync_log    carrier_pg.*       → marts (tested)              + Iceberg on RustFS
                                                    salesforce.*       + semantic layer               (DuckDB and Trino)
                                                    zendesk.*            (MetricFlow metrics)

                       ┌────────────────────── AI ONLY HAPPENS HERE ───────────────────────┐
 ACT 1 · naive agent   │  Claude (Haiku 5.5) ──tool: run_sql──► raw schemas only            │
                       │                                         (sap_s4, carrier_pg, ...)  │
 ACT 4 · governed agent│  Claude (Haiku 5.5) ──tools──► MCP bridge ──► dbt-mcp      :8103   │
                       │                                          ├──► mcp-metrics  :8101   │
                       │                                          └──► mcp-freshness:8102   │
                       └────────────────────────────────────────────────────────────────────┘
                                         │ structured answer (submit_answer)
                                         ▼
 ACT 5 · activate      marts.account_risk (dbt) + AI-drafted next steps ──► mock Salesforce + Slack
```

### Where AI is used, and where it isn't

| Piece | Uses Claude? | What it actually is |
|---|---|---|
| Act 2 sync, Act 3 dbt build, Iceberg, Trino | **No** | Python connectors, dbt, DuckDB |
| Act 1 naive agent | **Yes** | Claude with one tool, `run_sql`, over the raw tables |
| Act 1 "what went wrong" panel | No | Rule-based: [explain.py](../../contextloop/agent/explain.py) compares the SQL with the planted traps |
| Act 4 governed agent | **Yes** | The same Claude, model and budgets, with its tools coming from 3 MCP servers |
| Scores (x out of 6) | No | Rule-based: [score.py](../../contextloop/eval/score.py) checks the answer against hidden truth |
| Act 5 at-risk list and drivers | No | Read from `marts.account_risk` |
| Act 5 "next step" text | Indirectly | Taken from the governed agent's recorded G1 answer and marked **AI-drafted** |

**Claude is called from one function only:** `run()` in [runner.py](../../contextloop/agent/runner.py). Both agents use it. It is a manual tool-use loop on the Messages API:

```
user question
  → Claude answers with tool_use blocks
  → the loop runs each tool and sends back tool_result blocks
  → repeat (max 15 data tool calls, 300 s)
  → Claude calls submit_answer (a strict JSON schema) → Trace saved
```

**The model** is set by `CONTEXTLOOP_MODEL` in `.env`, read in [agent/config.py](../../contextloop/agent/config.py). It is currently `claude-haiku-5-5`.

**MCP is used only by the governed agent (Act 4).** The three MCP servers run in private containers, so the Messages API's built-in MCP connector can't reach them. [mcp_bridge.py](../../contextloop/agent/mcp_bridge.py) connects with the Python MCP client instead. It lists each server's tools, gives them to Claude as ordinary tool definitions, and sends each `tool_use` to the right server.

---

## 2. Check the model and key (1 min)

```bash
docker compose exec app sh -c 'echo mode=$CONTEXTLOOP_MODE model=$CONTEXTLOOP_MODEL; [ -n "$ANTHROPIC_API_KEY" ] && echo key=set'
docker compose exec app python -c "from contextloop.agent import config; print(config.MODEL)"
```

You should see `claude-haiku-5-5`. If you change `.env`, run `docker compose up -d` so the containers pick it up.

`CONTEXTLOOP_MODE=replay` controls only what the app shows first. **Replay** plays saved traces from `recordings/demo/` and makes no API calls. **Live** calls Claude now. You can switch with the sidebar toggle at any time.

---

## 3. See the data the agents will query (2 min)

The raw tables (what Act 1 sees):

```bash
docker compose run --rm -T --no-deps eval python -c "
from contextloop.agent import naive
print(naive.run_sql('select count(*) n from carrier_pg.shipment_event'))
print(naive.run_sql('select * from marts.fct_delivery limit 1'))   # blocked on purpose
"
```

The second query fails on purpose: the naive agent is limited to the raw schemas.

The source freshness (what feeds the freshness MCP server):

```bash
docker compose run --rm -T --no-deps eval python -c "
from contextloop.mcp_servers.freshness import freshness
for s in freshness()['sources']: print(s['source'].ljust(12), s['age_hours'], 'h  within_window=', s['within_window'])
"
```

`zendesk` is outside its window on purpose: that is trap T6, which the governed agent should report.

---

## 4. Call the MCP servers yourself, without Claude (3 min)

This is the clearest way to see what "context through MCP" means. These are the exact tools Claude gets in Act 4:

```bash
docker compose run --rm -T --no-deps eval python -c "
from contextloop.agent.mcp_bridge import Bridge
b = Bridge(); tools = b.connect()
for t in tools: print(b.tool_origin(t['name']).ljust(14), t['name'])
"
```

Expected:

```
dbt-mcp        dbt_list
dbt-mcp        dbt_get_lineage_dev
dbt-mcp        dbt_get_node_details_dev
mcp-metrics    list_metrics
mcp-metrics    query_metric
mcp-freshness  check_freshness
```

Now ask the metrics server the headline question directly, the way the agent would:

```bash
docker compose run --rm -T --no-deps eval python -c "
from contextloop.agent.mcp_bridge import Bridge
b = Bridge(); b.connect()
r = b.call('query_metric', {'metrics': ['account_risk_flag', 'on_time_delivery_rate'],
          'group_by': ['account__account_name'],
          'where': \"{{ Dimension('account__is_strategic') }} = true\",
          'order_by': ['-account_risk_flag'], 'limit': 10})
for row in r['rows']: print(row)
print(r['compiled_sql'][:600])
"
```

What to notice:
- The definition of "at risk" (`on_time < 0.85 and (tickets >= 2 or renewal due)`) appears in the compiled SQL. It comes from the dbt semantic layer, not from Claude.
- Every number the governed agent reports must come from a call like this one, and the result includes the SQL that produced it.

Try `b.call('list_metrics', {})` and `b.call('dbt_get_lineage_dev', {'unique_id': 'model.contextloop.fct_delivery'})` as well.

---

## 5. Run the two agents live and compare them (5 min, about $0.01 per run on Haiku)

Run the same question through both agents. Each tool call prints as it happens:

```bash
make ask AGENT=naive    Q=G1
make ask AGENT=governed Q=G1
```

Watch the `→` lines:

| Naive (Act 1) | Governed (Act 4) |
|---|---|
| `→ run_sql {"sql": "SELECT ... FROM sap_s4.likp ..."}` repeated | `→ check_freshness`, `→ list_metrics`, `→ query_metric ...`, `→ dbt_get_lineage_dev ...` |
| Guesses what "on time", "strategic" and "late" mean | Uses the definitions returned by `list_metrics` |
| Counts cancelled deliveries, uses the ship date (WADAT), misses the duplicate account | Gets the right accounts, cites lineage, warns that Zendesk is stale |

Reference run (governed, G1, Haiku, 11 Nov 2026): 5 API requests, 52 s, $0.008. The answer flagged the right strategic accounts, gave a playbook next step for each, and added the caveat: *"Zendesk is stale … six flags depend on ticket counts."*

The other golden questions are shorter and good for quick checks:

| ID | Question |
|---|---|
| G1 | Which strategic accounts are at risk because of late shipments, and what should the account teams do this week? |
| G2 | What is the 90-day on-time delivery rate across all strategic accounts? |
| G3 | What was net revenue in USD in EMEA for Q3 2026? |
| G4 | How many strategic accounts do we have today? (answer: 25) |
| G5 | Is our support ticket data current enough to act on today? |
| G6 | How many open shipping-related tickets do strategic accounts have in total? |

Read the two system prompts to see the only thing that differs between the agents:

```bash
docker compose run --rm -T --no-deps eval python -c "from contextloop.agent import governed; print(governed.system_prompt())"
docker compose run --rm -T --no-deps eval python -c "from contextloop.agent import naive; print(naive.system_prompt())"
```

---

## 6. Score them and record replays (10 min)

```bash
make record     # both agents x 6 questions, live; saves recordings/ and reports/ into the repo
make eval       # re-scores the saved recordings with no API calls (when CONTEXTLOOP_MODE=replay)
```

Open `reports/` for the scorecard, and `recordings/demo/governed/G1.json` for a full trace. In the trace:
- `steps[]` lists each tool call, with its input and output.
- `answer` is the structured `submit_answer` payload.
- `usage` gives tokens and cost.
- `model` and `served_by` confirm which model answered.

Replay mode in the app plays exactly these files.

---

## 7. Click through the app with that picture in mind (10 min)

Open http://127.0.0.1:8501 and turn on **Live mode** in the sidebar if you want real calls.

| Act | Click | What is happening underneath |
|---|---|---|
| 1 | Ask the naive agent | `naive.answer()` → `runner.run()` → Claude ↔ `run_sql` on DuckDB raw schemas. The "what went wrong" panel is rule-based. |
| 2 | Run incremental sync | `cli datagen --batch 2` + `cli sync`: connector `update()` runs and the sync log grows. No AI. |
| 3 | Break it, then restore | `cli build --break T1` → a named dbt test fails → rebuild. The DuckDB-vs-Trino button reads the same Iceberg table. No AI. |
| 4 | Ask the governed agent | `governed.answer()` → `Bridge.connect()` (MCP list_tools ×3) → `runner.run()` → each tool call becomes an MCP `call_tool`. The step labels show which server answered. |
| 5 | Sync to Salesforce / Post to Slack | Dry-run diff of `marts.account_risk` against the mock CRM. The next-step text comes from the governed G1 answer. No new AI call. |

---

## 8. One-sentence answers for the room

- **Where's the AI?** One Claude tool loop, used twice: once with raw SQL (Act 1), once with governed MCP tools (Act 4). Same model, same prompt style, same budgets.
- **Where's MCP?** Three servers on the private network: the official dbt MCP server (docs and lineage), a metrics server over MetricFlow (definitions and governed queries), and a freshness server (sync log). A small bridge exposes them to Claude.
- **Why does Act 4 win?** The context is better, not the model: definitions, lineage and freshness come from the data platform, so Claude doesn't have to guess.

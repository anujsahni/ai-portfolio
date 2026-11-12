# CL-10 completion record: governed agent via the dbt MCP, metrics and freshness MCP servers

**Date:** 11 Nov 2026 · **Model:** `claude-haiku-5-5` (set by `CONTEXTLOOP_MODEL` in `.env`), effort high · **Result:** all acceptance criteria met.

## MCP servers and bridge

`make up` starts all three servers healthy on the private network. The bridge (`contextloop/agent/mcp_bridge.py`) lists their tools:

```
dbt-mcp        dbt_list
dbt-mcp        dbt_get_lineage_dev
dbt-mcp        dbt_get_node_details_dev
mcp-metrics    list_metrics
mcp-metrics    query_metric
mcp-freshness  check_freshness
```

## Three live runs per golden question (`CONTEXTLOOP_EVAL_RUNS=3 make record`)

| Question | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| G1 at-risk strategic accounts | ✓ exact 9 | ✓ exact 9 | ✓ exact 9 |
| G2 90-day on-time rate | ✓ 86.1 | ✓ 86.1 | ✓ 86.1 |
| G3 EMEA net revenue Q3 2026 | ✓ | ✓ | ✓ |
| G4 strategic accounts today | ✓ 25 | ✓ 25 | ✓ 25 |
| G5 support data current? | ✓ no | ✓ no | ✓ no |
| G6 open shipping tickets | ✓ 28 | ✓ 28 | ✓ 28 |
| **Score** | **6/6** | **6/6** | **6/6** |

The headline G1 answer used 5–6 tool calls in about 45 s and cost about $0.008 per run. The tool sequence was: `list_metrics` → `check_freshness` → `query_metric` ×2 → `dbt_get_lineage_dev` ×1–2.

## The other criteria

- **Numbers come from `query_metric`.** The `test_governed_numbers_come_from_query_metric` test passes. Each on-time rate in the answer matches a `query_metric` result; the model may round, for example 0.615 for 0.6154.
- **T6 (stale Zendesk).** All three G1 runs say Zendesk is outside its 24-hour window: last sync 9 Nov, and the 11 Nov attempt failed on a rate limit. The answers say ticket counts may be understated and name the flags that depend on them. The run with Zendesk current (`recordings/demo/governed/G1-t6off.json`) is also correct and doesn't raise the staleness caveat.
- **Definitions and lineage.** Every G1 answer gives the `list_metrics` definition of all 6 metrics it used. Its lineage runs from `carrier_pg.shipment_event` through `fct_delivery` to `on_time_delivery_rate`.
- **Same setup as the naive agent.** `test_agents.py` checks that both agents share one model, effort, token limit, tool budget (15), time limit and base prompt. Only the tools differ.

## Changes made while closing the story

- **Tool budget raised from 8 to 15 calls, for both agents.** On Haiku, the naive agent spent 8 calls exploring and gave up instead of answering. The governed agent still uses 2–6 calls.
- **Answer repair in `runner.py`.** Haiku sometimes put fields such as `at_risk_accounts` inside `answer_summary` as `<parameter name="…">` markup (5 of 18 naive runs, no governed runs). The runner now recovers empty fields from that markup and sets `answer_repaired` on the trace. The existing recordings were repaired the same way and re-scored.

Report: [`reports/eval-2026-11-11.md`](../../../reports/eval-2026-11-11.md).

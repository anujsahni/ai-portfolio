"""Act 4: the governed agent. The same model, prompt style and budgets as the naive agent, but its tools come from three MCP
servers: the dbt MCP server (models, docs, lineage), the metrics server (governed metric definitions and queries) and the
freshness server (sync timestamps). It has no raw SQL tool.
"""
from __future__ import annotations

from contextloop.agent import config as cfg
from contextloop.agent import runner
from contextloop.agent.mcp_bridge import Bridge

GOVERNED_CONTEXT = """
## Your data and tools

You do not query raw tables. You work through Northstar's governed data foundation:
- Metrics tools (list_metrics, query_metric): the business definitions Northstar has agreed, computed from tested dbt models.
  Read the definitions with list_metrics before you query, and use the metrics' own rules rather than inventing new ones.
  At-risk strategic accounts are defined by the metric account_risk_flag (filter strategic accounts with the dimension
  account__is_strategic); report each account's drivers from on_time_delivery_rate, late_deliveries, open_shipping_tickets
  and renewals_due_120d. For a breakdown by tier, use delivery__tier_at_delivery.
- Freshness tool (check_freshness): when each source last synced. Check it before you answer. If a source is outside its
  window, say so in the summary and caveats, and say which parts of the answer depend on it.
- dbt tools (dbt_list, dbt_get_node_details_dev, dbt_get_lineage_dev): the models behind the metrics, their documentation
  and lineage. Use lineage to say where a number came from (for on_time_delivery_rate, model.contextloop.fct_delivery).

Every number in your answer must come from a query_metric result. In metrics_used, give each metric's definition as
list_metrics states it. In lineage, list the path from source tables to models to the metric.

Recommended next step for each at-risk account (Northstar's playbook): a renewal due within 120 days -> "Executive call
before the renewal, with a delivery recovery plan"; otherwise 3 or more open shipping tickets -> "Escalate the open tickets
with logistics and give the customer a named contact"; otherwise -> "Share the late-delivery list with the customer and
agree new delivery dates".
"""


def system_prompt() -> str:
    return cfg.BASE_SYSTEM + GOVERNED_CONTEXT


def answer(question_id: str, question: str, bridge: Bridge | None = None, **kw) -> runner.Trace:
    bridge = bridge or Bridge()
    if not bridge.tools:
        bridge.connect()
    return runner.run("governed", question_id, question, system_prompt(), bridge.tools, bridge.call, **kw)

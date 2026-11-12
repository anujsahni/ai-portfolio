"""One-line, plain-English descriptions of an agent's tool calls, for the step list in Acts 1 and 4.

For `run_sql` the description is read from the SQL itself (which raw tables it touches and what it does with them), so it
works for old recordings too. If the agent stated a purpose for the query, that is shown alongside.
"""
from __future__ import annotations

import re

TABLES = {
    "sap_s4.vbak": "SAP sales orders", "sap_s4.vbap": "SAP sales order items", "sap_s4.likp": "SAP deliveries",
    "sap_s4.lips": "SAP delivery items", "sap_s4.vbrk": "SAP billing documents", "sap_s4.vbrp": "SAP billing items",
    "sap_s4.kna_1": "SAP customers", "sap_s4.tcurr": "SAP exchange rates",
    "carrier_pg.shipment": "carrier shipments", "carrier_pg.shipment_event": "carrier tracking events",
    "salesforce.account": "Salesforce accounts", "salesforce.opportunity": "Salesforce opportunities",
    "salesforce.user": "Salesforce users",
    "zendesk.ticket": "Zendesk tickets", "zendesk.ticket_tag": "Zendesk ticket tags", "zendesk.organization": "Zendesk organizations",
}
TOOLS = {
    "list_metrics": "Reads the governed metric definitions and the dimensions available",
    "query_metric": "Queries governed metrics",
    "check_freshness": "Checks when each source last synced and whether it is inside its window",
    "dbt_list": "Lists the dbt models and sources",
    "dbt_get_lineage_dev": "Fetches dbt lineage",
    "dbt_get_node_details_dev": "Reads a dbt model's documentation and columns",
}
_TABLE_RE = re.compile(r"\b(sap_s4|carrier_pg|salesforce|zendesk)\s*\.\s*([a-z_0-9]+)", re.I)


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _strip_literals(sql: str) -> str:
    return re.sub(r"'(?:[^']|'')*'", "''", re.sub(r"--[^\n]*", "", sql))


def describe_sql(sql: str, out_columns: list[str] | None = None) -> str:
    """What a SELECT does, e.g. 'Counts Salesforce accounts, grouped by tier_c'."""
    s = _strip_literals(sql)
    low = s.lower()
    seen: list[str] = []
    for schema, table in _TABLE_RE.findall(s):
        name = TABLES.get(f"{schema.lower()}.{table.lower()}", f"{schema}.{table}")
        if name not in seen:
            seen.append(name)
    what = _join(seen) if seen else "the raw data"

    aggregates = bool(re.search(r"\b(count|sum|avg|min|max)\s*\(", low))
    group = re.search(r"\bgroup\s+by\s+(.+?)(?=\border\s+by\b|\bhaving\b|\blimit\b|\)|$)", low, re.S)
    limit = re.search(r"\blimit\s+(\d+)", low)
    if group:
        cols = [c.strip().split(".")[-1] for c in group.group(1).split(",") if c.strip()]
        positions = [int(c) for c in cols if c.isdigit()]
        cols = [c for c in cols if c and not c.isdigit()]
        cols += [out_columns[i - 1] for i in positions if out_columns and 0 < i <= len(out_columns)]
        cols = cols or ["several columns"]
        verb = f"Counts and summarises {what}, grouped by {_join(cols[:3])}"
    elif aggregates:
        verb = f"Computes totals over {what}"
    elif limit:
        verb = f"Looks at a sample of {limit.group(1)} rows from {what}"
    else:
        verb = f"Reads rows from {what}"
    if len(seen) > 1 and not verb.startswith(("Counts", "Computes")):
        verb = verb.replace(f"from {what}", f"joining {what}")
    elif len(seen) > 1:
        verb += " (joined)"

    extras = []
    if "date_diff" in low or "datediff" in low or re.search(r"\b(wadat|lfdat|vdatu)\b.*[<>]", low):
        extras.append("compares dates")
    if re.search(r"\bnot\s+(\w+\.)?(_fivetran_deleted|is_deleted)\b|\b(_fivetran_deleted|is_deleted)\s*(=\s*false|is\s+not\s+true)", low):
        extras.append("excludes deleted rows")
    elif re.search(r"\b_fivetran_deleted\b|\bis_deleted\b", low):
        extras.append("looks at deleted rows")
    return verb + (f"; {', '.join(extras)}" if extras else "")


def describe_error(output: dict) -> str | None:
    err = str(output.get("error") or "")
    if not err:
        return None
    if "Tool budget" in err:
        n = re.search(r"budget of (\d+)", err)
        return f"Not run: the agent had already used its {n.group(1) if n else ''} query budget".replace("  ", " ")
    if "Parser" in err or "syntax" in err.lower():
        return "Failed: SQL syntax error, so the query was wasted"
    if "Only the raw schemas" in err:
        return "Refused: tried to read a table outside the raw schemas"
    if "Binder" in err or "Catalog" in err:
        return "Failed: referenced a column or table that doesn't exist"
    return "Failed: " + err.split("\n", 1)[0][:90]


def describe(step: dict) -> str:
    """The one-line description for a step (a recorded dict or a live Step as a dict)."""
    tool, inp = step.get("tool"), step.get("input") or {}
    if tool == "run_sql":
        text = describe_sql(inp.get("sql", ""), (step.get("output") or {}).get("columns"))
    elif tool == "query_metric":
        text = f"Queries governed metric(s) {', '.join(inp.get('metrics') or [])}"
        if inp.get("group_by"):
            text += f" by {', '.join(inp['group_by'])}"
    elif tool in ("dbt_get_lineage_dev", "dbt_get_node_details_dev") and inp:
        target = next(iter(v for v in inp.values() if isinstance(v, str)), "")
        text = f"{TOOLS[tool]} for {target.split('.')[-1]}" if target else TOOLS[tool]
    else:
        text = TOOLS.get(tool, tool or "")
    return text

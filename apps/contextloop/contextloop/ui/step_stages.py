"""Groups an agent's tool calls into the stages of its reasoning, so the step list in Acts 1 and 4 tells a story.

Both agents answer the same question, but the raw-SQL agent has to work out for itself what the data means, how the systems
connect and what "late" means, while the governed agent reads those as definitions. Each stage is named for what the agent was
trying to work out, and each call is placed by its tool, its stated purpose and its SQL. Works for recordings and live runs.
"""
from __future__ import annotations

import re

# key: (title, the question the agent is asking itself)
STAGES: dict[str, tuple[str, str]] = {
    "definitions": ("Read the agreed definitions", "What do “strategic”, “on time” and “at risk” mean at Northstar?"),
    "explore": ("Explore the raw tables", "What is in these tables, and what do the columns mean?"),
    "connect": ("Connect the systems", "Which SAP, Salesforce and Zendesk records are the same customer, and which version is current?"),
    "late": ("Decide which deliveries count as late", "Which date is the promise, which is the real delivery, and which rows to ignore?"),
    "fresh": ("Check the data is current", "Is every source recent enough to act on?"),
    "compute": ("Work out the answer", "Put it together into the accounts and numbers the question asks for."),
    "lineage": ("Show where the numbers come from", "Which models and sources is the key metric built from?"),
}
# Where each trap in Act 1's "what went wrong" was decided.
TRAP_STAGE = {"T1": "late", "T2": "late", "T3": "compute", "T4": "connect", "T5": "connect", "T6": "fresh", "—": "compute"}
# What the governed agent no longer has to work out, and where the data foundation answers it instead.
HANDLED_BY_FOUNDATION = {
    "explore": "documented, tested dbt models (Act 3)",
    "connect": "identity resolution and tier history in dbt (Acts 2 and 3)",
    "late": "the on_time_delivery_rate definition (Act 3)",
}
TOOL_STAGE = {"list_metrics": "definitions", "dbt_list": "definitions", "dbt_get_node_details_dev": "definitions",
              "check_freshness": "fresh", "query_metric": "compute", "dbt_get_lineage_dev": "lineage"}

_COMPUTE = re.compile(r"\b(per (active )?strategic|per account|compute|for the weakest|sensitivity|final|at[- ]risk list)\b")
_CONNECT = re.compile(r"\b(link|linkage|join|match|map|maps|mapping|relate|duplicate|duplicated|current|historical|history|halbrook)\b")
_LATE = re.compile(r"\b(late|on[- ]time|timing|delivery date|date fields?|planned|requested|goods[- ]issue|wadat|lfdat|vdatu|delivered)\b")


def stage_of(step: dict) -> str:
    tool = step.get("tool")
    if tool in TOOL_STAGE:
        return TOOL_STAGE[tool]
    purpose = str((step.get("input") or {}).get("purpose") or "").lower()
    sql = str((step.get("input") or {}).get("sql") or "").lower()
    if _COMPUTE.search(purpose):
        return "compute"
    if "fresh" in purpose and "group by" not in sql:
        return "fresh"
    if _CONNECT.search(purpose):
        return "connect"
    if _LATE.search(purpose):
        return "late"
    return "explore"


def stages(trace: dict) -> list[dict]:
    """The stages of a run, in the order the agent first entered each: key, title, question, and the numbered steps in it."""
    groups: dict[str, list[tuple[int, dict]]] = {}
    for n, s in enumerate(trace.get("steps", []), start=1):
        groups.setdefault(stage_of(s), []).append((n, s))
    return [{"key": k, "title": STAGES[k][0], "question": STAGES[k][1], "steps": v} for k, v in groups.items()]


def step_numbers(steps: list[tuple[int, dict]]) -> str:
    """'1–3, 9, 11–12' from the numbered steps."""
    nums = [n for n, _ in steps]
    runs, start = [], nums[0]
    for a, b in zip(nums, nums[1:] + [None], strict=False):
        if b != a + 1:
            runs.append(f"{start}" if start == a else f"{start}–{a}")
            start = b
    return ", ".join(runs)

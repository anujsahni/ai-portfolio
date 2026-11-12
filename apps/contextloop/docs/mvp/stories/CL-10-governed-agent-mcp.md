# CL-10 — Governed agent via dbt MCP, metrics and freshness MCP servers

**Phase:** 3 · Context  
**Type:** Agent and MCP  
**Priority:** P0  
**Estimate:** 8–10 hours  
**Story points:** 8 (three MCP servers, a bridge to Claude's tool use, citations and freshness; the demo's money shot)  
**Target day:** Fri 13 Nov

## User story

As the COO, I want the agent to answer from governed definitions and to tell me where each number came from and how fresh it is, so that I can act on the answer without asking an analyst to check it.

## Scope

- **Three MCP servers**, each in its own container on the private network:
  - **`dbt-mcp`**: the dbt MCP server against the mounted project, with the local CLI and project tools (list models, read model details and docs, get lineage, compile SQL). Tools that need the dbt platform are turned off. Spike: confirm its HTTP transport works in a container; if not, start it over stdio inside the `app` container and record the change.
  - **`mcp-metrics`** (Python MCP SDK, streamable HTTP): `list_metrics` (names, descriptions, dimensions) and `query_metric` (metrics, group by, filters, time range), which runs MetricFlow.
  - **`mcp-freshness`**: `check_freshness`, which returns each source's last successful sync, rows changed and whether it is inside the agreed window, from `fivetran_log`.
- **Bridge** (`contextloop/agent/mcp_bridge.py`): connects to the MCP servers with the Python MCP client, lists their tools and passes them to Claude as tool definitions; runs each tool call against the right server and returns the result. (The Messages API's built-in MCP connector needs servers on public URLs; these are private containers, so the bridge connects to them itself.)
- **Governed agent** (`contextloop/agent/governed.py`): the same model, prompt style and tool budget as CL-09. The system prompt tells it to use metrics before raw SQL, to check freshness before answering, and to say so when a source is outside its window. It has no raw SQL tool.
- **Structured answer:** at-risk accounts with drivers and a recommended next step each; the metrics used, with their definitions; lineage (source tables to mart to metric); freshness per source; and stated caveats. Validated against a schema.
- **Untrusted text:** ticket text is data. The prompt tells the agent not to follow instructions found in data, and the answer must cite only metric results.

**Out of scope:** the hosted dbt platform Semantic Layer and discovery APIs; write tools of any kind.

## Acceptance criteria

- [ ] All three MCP servers start healthy under `make up`, and the bridge lists their tools.
- [ ] In live mode the governed agent answers the headline question with **exactly** the hidden-truth at-risk list, across three runs.
- [ ] It scores at least 5 of 6 on the golden set on average across three runs (CL-11 scoring).
- [ ] Every number in the answer comes from a `query_metric` call in the trace (an automated check).
- [ ] With the T6 flag on, the answer says that Zendesk data is two days old and qualifies the ticket-based drivers.
- [ ] The answer cites the definition of every metric it used and includes lineage for `on_time_delivery_rate`.
- [ ] Prompt, model, effort and tool budget match CL-09 except for the tools (a test compares the configuration).

## Dependencies and deliverables

**Dependencies:** CL-07 (metrics), CL-09 (shared config), CL-05 (sync log).  
**Deliverables:** `contextloop/mcp_servers/`, `contextloop/agent/mcp_bridge.py`, `contextloop/agent/governed.py`, Compose services, tests.

## Completion evidence

Traces for three runs of the headline question, the T6 run, and the golden-set scores.

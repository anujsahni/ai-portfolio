"""Bridge between Claude's tool use and the three MCP servers on the private network.

The Messages API's built-in MCP connector needs servers on public URLs; these run in private containers, so the bridge
connects to them itself with the Python MCP client: it lists their tools, hands them to Claude as tool definitions, and runs
each tool call against the right server. dbt-mcp's tool names get a `dbt_` prefix so their origin is obvious in a trace.
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from contextloop.mcp_servers.dbt_mcp_server import ALLOWED_TOOLS as DBT_ALLOWED


@dataclass(frozen=True)
class Server:
    name: str
    url: str
    prefix: str = ""
    allow: tuple[str, ...] | None = None


SERVERS = [
    Server("dbt-mcp", os.environ.get("DBT_MCP_URL", "http://dbt-mcp:8103/mcp"), "dbt_", DBT_ALLOWED),
    Server("mcp-metrics", os.environ.get("METRICS_MCP_URL", "http://mcp-metrics:8101/mcp")),
    Server("mcp-freshness", os.environ.get("FRESHNESS_MCP_URL", "http://mcp-freshness:8102/mcp")),
]


async def _list(server: Server) -> list[dict]:
    async with streamablehttp_client(server.url, timeout=30) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
    out = []
    for t in tools:
        if server.allow is not None and t.name not in server.allow:
            continue
        out.append({"name": server.prefix + t.name, "description": (t.description or "")[:1500],
                    "input_schema": t.inputSchema or {"type": "object", "properties": {}}})
    return out


async def _call(server: Server, tool: str, args: dict) -> dict:
    async with streamablehttp_client(server.url, timeout=180) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool(tool, args)
    if res.structuredContent:
        data = res.structuredContent
        data = data.get("result", data) if isinstance(data, dict) and set(data) == {"result"} else data
    else:
        text = "\n".join(getattr(c, "text", "") for c in res.content)
        try:
            data = json.loads(text)
        except ValueError:
            data = {"text": text}
    if not isinstance(data, dict):
        data = {"result": data}
    if res.isError:
        data = {"error": data.get("text") or json.dumps(data)[:2000]}
    return data


class Bridge:
    """Synchronous facade used by the agent loop."""

    def __init__(self, servers: list[Server] | None = None):
        self.servers = servers or SERVERS
        self._route: dict[str, tuple[Server, str]] = {}
        self.tools: list[dict] = []

    def connect(self) -> list[dict]:
        async def gather():
            return await asyncio.gather(*[_list(s) for s in self.servers])

        self.tools = []
        for server, tools in zip(self.servers, asyncio.run(gather()), strict=True):
            for t in tools:
                self._route[t["name"]] = (server, t["name"][len(server.prefix):])
                self.tools.append(t)
        return self.tools

    def call(self, name: str, args: dict) -> dict:
        if name not in self._route:
            return {"error": f"Unknown tool {name}"}
        server, tool = self._route[name]
        return asyncio.run(_call(server, tool, args))

    def tool_origin(self, name: str) -> str:
        return self._route[name][0].name if name in self._route else "?"

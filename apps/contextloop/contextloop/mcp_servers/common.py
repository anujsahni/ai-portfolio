"""Helpers shared by the ContextLoop MCP servers (streamable HTTP plus a plain /health route)."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse


def make_server(name: str, port: int, instructions: str) -> FastMCP:
    server = FastMCP(name, instructions=instructions, host="0.0.0.0", port=port, stateless_http=True)

    @server.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": name})

    return server

"""Runs the official dbt MCP server (dbt-mcp) against the ContextLoop dbt project, over streamable HTTP on the private network.

Only the local, read-only project tools stay on: `list` (models and sources), `get_node_details_dev` (descriptions, columns,
SQL) and `get_lineage_dev` (upstream and downstream nodes). They read the dbt manifest from the latest `make build`. Tools that
need the dbt platform (Semantic Layer API, Discovery, Admin API, remote SQL) and tools that build, run or change anything are
turned off. Metric queries go through the metrics MCP server instead.
"""
from __future__ import annotations

import asyncio
import os

from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

from contextloop.config import DBT_PROJECT_DIR

PORT = 8103
ALLOWED_TOOLS = ("list", "get_node_details_dev", "get_lineage_dev")
DISABLED = ["SEMANTIC_LAYER", "DISCOVERY", "ADMIN_API", "SQL", "DBT_CODEGEN", "PRODUCT_DOCS", "REMOTE", "LSP",
            "MCP_SERVER_METADATA", "MCP_APPS"]
DISABLED_CLI_TOOLS = "build,run,test,clone,show,compile,docs,parse"


def configure_env() -> None:
    os.environ.update({
        "DBT_PROJECT_DIR": str(DBT_PROJECT_DIR), "DBT_PROFILES_DIR": str(DBT_PROJECT_DIR), "DBT_PATH": "/opt/venv/bin/dbt",
        "DBT_SEND_ANONYMOUS_USAGE_STATS": "false", "DO_NOT_TRACK": "1", "DISABLE_TOOLS": DISABLED_CLI_TOOLS,
        **{f"DISABLE_{d}": "true" for d in DISABLED},
    })


def main() -> None:
    configure_env()
    from dbt_mcp.config.config import load_config
    from dbt_mcp.mcp.server import create_dbt_mcp

    server = asyncio.run(create_dbt_mcp(load_config()))
    server.settings.host = "0.0.0.0"
    server.settings.port = PORT
    # Containers call it by service name (dbt-mcp:8103), so the localhost-only Host check does not apply on this network.
    server.settings.transport_security = TransportSecuritySettings(enable_dns_rebinding_protection=False)

    @server.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "dbt-mcp"})

    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()

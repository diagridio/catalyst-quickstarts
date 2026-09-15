"""The agent's tools.

Separate from main.py so the tests can import the real tool without paying for
main.py's module-level work: importing main.py installs the identity middleware
and compiles the graph.

Two tools, showing the two ways an agent can act for someone. `my_bookings`
runs in-process and is handed the caller's subject as an argument.
`account_summary` leaves the process, and carries the caller in a token Catalyst
mints for that one call.
"""

import os

from diagrid.identity.http import AsyncClient
from langchain_core.tools import tool
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


@tool
def my_bookings(subject: str) -> str:
    """List the bookings that belong to the calling user."""
    return (
        f"Bookings for {subject}: "
        "Grand Ballroom on March 15th, 9AM-1PM; "
        "Rooftop Terrace on March 22nd, 6PM-11PM."
    )




# --- The outbound half: calling a tool as the user -------------------------
# `my_bookings` above runs in-process, so it trusts whatever subject the agent
# hands it. `account_summary` below leaves the process, and that changes the
# trust story: it takes no subject at all. The calling user travels in a token
# Catalyst mints for this one call, so the CRM establishes who is asking for
# itself rather than believing the agent.

MCP_SERVER_NAME = "crm-mcp"

# Catalyst's MCP proxy. Reaching a tool through this path is what attaches the
# calling user; calling the CRM directly would not.
MCP_URL = (
    f"{os.environ.get('DAPR_HTTP_ENDPOINT', 'http://localhost:3500')}"
    f"/v1.0/diagrid/mcp/{MCP_SERVER_NAME}"
)

# Safe to share across requests: the caller is read at send time, so concurrent
# requests each carry their own.
_mcp_client = AsyncClient(headers={"dapr-api-token": os.environ.get("DAPR_API_TOKEN", "")})


@tool
async def account_summary(account_id: str) -> str:
    """Summarise a CRM account. Runs as the user who invoked the agent."""
    async with streamable_http_client(MCP_URL, http_client=_mcp_client) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            answer = await session.call_tool("account_summary", {"account_id": account_id})
            return answer.content[0].text


# The graph gets one tool or the other. The offline issuer has no Catalyst
# project behind it, so it cannot reach an MCP server; `my_bookings` keeps the
# whole walkthrough runnable there.
local_tools = [my_bookings]
local_tools_by_name = {t.name: t for t in local_tools}

catalyst_tools = [account_summary]
catalyst_tools_by_name = {t.name: t for t in catalyst_tools}

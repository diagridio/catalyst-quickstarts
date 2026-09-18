"""The agent's tools.

`my_bookings` runs in-process and is handed the caller's subject as an argument.
`account_summary` leaves the process and takes no subject at all: the caller
travels in a token Catalyst mints for that one call, so the CRM establishes who
is asking for itself rather than believing the agent.
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


MCP_SERVER_NAME = "crm-mcp"

# Catalyst's MCP proxy: reaching the tool through this path is what attaches the
# calling user. Calling the CRM directly would not.
MCP_URL = (
    f"{os.environ.get('DAPR_HTTP_ENDPOINT', 'http://localhost:3500')}"
    f"/v1.0/diagrid/mcp/{MCP_SERVER_NAME}"
)

# Safe to share: the caller is read at send time, so concurrent requests each
# carry their own.
_mcp_client = AsyncClient(headers={"dapr-api-token": os.environ.get("DAPR_API_TOKEN", "")})


@tool
async def account_summary(account_id: str) -> str:
    """Summarise a CRM account. Runs as the user who invoked the agent."""
    async with streamable_http_client(MCP_URL, http_client=_mcp_client) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            answer = await session.call_tool("account_summary", {"account_id": account_id})
            return answer.content[0].text


local_tools = [my_bookings]
local_tools_by_name = {t.name: t for t in local_tools}

catalyst_tools = [account_summary]
catalyst_tools_by_name = {t.name: t for t in catalyst_tools}

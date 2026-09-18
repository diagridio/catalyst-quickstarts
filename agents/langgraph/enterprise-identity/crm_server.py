"""A stand-in CRM, exposed over MCP.

Its one tool reports the identity the call arrived with. The agent sends no
password and no API key, and the CRM still knows whose question it is answering.
"""

import base64
import json
import logging
import os

logging.basicConfig(level=logging.INFO)

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

mcp = FastMCP("crm")

USER_TOKEN_HEADER = "x-diagrid-user-token"


def _calling_user() -> dict:
    """Read the calling user from the token Catalyst minted for this request.

    Catalyst verifies the signature before the request arrives, so this only
    decodes the claims in order to show them.
    """
    raw = get_http_headers().get(USER_TOKEN_HEADER, "")
    token = raw[len("Bearer ") :] if raw.lower().startswith("bearer ") else raw
    if not token:
        return {}
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


@mcp.tool()
def account_summary(account_id: str) -> str:
    """Summarise a CRM account, and report who the CRM is answering."""
    claims = _calling_user()
    user = claims.get("sub", "<no user identity>")
    agent = (claims.get("act") or {}).get("sub", "<no agent>")
    logging.info("account_summary(%s) for user=%s via agent=%s", account_id, user, agent)
    return (
        f"Account {account_id}: 3 open opportunities, $120k pipeline. "
        f"Served to user={user} via agent={agent}."
    )


if __name__ == "__main__":
    try:
        mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("APP_PORT", "8007")))
    except KeyboardInterrupt:
        # fastmcp's runner re-raises it; uvicorn, which the agent uses, does not.
        pass

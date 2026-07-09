import os

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.datastructures import Headers
from starlette.responses import JSONResponse

mcp = FastMCP("mcp-auth-demo", host="0.0.0.0", port=8000, stateless_http=True)

# The header + value Catalyst must present on every request it proxies to this
# server. Configured on the MCPServer resource (see resources/mcp-server.yaml)
# as a static header credential, Catalyst attaches it automatically on every
# call — the mcp-client never sees or sends it.
SHARED_SECRET_HEADER = "x-mcp-shared-secret"
SERVER_SHARED_SECRET = os.getenv("SERVER_SHARED_SECRET", "local-dev-shared-secret")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b


@mcp.tool()
def get_account_balance(account_id: str) -> str:
    """Look up the balance for an account. Treated as a sensitive operation."""
    return f"Account {account_id} balance: $1,204.53"


class RequireUpstreamCredential:
    """Rejects any request that doesn't carry Catalyst's upstream credential.

    Plain ASGI middleware (rather than Starlette's BaseHTTPMiddleware) so it
    doesn't interfere with the streamable-http transport's chunked responses.
    This models the Catalyst-to-upstream-server authentication hop described
    in https://docs.diagrid.io/develop/mcp/mcp-authentication: it is
    independent of, and enforced before, Catalyst's per-tool access policy.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and Headers(scope=scope).get(SHARED_SECRET_HEADER) != SERVER_SHARED_SECRET:
            response = JSONResponse({"error": "unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


if __name__ == "__main__":
    app = RequireUpstreamCredential(mcp.streamable_http_app())
    uvicorn.run(app, host=mcp.settings.host, port=mcp.settings.port)

import logging
import os

import httpx
from fastapi import FastAPI, HTTPException
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

app = FastAPI()
logging.basicConfig(level=logging.INFO)

DAPR_HTTP_ENDPOINT = os.getenv("DAPR_HTTP_ENDPOINT", "http://localhost")
DAPR_API_TOKEN = os.getenv("DAPR_API_TOKEN", "")
MCP_URL = f"{DAPR_HTTP_ENDPOINT}/v1.0/invoke/mcp-server/method/mcp"

# Optional OAuth2 credentials (for Part 2 of the quickstart)
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")


def _fetch_oauth_token():
    """Fetch an OAuth2 token from Auth0 using client credentials grant."""
    if not all([AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET, AUTH0_AUDIENCE]):
        return None
    resp = httpx.post(
        f"https://{AUTH0_DOMAIN}/oauth/token",
        json={
            "grant_type": "client_credentials",
            "client_id": AUTH0_CLIENT_ID,
            "client_secret": AUTH0_CLIENT_SECRET,
            "audience": AUTH0_AUDIENCE,
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


@app.get("/")
async def health():
    return {"status": "healthy", "message": "MCP client is running"}


@app.post("/run")
async def run():
    headers = {}
    if DAPR_API_TOKEN:
        headers["dapr-api-token"] = DAPR_API_TOKEN

    # Attach OAuth2 token if credentials are configured
    token = _fetch_oauth_token()
    if token:
        headers["authorization"] = f"Bearer {token}"
        logging.info("OAuth2 token attached to request")

    results = {"tools": [], "add_result": None, "weather_alert": None, "errors": []}

    try:
        async with streamablehttp_client(
            url=MCP_URL, headers=headers
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Discover available MCP tools
                tools_response = await session.list_tools()
                results["tools"] = [
                    {"name": t.name, "description": t.description}
                    for t in tools_response.tools
                ]
                logging.info("Discovered %d tools", len(results["tools"]))

                # Invoke the 'add' tool
                try:
                    add_response = await session.call_tool("add", {"a": 2, "b": 3})
                    results["add_result"] = add_response.content[0].text
                    logging.info("add(2, 3) = %s", results["add_result"])
                except Exception as e:
                    results["errors"].append({"tool": "add", "error": str(e)})
                    logging.error("add tool failed: %s", e)

                # Invoke the 'get_weather_alert' tool
                try:
                    weather_response = await session.call_tool(
                        "get_weather_alert", {"city": "Chicago"}
                    )
                    results["weather_alert"] = weather_response.content[0].text
                    logging.info("weather alert: %s", results["weather_alert"])
                except Exception as e:
                    results["errors"].append(
                        {"tool": "get_weather_alert", "error": str(e)}
                    )
                    logging.error("get_weather_alert tool failed: %s", e)

    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        logging.error("HTTP error from MCP server: %s", e)
        raise HTTPException(
            status_code=status,
            detail={
                "error": "ACCESS_DENIED",
                "message": f"MCP server returned HTTP {status}",
            },
        )
    except BaseException as e:
        # Unwrap TaskGroup / ExceptionGroup to surface the root cause
        cause = e
        while hasattr(cause, "exceptions") and cause.exceptions:
            cause = cause.exceptions[0]
        if isinstance(cause, httpx.HTTPStatusError):
            status = cause.response.status_code
            logging.error("HTTP error from MCP server: %s", cause)
            raise HTTPException(
                status_code=status,
                detail={
                    "error": "ACCESS_DENIED",
                    "message": f"MCP server returned HTTP {status}",
                },
            )
        logging.error("Failed to connect to MCP server: %s (cause: %s)", e, cause)
        raise HTTPException(
            status_code=502,
            detail={"error": "MCP_CONNECTION_FAILED", "message": str(cause)},
        )

    return results


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("APP_PORT", "5001")))

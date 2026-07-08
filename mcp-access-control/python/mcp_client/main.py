import logging
import os

import httpx
from fastapi import FastAPI
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

app = FastAPI()
logging.basicConfig(level=logging.INFO)

DAPR_HTTP_ENDPOINT = os.getenv("DAPR_HTTP_ENDPOINT", "http://localhost")
DAPR_API_TOKEN = os.getenv("DAPR_API_TOKEN", "")
MCP_URL = f"{DAPR_HTTP_ENDPOINT}/v1.0/diagrid/mcp/mcp-server"


@app.get("/")
async def health():
    return {"status": "healthy", "message": "MCP client is running"}


@app.post("/run")
async def run():
    headers = {}
    if DAPR_API_TOKEN:
        headers["dapr-api-token"] = DAPR_API_TOKEN

    results = {"tools": [], "add_result": None, "weather_alert": None, "errors": []}

    # Discover available MCP tools. Catalyst filters tools/list down to the
    # tools this caller is granted, so this only ever shows authorized tools.
    try:
        logging.info("Discovering tools")
        results["tools"] = await _discover_tools(headers)
        logging.info("Discovered %d tools", len(results["tools"]))
    except BaseException as e:
        results["errors"].append({"step": "list_tools", **_describe_error(e)})
        logging.error("tool discovery failed: %s", _root_cause(e))

    # Each tool runs on its own session so an access-policy denial on one tool
    # (a 403 that tears down that session) does not abort the others. The happy
    # path returns the tool result; an unauthorized tool is reported in errors.
    tool_calls = [
        ("add", {"a": 2, "b": 3}, "add_result"),
        ("get_weather_alert", {"city": "Chicago"}, "weather_alert"),
    ]
    for tool_name, arguments, result_key in tool_calls:
        try:
            results[result_key] = await _call_tool(headers, tool_name, arguments)
            logging.info("%s -> %s", tool_name, results[result_key])
        except BaseException as e:
            results["errors"].append({"tool": tool_name, **_describe_error(e)})
            logging.error("%s tool failed: %s", tool_name, _root_cause(e))

    return results

async def _discover_tools(headers):
    """Open a fresh MCP session and return the list of available tools."""
    async with streamablehttp_client(
        url=MCP_URL,
        headers=headers,
    ) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools_response = await session.list_tools()
            return [
                {"name": t.name, "description": t.description}
                for t in tools_response.tools
            ]


async def _call_tool(headers, tool_name, arguments):
    """Invoke a single MCP tool over its own session.

    Each tool call gets an isolated streamable-http session so an access-policy
    denial on one tool (which tears down the underlying anyio task group) cannot
    abort the other tool calls in the run.
    """
    async with streamablehttp_client(
        url=MCP_URL,
        headers=headers,
    ) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            response = await session.call_tool(tool_name, arguments)
            return response.content[0].text

def _root_cause(exc):
    """Unwrap a TaskGroup/ExceptionGroup down to its underlying root cause.

    The MCP streamable-http transport runs the HTTP exchange inside an anyio
    task group, so an upstream failure (e.g. a 403 from Catalyst's access
    policy) surfaces as a nested ExceptionGroup at the ``async with`` boundary
    rather than at the ``call_tool`` await. Drill through the ``exceptions``
    chain to recover the real error.
    """
    cause = exc
    while hasattr(cause, "exceptions") and cause.exceptions:
        cause = cause.exceptions[0]
    return cause


def _describe_error(exc):
    """Turn an exception into a JSON-serializable error entry.

    Catalyst denies an unauthorized tools/call with HTTP 403 *before* the
    request reaches the MCP server, so the access-control denial arrives as an
    ``httpx.HTTPStatusError`` rather than an in-band JSON-RPC error. Surface the
    HTTP status when we have one so the demo can show the access policy at work.
    """
    cause = _root_cause(exc)
    entry = {"error": str(cause)}
    if isinstance(cause, httpx.HTTPStatusError):
        entry["status_code"] = cause.response.status_code
        if cause.response.status_code == 403:
            entry["reason"] = "ACCESS_DENIED"
    return entry

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("APP_PORT", "5001")))

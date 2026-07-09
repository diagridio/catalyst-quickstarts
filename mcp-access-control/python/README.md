# MCP Access Control Quickstart

This quickstart shows how to secure a [Model Context Protocol (MCP)](https://modelcontextprotocol.io)
server with **Diagrid Catalyst MCP access policies**. Catalyst sits in front of your MCP
server and enforces a per-tool, per-caller allow-list: it filters tool discovery
(`tools/list`) down to the tools each caller is authorized to use, and rejects any
unauthorized tool call (`tools/call`) with `403 Forbidden` before it ever reaches the
server.

To find out more on developing and operating MCPs servers read [MCP on Diagrid Catalyst](read https://docs.diagrid.io/develop/mcp) and [Manage MCP Servers](https://docs.diagrid.io/operate/manage/mcp-servers)

## What This Quickstart Demonstrates

- **MCP behind Catalyst**: An MCP server reached through Catalyst's MCP proxy endpoint
  (`/v1.0/diagrid/mcp/<server>`) instead of directly, so access control is enforced at the
  platform boundary.
- **Deny-by-default access**: A newly created MCP server denies everything until you
  explicitly grant access.
- **Per-tool, per-caller authorization (ACLs)**: Grant a caller App ID access to specific
  tools (e.g. `add` but not `get_weather_alert`) and see `tools/list` filtered and
  unauthorized calls rejected with `403`.
- **Dynamic policy updates**: Change the policy at runtime with
  `diagrid mcpserver access grant|revoke` and observe the effect on the next client run.
- **Tool-gated downstream calls**: The `get_weather_alert` tool calls a downstream
  `weather-service` via Dapr service invocation — denying the tool prevents the caller from
  ever triggering that downstream call.

## Architecture

```
                         MCP access policy
                         enforced here (per-tool, per-caller ACL)
                                    │
                                    ▼
  mcp-client ───HTTP──▶  Catalyst  ───▶  mcp-server ──Dapr service invoke──▶  weather-service
   (caller)            (MCP proxy endpoint +        (tools: add,                        (downstream
                        policy ACL)         get_weather_alert, echo)            dependency)
```

- The **mcp-client** reaches the server only through Catalyst's MCP proxy endpoint. Catalyst applies
  the MCP server's access policy here.
- The **mcp-server** exposes three tools. `get_weather_alert` calls **weather-service** over
  Dapr service invocation; the other tools are self-contained.
- `weather-service` is a plain downstream dependency — this quickstart does not put a
  separate access policy on it. It is only reachable when a caller is allowed to invoke the
  `get_weather_alert` tool.

**Three services:**

| Service | Port | Description |
|---------|------|-------------|
| **mcp-client** | 5001 | Discovers and invokes MCP tools through Catalyst's MCP proxy endpoint |
| **mcp-server** | 8000 | Exposes MCP tools (`add`, `get_weather_alert`, `echo`) via FastMCP |
| **weather-service** | 8001 | Provides mock weather alert data (downstream dependency of `get_weather_alert`) |

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [Python 3.12+](https://www.python.org/downloads/)

## Setup

```bash
cd mcp-access-control/python

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On macOS/Linux

# Install dependencies for all services
pip install -e mcp_client/ -e mcp_server/ -e weather_service/
```

## Running the Quickstart

### 1. Deploy and Run

```bash
diagrid login

diagrid dev run -f mcp-quickstart.yaml --project mcp-access-control --approve --skip-default-resiliency
```

`diagrid dev run` creates the project (if it does not exist), the three App IDs, and the
`mcp-server` MCP server resource, then launches all three services locally. The `mcp-server`
App ID is recognized as an MCP server and exposed to Catalyst through a tunnel. Wait for the
log output to show all three apps started before continuing.

> Leave `diagrid dev run` running in this terminal and use a second terminal for the steps
> below.

### 2. Test All Access Denied (Default)

A newly created MCP server has a deny-all policy: no caller may discover or call any tool.

From the second terminal, trigger the MCP client:

```bash
curl -s -X POST http://localhost:5001/run | python -m json.tool
```

Expected response — no tools listed and every tool call fails (Catalyst tears the session
down before any tool runs):

```json
{
    "tools": [],
    "add_result": null,
    "weather_alert": null,
    "errors": [
        { "step": "list_tools", "error": "Session terminated" },
        { "tool": "add", "error": "Session terminated" },
        { "tool": "get_weather_alert", "error": "Session terminated" }
    ]
}
```

## Testing the MCP Server Access Policy

A Catalyst MCP server access policy is an allow-list that decides which caller App IDs may
use which tools. You change it at runtime — no redeploy.

### Phase 1 — Allow the "add" tool

Grant the `mcp-client` App ID access to just the `add` tool:

```bash
diagrid mcpserver access grant mcp-server --caller mcp-client --allow-tools add --wait
```

Trigger the MCP client again:

```bash
curl -s -X POST http://localhost:5001/run | python -m json.tool
```

Now `add` is discoverable and succeeds, while `get_weather_alert` is rejected with `403`
(it is not in the allow-list), so the downstream `weather-service` is never reached:

```json
{
    "tools": [
        { "name": "add", "description": "Add two numbers together." }
    ],
    "add_result": "5",
    "weather_alert": null,
    "errors": [
        {
            "tool": "get_weather_alert",
            "error": "Client error '403 Forbidden' for url '.../v1.0/diagrid/mcp/mcp-server'",
            "status_code": 403,
            "reason": "ACCESS_DENIED"
        }
    ]
}
```

### Phase 2 — Allow all tools for all callers

Open the server up with a wildcard grant:

```bash
diagrid mcpserver access grant mcp-server --caller "*" --allow-tools "*" --wait
```

Trigger the client again:

```bash
curl -s -X POST http://localhost:5001/run | python -m json.tool
```

All three tools are now discoverable, and both `add` and `get_weather_alert` succeed (the
latter reaching `weather-service` downstream):

```json
{
    "tools": [
        { "name": "add", "description": "Add two numbers together." },
        { "name": "get_weather_alert", "description": "Get a weather alert for a given city." },
        { "name": "echo", "description": "Echo back a message." }
    ],
    "add_result": "5",
    "weather_alert": "Severe thunderstorm warning until 6 PM CDT",
    "errors": []
}
```

## How It Works

### Access Policy

Each MCP server has exactly one **access policy**, created automatically with a deny-all
baseline and lifecycle-locked to the server (you edit its rules; you don't create or delete
it directly). A rule is an allow-list entry: it names one or more **callers** (App IDs, or
`*` for any) and the **tools** they may use (names, or `*` for all). A tool call is allowed
only if some rule matches both the caller and the tool; otherwise it is denied.

Manage the policy with the `diagrid mcpserver access` commands:

```bash
# Grant: add caller→tool allow-list entries
diagrid mcpserver access grant mcp-server --caller mcp-client --allow-tools add,echo

# Revoke specific grants, or a caller's entire rule
diagrid mcpserver access revoke mcp-server --caller mcp-client --allow-tools echo
diagrid mcpserver access revoke mcp-server --caller "*" --all

# Inspect the current policy
diagrid mcpserver access get mcp-server      # one server, full detail
diagrid mcpserver access list                # all servers in the project

# Preview a verdict WITHOUT calling the server or waiting for rollout.
# Evaluated locally with the same OPA policy the data plane enforces.
diagrid mcpserver access test mcp-server --caller mcp-client --tool get_weather_alert
# → ALLOWED: ...  or  DENIED: ...
```

### Enforcement

Callers never talk to the MCP server directly — they go through Catalyst's MCP proxy endpoint
(`{DAPR_HTTP_ENDPOINT}/v1.0/diagrid/mcp/<server>`, see `mcp_client/main.py`). Catalyst
enforces the policy on that hop in two ways:

- **Discovery is filtered.** `tools/list` returns only the tools the calling App ID is
  granted, so an unauthorized tool is invisible rather than merely un-callable.
- **Calls are gated.** An unauthorized `tools/call` is rejected with `403 Forbidden` before
  the request reaches the server. With a full deny-all policy the MCP session itself is
  refused (the client sees `Session terminated`).

The demo client (`mcp_client/main.py`) runs each tool on its own MCP session and reports a
per-tool error, so one tool's `403` doesn't hide the others' results — which is what lets a
single run show `add` succeeding while `get_weather_alert` is denied.

## Files

| File | Purpose |
|------|---------|
| `mcp-quickstart.yaml` | `diagrid dev run` multi-app file (the three services) |
| `resources/mcp-server.yaml` | The `MCPServer` resource (points Catalyst at `localhost:8000/mcp`) |
| `mcp_client/main.py` | FastAPI client that discovers and invokes tools through Catalyst |
| `mcp_server/main.py` | FastMCP server exposing `add`, `get_weather_alert`, `echo` |
| `weather_service/main.py` | Mock downstream weather service |
| `test.rest` | REST-client requests for manual testing |

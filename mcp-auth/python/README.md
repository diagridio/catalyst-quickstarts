# MCP Authentication & Authorization Quickstart

This quickstart shows how to secure a [Model Context Protocol (MCP)](https://modelcontextprotocol.io)
server with **Diagrid Catalyst**, covering the two security layers Catalyst sits in front of
an MCP server with:

- **Authentication** — the credential Catalyst presents to *your* MCP server on every proxied
  request, so the server can verify the call really came through Catalyst.
- **Authorization** — the per-tool, per-caller access policy Catalyst enforces before a
  `tools/call` (or even `tools/list`) ever reaches your server.

These are independent gates. Fixing one does not fix the other, and this quickstart runs them
in that order on purpose: authentication first (nothing works at all until Catalyst can reach
your server), then authorization (the server is reachable, but only approved callers/tools get
through).

## What This Quickstart Demonstrates

- **MCP behind Catalyst**: An MCP server reached through Catalyst's MCP proxy endpoint
  (`/v1.0/diagrid/mcp/<server>`) instead of directly.
- **A local server, exposed via tunnel**: `diagrid dev run --app-id mcp-server --app-port 8000`
  opens a secure tunnel from Catalyst Cloud to your machine — used here for exactly that one
  purpose, not as a process supervisor — so a server running on `localhost:8000` is reachable
  from your hosted Catalyst project, with no public endpoint or inbound firewall rule required.
- **Authenticating Catalyst to your MCP server**: A static shared-secret header, configured on
  the `MCPServer` resource, that your server validates on every request.
- **Deny-by-default authorization**: A newly registered MCP server allows no caller to
  discover or invoke any tool until you explicitly grant access.
- **Per-tool, per-caller access control**: Grant a caller access to one tool (`add`) but not
  another (`get_account_balance`), and see `tools/list` filtered and the unauthorized call
  rejected — live, with no redeploy.

## Architecture

```
                         MCP access policy
                         enforced here (per-tool, per-caller ACL)
                                    │
                                    ▼
  mcp-client ───HTTP──▶  Catalyst  ───HTTP + shared secret──▶  mcp-server
   (caller)            (MCP proxy endpoint +                    (tools: add,
                        policy ACL)                              get_account_balance)
```

- The **mcp-client** reaches the server only through Catalyst's MCP proxy endpoint.
- **Catalyst** authenticates itself to `mcp-server` with a shared-secret header on every
  request, and enforces the per-tool access policy before any request is proxied.
- The **mcp-server** exposes two tools: `add` (harmless) and `get_account_balance` (treated as
  sensitive — the kind of tool you'd want to restrict to specific callers).

**Two services:**

| Service | Port | Description |
|---------|------|-------------|
| **mcp-client** | 5001 | Discovers and invokes MCP tools through Catalyst's MCP proxy endpoint |
| **mcp-server** | 8000 | Exposes MCP tools (`add`, `get_account_balance`) via FastMCP, guarded by a shared-secret check |

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [Python 3.12+](https://www.python.org/downloads/)

## Setup

```bash
cd mcp-auth/python

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On macOS/Linux

# Install dependencies for both services
pip install -e mcp_client/ -e mcp_server/
```

## Running the Quickstart

There's no `diagrid dev run` multi-app file here — every Catalyst resource and every local
process is its own explicit command, so it's clear exactly what's talking to what. You'll end
up with three long-running terminals (a tunnel, the server, the client) plus one free terminal
for the commands below.

### 1. Log in and create the project

```bash
diagrid login
diagrid project create mcp-auth --use
```

`--use` sets `mcp-auth` as your default project, so most commands below don't need an explicit
`--project` flag — `diagrid dev run` in step 4 is the one exception, noted there.

### 2. Register the MCP server

```bash
diagrid apply -f resources/mcp-server.yaml
```

This creates the `mcp-server` MCP server resource pointing at `http://localhost:8000/mcp`, with
its access policy starting deny-all. It isn't reachable yet: nothing is listening on
`localhost:8000`, and no upstream credential is configured.

### 3. Create the mcp-client App ID

```bash
diagrid appid create mcp-client --wait
```

This prints an API token — `mcp-client` runs as a plain local process later (not through
`diagrid dev run`), so you'll export this token yourself in step 6:

```
🔒 YOUR API_TOKEN: diagrid://v1/.../mcp-client/...
```

You can always retrieve it again with `diagrid appid get mcp-client -o yaml` (under
`status.apiToken`). Also note your project's HTTP endpoint, which you'll need in step 6 too:

```bash
diagrid project get mcp-auth
```

```
Endpoints:
  http:
    url:   https://http-prj123456.cloud.r1.diagrid.io:443
```

### 4. Open the tunnel for mcp-server — Terminal 1

```bash
diagrid dev run --app-id mcp-server --app-port 8000 --project mcp-auth --skip-managed-kv --skip-managed-pubsub --skip-default-resiliency
```

This is the only role `diagrid dev run` plays in this quickstart. With no trailing command, it
does exactly one thing: open a secure tunnel from Catalyst Cloud to `localhost:8000` for the
`mcp-server` App ID. It does not run your code — that's the next step. Leave it running.

(`--project` has to be explicit here — without it, `dev run` prompts for an interactive
confirmation, which just hangs in a non-interactive shell.)

### 5. Run the MCP server — Terminal 2

```bash
cd mcp_server
source ../venv/bin/activate
SERVER_SHARED_SECRET=local-dev-shared-secret python main.py
```

Leave it running.

### 6. Run the MCP client — Terminal 3

```bash
cd mcp_client
source ../venv/bin/activate
export DAPR_HTTP_ENDPOINT=<the http url from step 3>
export DAPR_API_TOKEN=<the token from step 3>
python main.py
```

Leave it running. Unlike `mcp-server`, `mcp-client` never receives inbound requests through
Catalyst — it only calls out to Catalyst's MCP proxy endpoint — so it needs no tunnel, just
these two environment variables.

### 7. See it fail closed (default state) — Terminal 4

A freshly registered MCP server starts in two "closed" states at once: `mcp-server` requires a
shared-secret header that Catalyst hasn't been given yet, and the access policy denies every
caller and tool by default.

```bash
curl -s -X POST http://localhost:5001/run | python -m json.tool
```

Both problems currently look identical from the caller's side — Catalyst tears the session
down before anything reaches your tool code:

```json
{
    "tools": [],
    "add_result": null,
    "balance_result": null,
    "errors": [
        { "step": "list_tools", "error": "Session terminated" },
        { "tool": "add", "error": "Session terminated" },
        { "tool": "get_account_balance", "error": "Session terminated" }
    ]
}
```

Check the `mcp-server` log in Terminal 2 and you'll see why — your server itself is rejecting
Catalyst:

```
INFO:     ... "POST /mcp HTTP/1.1" 401 Unauthorized
```

## Authenticating to the MCP Server

`mcp_server/main.py` requires every request to carry a `x-mcp-shared-secret` header matching
`SERVER_SHARED_SECRET` (see the `RequireUpstreamCredential` middleware) — this is the server's
own defense, independent of Catalyst. Catalyst has to be given that credential before it can
authenticate itself to your server on the caller's behalf; see
[MCP Authentication](https://docs.diagrid.io/develop/mcp/mcp-authentication) for the full set of
options (static headers, OAuth2 client credentials, or secretless SPIFFE JWT). This quickstart
uses the simplest one — a static header — stored in Catalyst's secret store, never in the
caller's code.

### Configure the upstream credential

Add a `headers` entry to `resources/mcp-server.yaml`:

```yaml
apiVersion: dapr.io/v1alpha1
kind: MCPServer
metadata:
  name: mcp-server
spec:
  endpoint:
    streamableHTTP:
      url: http://localhost:8000/mcp
      headers:
        - name: x-mcp-shared-secret
          value: local-dev-shared-secret
```

Apply the change from Terminal 4 — Terminals 1-3 keep running as-is, nothing needs restarting:

```bash
diagrid apply -f resources/mcp-server.yaml
```

Trigger the client again:

```bash
curl -s -X POST http://localhost:5001/run | python -m json.tool
```

The response is unchanged — still `Session terminated` for everything. But look at the
`mcp-server` log in Terminal 2 again:

```
INFO:     ... "POST /mcp HTTP/1.1" 200 OK
Processing request of type ListToolsRequest
```

Catalyst is now authenticating successfully — the request reaches your tool code. The session
still terminates because `mcp-client` has zero grants on the access policy, which denies
everyone by default. Authentication is fixed; authorization is next.

## Authorizing Tool Calls

A Catalyst MCP access policy is an allow-list that decides which caller App IDs may use which
tools. Like authentication, you change it at runtime — no redeploy.

### Phase 1 — Allow the "add" tool

Grant the `mcp-client` App ID access to just the `add` tool:

```bash
diagrid mcpserver access grant mcp-server --caller mcp-client --allow-tools add --wait
```

`--wait` only waits for the control-plane update to finish — data-plane enforcement can lag a
couple of seconds behind that. If the very next call still looks denied, retry once.

Trigger the client again:

```bash
curl -s -X POST http://localhost:5001/run | python -m json.tool
```

Now `add` is discoverable and succeeds, while `get_account_balance` is rejected with a clean
`403` — the session itself no longer terminates, because the caller has *some* grant:

```json
{
    "tools": [
        { "name": "add", "description": "Add two numbers together." }
    ],
    "add_result": "5",
    "balance_result": null,
    "errors": [
        {
            "tool": "get_account_balance",
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

Both tools are now discoverable and succeed:

```json
{
    "tools": [
        { "name": "add", "description": "Add two numbers together." },
        { "name": "get_account_balance", "description": "Look up the balance for an account. Treated as a sensitive operation." }
    ],
    "add_result": "5",
    "balance_result": "Account acct-42 balance: $1,204.53",
    "errors": []
}
```

## How It Works

### Authentication

Catalyst authenticates itself to your MCP server using whatever credential you configure on
the `MCPServer` resource's `spec.endpoint.streamableHTTP` — a static `headers` entry (this
quickstart), an OAuth2 client-credentials flow, or a secretless SPIFFE JWT it mints per-request.
Whichever you choose, the credential lives on the connection config in Catalyst's secret store —
never in the caller's code, prompts, or logs. `mcp_client/main.py` never sees the
`x-mcp-shared-secret` header at all; only Catalyst and your server do. See
[MCP Authentication](https://docs.diagrid.io/develop/mcp/mcp-authentication) for the other
options, and [Register a custom server](https://docs.diagrid.io/develop/mcp/mcpserver-getting-started#register-a-custom-server)
for registering one via CLI flags (`diagrid mcpserver create --header ...`) instead of YAML.

### Authorization

Each MCP server has exactly one **access policy**, created automatically with a deny-all
baseline and lifecycle-locked to the server (you edit its rules; you don't create or delete it
directly). A rule names one or more **callers** (App IDs, or `*` for any) and the **tools**
they may use (names, or `*` for all). A tool call is allowed only if some rule matches both the
caller and the tool.

Manage the policy with the `diagrid mcpserver access` commands:

```bash
# Grant: add caller→tool allow-list entries
diagrid mcpserver access grant mcp-server --caller mcp-client --allow-tools add,echo

# Revoke specific grants, or a caller's entire rule. Unlike grant, revoke asks
# for interactive confirmation unless you pass --yes (or --approve).
diagrid mcpserver access revoke mcp-server --caller mcp-client --allow-tools echo --yes
diagrid mcpserver access revoke mcp-server --caller "*" --all --yes

# Inspect the current policy
diagrid mcpserver access get mcp-server      # one server, full detail
diagrid mcpserver access list                # all servers in the project

# Preview a verdict WITHOUT calling the server or waiting for rollout.
diagrid mcpserver access test mcp-server --caller mcp-client --tool get_account_balance
# → ALLOWED: ...  or  DENIED: ...
```

### Telling authentication and authorization failures apart

`Session terminated`, with no HTTP status, specifically means the caller matches **no rule at
all** in the access policy — Catalyst tears the session down at that point regardless of
whether the upstream credential is even valid, so on its own it doesn't tell you which problem
you have. Once a caller matches at least one rule, the two failure modes stop looking alike: a
call to a tool that rule doesn't cover comes back as a clean `403`, as seen above with
`get_account_balance`, and a bad upstream credential comes back as a clean `401` instead of a
session teardown — the request now gets far enough to actually reach, and be rejected by, your
server. To tell the two apart when the whole session is failing:

- **Check the MCP server's own log.** `401 Unauthorized` from your server means Catalyst
  itself isn't authenticated yet — fix the credential on the `MCPServer` resource. A `200 OK`
  followed by `Processing request of type ListToolsRequest` means Catalyst reached your tool
  code — authentication is fine, and it's the access policy (no matching rule) holding
  everything closed.
- **Run `diagrid mcpserver access test`.** It evaluates the policy directly and answers
  `ALLOWED`/`DENIED` without calling the server at all. `DENIED` for every tool confirms the
  caller matches no rule — check the server log to see whether authentication is *also*
  broken. `ALLOWED` means the policy isn't the problem — if the caller still can't reach that
  tool, the upstream credential is, and it'll surface as a clean `401`, not `Session
  terminated`.

## Files

| File | Purpose |
|------|---------|
| `resources/mcp-server.yaml` | The `MCPServer` resource — add the `headers` block here to configure the upstream credential |
| `mcp_client/main.py` | FastAPI client that discovers and invokes tools through Catalyst |
| `mcp_server/main.py` | FastMCP server exposing `add` and `get_account_balance`, guarded by a shared-secret middleware |
| `test.rest` | REST-client requests for manual testing |

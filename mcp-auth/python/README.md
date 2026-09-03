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
- **A local server, exposed via tunnel**: `mcp-server` declares an `appPort` in
  `mcp-auth-quickstart.yaml`, so `diagrid dev run` opens a secure tunnel from Catalyst Cloud to
  `localhost:8000` for it — reachable from your hosted Catalyst project with no public endpoint
  or inbound firewall rule required — while also running its process for you.
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

1. [Diagrid CLI](https://docs.diagrid.io/references/catalyst/catalyst-cli-intro/) installed
2. [Python 3.12+](https://www.python.org/downloads/)
3. [uv](https://docs.astral.sh/uv/getting-started/installation/) installed

## Setup

`mcp_client` and `mcp_server` share the one `uv`-managed project at the repo root — a single
sync installs dependencies for both:

```bash
cd mcp-auth/python
uv sync
```

## Running the Quickstart

### 1. Log in, create the project, and create the mcp-client App

```bash
diagrid login
diagrid project create mcp-auth --use
```

`--use` sets `mcp-auth` as your default project, so the commands below don't need an explicit
`--project` flag.

```bash
diagrid app create mcp-client --wait
```

A one-off command that returns immediately — no dedicated terminal needed. `mcp-client` is a
plain caller with no MCP-specific behavior of its own, so a generic Catalyst App is all it needs.

### 2. Register the MCP server

```bash
diagrid apply -f resources/mcp-server.yaml
```

Also a one-off command, run right after the client's. `mcp-server` doesn't get a plain
`app create` like `mcp-client` did: it's different because it needs an identity *and* its
MCP-specific behavior (the proxy endpoint, the access policy) together, and applying the
`MCPServer` resource is what gives it both at once — creating it as a plain App first would
collide with that (`cannot create MCPServer "mcp-server": an App ID with the same name already
exists`). This creates the resource pointing at `http://localhost:8000/mcp`, with its access
policy starting deny-all and no upstream credential yet — nothing is listening on `localhost:8000`
until the next step, so it isn't reachable yet either.

### 3. Run everything — Terminal 1

`diagrid dev run` is a local dev-loop helper, not a production deployment mechanism — it runs
multiple processes together, alongside their tunnel connectivity, in one place specifically to
make local iteration and debugging easier.

```bash
diagrid dev run -f mcp-auth-quickstart.yaml --project mcp-auth --approve --skip-managed-kv --skip-managed-pubsub --skip-default-resiliency
```

`mcp-auth-quickstart.yaml` also points `resourcesPath` at `./resources`, so `diagrid dev run`
re-applies the `mcp-server` resource you just registered — harmlessly, since applying is
idempotent — and recognizes its App identity is already managed by that MCPServer resource, so
it doesn't try to provision it again. It then launches both services locally, `mcp-client` under
the App you created in step 1. `mcp-server` declares an `appPort`, so it also gets a secure
tunnel from Catalyst Cloud to `localhost:8000`; `mcp-client` doesn't declare one, since it only
calls out to Catalyst's MCP proxy endpoint and never receives inbound requests, so no tunnel is
opened for it. No manual token or endpoint copying either — `dev run` wires `DAPR_HTTP_ENDPOINT`
and `DAPR_API_TOKEN` straight into `mcp-client`'s process. Wait for the log output to show both
apps started before continuing.

Catalyst also starts periodically probing `mcp-server`'s reachability as soon as its tunnel is
up, independent of anything `mcp-client` does — so this terminal may already show rejected
requests by the time both apps report started, before you ever trigger anything yourself in
step 4 below.

> Leave `diagrid dev run` running in this terminal and use a second terminal for the steps below.

### 4. See it fail closed (default state) — Terminal 2

A freshly registered MCP server starts in two "closed" states at once: `mcp-server` requires a
shared-secret header that Catalyst hasn't been given yet, and the access policy denies every
caller and tool by default.

> **Reusing a project from an earlier pass through this quickstart?** The access policy and the
> `headers` credential both live on the `mcp-server` resource itself, not on this walkthrough —
> re-registering it with `diagrid apply` updates the resource but doesn't reset either one. If
> `mcp-server` already existed in this project, `add` (or everything) may already succeed below
> instead of failing closed. Check `diagrid mcpserver access get mcp-server` and revoke any
> grants it shows (`diagrid mcpserver access revoke mcp-server --caller <name> --all --yes`, once
> per caller listed), and confirm `resources/mcp-server.yaml` has no `headers` block before
> applying, to see the fail-closed behavior below.

**macOS/Linux (curl):**

```bash
curl -s -X POST http://localhost:5001/run | python -m json.tool
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:5001/run' | ConvertTo-Json -Depth 6
```

Both problems currently look identical here — `Session terminated`, no detail:

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

The real reason is sitting in Terminal 1, in `mcp-client`'s own log lines (labeled
`== APP - mcp-client ==`), via the HTTP request it actually made:

```
INFO:httpx:HTTP Request: POST https://.../v1.0/diagrid/mcp/mcp-server "HTTP/1.1 404 Not Found"
```

That `404` is Catalyst's access-policy gate turning the caller away before the request ever
reaches `mcp-server` — this quickstart never has a case where the MCP server itself doesn't
exist, so read it as "this caller matches no rule," not "not found." The JSON response above
doesn't carry that code; only an in-session per-tool denial (see Authorizing Tool Calls below)
comes back as a clean status the demo can report.

You'll likely also see `mcp-server`'s own lines (`== APP - mcp-server ==`) in Terminal 1 already
showing `401 Unauthorized` on their own — that's Catalyst periodically checking the upstream
credential in the background (see step 3 above), independent of anything you just did. It's a
real signal, just not about this call: while the access policy denies you, your request never
reaches `mcp-server` at all.

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

Apply the change from your driver terminal (Terminal 2 in the consolidated flow, Terminal 4 if
you ran every process manually) — everything you started earlier keeps running as-is, nothing
needs restarting:

```bash
diagrid apply -f resources/mcp-server.yaml
```

Trigger the client again:

**macOS/Linux (curl):**

```bash
curl -s -X POST http://localhost:5001/run | python -m json.tool
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:5001/run' | ConvertTo-Json -Depth 6
```

The response is unchanged — still `Session terminated` for everything. Fixing the upstream
credential doesn't unlock the caller; the access policy is a separate gate, and it's still
deny-all.

Separately — and independent of the client call above — Catalyst has been retrying its own
connection to `mcp-server` in the background ever since the tunnel came up, so you don't need to
trigger anything to see it succeed. Check that output whenever you like (Terminal 1 in the
consolidated flow, Terminal 2 if you ran it manually):

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

**macOS/Linux (curl):**

```bash
curl -s -X POST http://localhost:5001/run | python -m json.tool
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:5001/run' | ConvertTo-Json -Depth 6
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

**macOS/Linux (curl):**

```bash
curl -s -X POST http://localhost:5001/run | python -m json.tool
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:5001/run' | ConvertTo-Json -Depth 6
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

`Session terminated`, with no status code in the JSON response, specifically means the caller
matches **no rule at all** in the access policy. Catalyst does send back a real status — a `404`
from its edge, before the request ever reaches `mcp-server` — but it happens on the request that
establishes the MCP session, and the Python MCP client library doesn't preserve that code the
way it preserves one from an in-session tool call, so the demo's own error handling never gets a
hold of it either. `mcp-client`'s own log shows it plainly, via httpx's request logging:
`"HTTP/1.1 404 Not Found"`. Read that as "caller matches no rule," not "server doesn't exist" —
this quickstart has no scenario where the MCP server itself is missing; Catalyst reuses the same
generic code for both so a fully unauthorized caller can't tell which one it hit.

While the caller has zero grants, `mcp-server`'s own log is a red herring: none of the caller's
requests ever reach it, so anything you see there — including a `401` — is Catalyst's own
independent, periodic health-check of the credential, updating on its own regardless of what any
caller does. Once the caller matches at least one rule, that changes: real proxied requests start
reaching `mcp-server` too, and the two failure modes stop looking alike in the JSON response as
well — a call to a tool that rule doesn't cover comes back as a clean `403`, as seen above with
`get_account_balance`, and a bad upstream credential comes back as a clean `401` instead of
`Session terminated` — the request now gets far enough to actually reach, and be rejected by,
your server. To tell the two apart when the whole session is failing:

- **Check `mcp-client`'s own log for the actual status code**, especially while grants are still
  zero — `mcp-server`'s log won't reflect your request at all in that state.
- **Run `diagrid mcpserver access test`.** It evaluates the policy directly and answers
  `ALLOWED`/`DENIED` without calling the server at all. `DENIED` for every tool confirms the
  caller matches no rule. `ALLOWED` means the policy isn't the problem — if the caller still
  can't reach that tool, the upstream credential is.

## Files

| File | Purpose |
|------|---------|
| `mcp-auth-quickstart.yaml` | `diagrid dev run` multi-app file (both services) |
| `resources/mcp-server.yaml` | The `MCPServer` resource — add the `headers` block here to configure the upstream credential |
| `mcp_client/main.py` | FastAPI client that discovers and invokes tools through Catalyst |
| `mcp_server/main.py` | FastMCP server exposing `add` and `get_account_balance`, guarded by a shared-secret middleware |
| `test.rest` | REST-client requests for manual testing |

## Appendix: Run Every Process Manually

The flow above uses one `diagrid dev run -f` command to launch both services and their tunnel
together. If you'd rather see every Catalyst resource and every local process as its own
explicit command — useful for understanding exactly what's talking to what, or for attaching a
debugger to one process without disturbing the other — use the fully manual version below
instead. It reaches the identical end state, just via more terminals and more individual
commands.

Follow this section **instead of** "Running the Quickstart" above, not in addition to it — both
create the same `mcp-auth` project, App IDs, and MCP server resource, so running both against the
same project will collide. Once you've gotten this far with either one, "Authenticating to the
MCP Server" and "Authorizing Tool Calls" above apply the same way regardless of which path you
used to get here.

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

### 3. Create the mcp-client App

```bash
diagrid app create mcp-client --wait
```

`mcp-client` runs as a plain local process later (not through `diagrid dev run`), so you'll
export its API token yourself in step 6. Unlike the old `appid create`, `app create` doesn't
print the token directly — fetch it with:

```bash
diagrid app get mcp-client -o yaml
```

```yaml
status:
  apiToken: diagrid://v1/.../mcp-client/...
```

(under `status.apiToken`). Also note your project's HTTP endpoint, which you'll need in step 6 too:

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
diagrid dev run --id mcp-server --app-port 8000 --project mcp-auth --skip-managed-kv --skip-managed-pubsub --skip-default-resiliency
```

With no trailing command, `diagrid dev run` does exactly one thing here: open a secure tunnel
from Catalyst Cloud to `localhost:8000` for the `mcp-server` App ID. It does not run your code —
that's the next step. Leave it running.

(`--project` has to be explicit here — without it, `dev run` prompts for an interactive
confirmation, which just hangs in a non-interactive shell.)

### 5. Run the MCP server — Terminal 2

```bash
cd mcp_server
SERVER_SHARED_SECRET=local-dev-shared-secret uv run main.py
```

Leave it running. Catalyst starts periodically probing `mcp-server`'s reachability as soon as it
can reach this process, independent of anything `mcp-client` does — so this terminal may already
show rejected requests before you ever trigger anything yourself in step 7 below.

### 6. Run the MCP client — Terminal 3

```bash
cd mcp_client
export DAPR_HTTP_ENDPOINT=<the http url from step 3>
export DAPR_API_TOKEN=<the token from step 3>
uv run main.py
```

Leave it running. Unlike `mcp-server`, `mcp-client` never receives inbound requests through
Catalyst — it only calls out to Catalyst's MCP proxy endpoint — so it needs no tunnel, just
these two environment variables.

### 7. See it fail closed (default state) — Terminal 4

A freshly registered MCP server starts in two "closed" states at once: `mcp-server` requires a
shared-secret header that Catalyst hasn't been given yet, and the access policy denies every
caller and tool by default.

> **Reusing a project from an earlier pass through this quickstart?** The access policy and the
> `headers` credential both live on the `mcp-server` resource itself, not on this walkthrough —
> re-registering it with `diagrid apply` updates the resource but doesn't reset either one. If
> `mcp-server` already existed in this project, `add` (or everything) may already succeed below
> instead of failing closed. Check `diagrid mcpserver access get mcp-server` and revoke any
> grants it shows (`diagrid mcpserver access revoke mcp-server --caller <name> --all --yes`, once
> per caller listed), and confirm `resources/mcp-server.yaml` has no `headers` block before
> applying, to see the fail-closed behavior below.

**macOS/Linux (curl):**

```bash
curl -s -X POST http://localhost:5001/run | python -m json.tool
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:5001/run' | ConvertTo-Json -Depth 6
```

Both problems currently look identical here — `Session terminated`, no detail:

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

The real reason is sitting in Terminal 3, in `mcp-client`'s own log, via the HTTP request it
actually made:

```
INFO:httpx:HTTP Request: POST https://.../v1.0/diagrid/mcp/mcp-server "HTTP/1.1 404 Not Found"
```

That `404` is Catalyst's access-policy gate turning the caller away before the request ever
reaches `mcp-server` — this quickstart never has a case where the MCP server itself doesn't
exist, so read it as "this caller matches no rule," not "not found." The JSON response above
doesn't carry that code; only an in-session per-tool denial (see Authorizing Tool Calls below)
comes back as a clean status the demo can report.

You'll likely also see `mcp-server`'s own log in Terminal 2 already showing `401 Unauthorized`
on its own — that's Catalyst periodically checking the upstream credential in the background
(see step 5 above), independent of anything you just did. It's a real signal, just not about
this call: while the access policy denies you, your request never reaches `mcp-server` at all.

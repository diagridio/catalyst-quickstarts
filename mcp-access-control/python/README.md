# MCP Access Control Quickstart

This quickstart demonstrates how to secure MCP (Model Context Protocol) servers and tools using Diagrid Catalyst **access control lists (ACLs)** and **OAuth2 middleware pipelines**.

## What This Quickstart Demonstrates

- **MCP Server with Dapr Service Invocation**: Run an MCP server that exposes tools, with downstream service calls routed through Dapr
- **Access Control Lists (ACLs)**: Control which services can invoke the MCP server and its downstream dependencies
- **Granular Tool-Level Security**: Allow the MCP client to call the server while blocking the server from reaching a specific downstream service
- **OAuth2 Middleware Pipeline**: Protect MCP endpoints with JWT token validation using Dapr's bearer middleware

## Architecture

```
                          Access Control                    Access Control
                          enforced here                     enforced here
                               |                                |
                               v                                v
MCP Client ──> [ Dapr Service Invocation ] ──> MCP Server ──> [ Dapr Service Invocation ] ──> Weather Service
  (5001)                                        (8000)                                          (8001)
               Tools: add, get_weather_alert, echo              Endpoint: /weather-alert
```

**Three services:**

| Service | Port | Description |
|---------|------|-------------|
| **mcp-client** | 5001 | Discovers and invokes MCP tools through Dapr service invocation |
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
diagrid project create mcp-access-control
diagrid project use mcp-access-control
diagrid dev run -f mcp-quickstart.yaml --project mcp-access-control --approve --skip-default-resiliency
```

This starts all three services. Wait for the log output to confirm they are ready.

### 2. Test All Access Allowed (Default)

From another terminal, trigger the MCP client:

```bash
curl -s -X POST http://localhost:5001/run | python -m json.tool
```

Expected response — all tools succeed:

```json
{
    "tools": [
        {"name": "add", "description": "Add two numbers together."},
        {"name": "get_weather_alert", "description": "Get a weather alert for a given city."},
        {"name": "echo", "description": "Echo back a message."}
    ],
    "add_result": "5",
    "weather_alert": "Severe thunderstorm warning until 6 PM CDT",
    "errors": []
}
```

## Part 1: Access Control Lists

Catalyst access control configurations determine which App IDs are allowed to invoke other App IDs. You can dynamically apply and swap configurations without restarting services.

### Phase 1 — All Access Allowed (Default)

By default, there are no access restrictions. The MCP client successfully discovers tools and invokes both `add` and `get_weather_alert`.

```bash
curl -s -X POST http://localhost:5001/run | python -m json.tool
```

Both tools return valid results.

### Phase 2 — Block Client from MCP Server

Stop the dev session (Ctrl+C), then create and apply a deny configuration that blocks `mcp-client` from calling `mcp-server`:

```bash
diagrid configuration create mcp-server-deny \
    --default-action deny \
    --policy mcp-client:deny

diagrid appid update mcp-server --app-config mcp-server-deny
```

Restart the dev session:

```bash
diagrid dev run -f mcp-quickstart.yaml --project mcp-access-control --approve --skip-default-resiliency
```

From another terminal, trigger the client:

```bash
curl -s -X POST http://localhost:5001/run | python -m json.tool
```

The client receives an error — it **cannot reach the MCP server at all**. No tools are discovered, no calls succeed.

### Phase 3 — Block MCP Server from Weather Service

Stop the dev session (Ctrl+C), then restore client access to the MCP server but block the MCP server from reaching the weather service:

```bash
# Restore MCP server access
diagrid configuration create mcp-server-allow \
    --default-action allow

diagrid appid update mcp-server --app-config mcp-server-allow

# Block MCP server from calling weather service
diagrid configuration create weather-deny \
    --default-action deny \
    --policy mcp-server:deny

diagrid appid update weather-service --app-config weather-deny
```

Restart the dev session:

```bash
diagrid dev run -f mcp-quickstart.yaml --project mcp-access-control --approve --skip-default-resiliency
```

From another terminal, trigger the client:

```bash
curl -s -X POST http://localhost:5001/run | python -m json.tool
```

The `add` tool works normally, but `get_weather_alert` returns a `403 Forbidden` error indicating the MCP server was denied access to the weather service. This demonstrates **granular, tool-level access control** — the client can use the MCP server, but the server's downstream calls are restricted.

### Restore Full Access

Stop the dev session (Ctrl+C), then restore access:

```bash
diagrid configuration create weather-allow \
    --default-action allow

diagrid appid update weather-service --app-config weather-allow
```

## Part 2: OAuth2 Middleware Pipeline

This section demonstrates adding JWT token validation to the MCP server using Dapr's HTTP bearer middleware. Requests without a valid token are rejected before reaching the application.

### Prerequisites

An OAuth2 provider (e.g., [Auth0](https://auth0.com)) with:
- A **Machine-to-Machine application** configured for client credentials grant
- An **API audience** defined

### Setup OAuth2

1. Set your OAuth2 credentials:

```bash
export AUTH0_DOMAIN="your-tenant.us.auth0.com"
export AUTH0_CLIENT_ID="your-client-id"
export AUTH0_CLIENT_SECRET="your-client-secret"
export AUTH0_AUDIENCE="https://your-api-audience/"
```

2. Update and apply the bearer middleware component:

```bash
envsubst < resources/bearer-component.yaml | diagrid apply -f -
```

3. Apply the OAuth configuration:

```bash
diagrid apply -f resources/mcp-server-oauth.yaml
```

### Phase 1 — Server Enforces OAuth, No Token Sent

Apply the OAuth configuration to the MCP server:

```bash
diagrid appid update mcp-server --app-config mcp-server-oauth
```

Stop and restart the services **without** the `AUTH0_*` environment variables (or unset them):

```bash
diagrid dev run -f mcp-quickstart.yaml --project mcp-access-control --approve --skip-default-resiliency
```

Trigger the client:

```bash
curl -s -X POST http://localhost:5001/run | python -m json.tool
```

The request fails — the bearer middleware rejects it because no token is present.

### Phase 2 — Server Enforces OAuth, Valid Token Sent

Stop the services and restart **with** the `AUTH0_*` environment variables set:

```bash
export AUTH0_DOMAIN="your-tenant.us.auth0.com"
export AUTH0_CLIENT_ID="your-client-id"
export AUTH0_CLIENT_SECRET="your-client-secret"
export AUTH0_AUDIENCE="https://your-api-audience/"
diagrid dev run -f mcp-quickstart.yaml --project mcp-access-control --approve --skip-default-resiliency
```

Trigger the client:

```bash
curl -s -X POST http://localhost:5001/run | python -m json.tool
```

The client automatically fetches an Auth0 token using the client credentials grant and attaches it to the request. The bearer middleware validates the JWT (checking the issuer and audience claims), and the MCP tools are invoked successfully.

### Restore Default Configuration

```bash
diagrid appid update mcp-server --app-config mcp-server-allow
```

## How It Works

### Access Control Lists

Catalyst enforces access control at the service invocation layer. Each App ID can have a **configuration** that defines:

- **`defaultAction`**: `allow` or `deny` — the default policy for all callers
- **`policies`**: Per-App-ID overrides (e.g., deny `mcp-client` specifically)

When `mcp-client` calls `mcp-server` via Dapr service invocation, Catalyst checks the target's configuration. If the caller's App ID is denied, the request returns **403 Forbidden** before reaching the application.

### OAuth2 Bearer Middleware

The Dapr HTTP bearer middleware intercepts incoming requests and validates JWT tokens:

1. Checks for an `Authorization: Bearer <token>` header
2. Fetches the issuer's JWKS (JSON Web Key Set) to verify the token signature
3. Validates the `iss` (issuer) and `aud` (audience) claims
4. Forwards the request if valid; returns **401 Unauthorized** if not

The middleware is configured as a **component** and attached to an App ID's HTTP pipeline via a **configuration**.

```yaml
# Bearer middleware component
spec:
  type: middleware.http.bearer
  metadata:
  - name: issuer
    value: "https://your-tenant.auth0.com/"
  - name: audience
    value: "https://your-api-audience/"

# Configuration with OAuth pipeline
spec:
  appHttpPipeline:
    handlers:
    - name: bearer
      type: middleware.http.bearer
```

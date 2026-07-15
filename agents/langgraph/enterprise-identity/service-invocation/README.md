# Enterprise Identity — Vanilla LangGraph over Service Invocation

Run a **vanilla LangGraph agent** under a user identity that can act on the
user's behalf — with **no Diagrid workflow runner**. This is a plain FastAPI app
that hosts a LangGraph graph, adds the Diagrid identity middleware, and calls an
MCP tool through the Diagrid sidecar on behalf of the calling user.

## What this quickstart demonstrates

- **No Diagrid workflow runner** — a plain FastAPI app hosting LangGraph. The
  graph itself has no Diagrid awareness.
- **User identity flows in via `X-Diagrid-User-Token`** — the sidecar populates
  this header, and `OAuthMiddleware`
  reads the delivered claims onto `request.state.diagrid_user`.
- **OBO to MCP is transparent** — the on-behalf-of exchange happens in the
  sidecar. Nothing the developer does beyond calling the sidecar
  (`invoke_method`) is identity-aware; the user token propagates automatically to
  the MCP tool call.
- **HITL is not available in this path** — human-in-the-loop requires the durable
  workflow runner. See [`workflow-durability/`](../../workflow-durability/) for that.

## Identity setup

Diagrid identity is wired in three steps, all in [`main.py`](./main.py):

1. Construct an `OAuthConfig` with the scopes the agent requires.
2. Register `OAuthMiddleware` on the FastAPI app with that config.
3. Read the authenticated user off `request.state.diagrid_user` inside any
   endpoint — the middleware populates it from the sidecar-delivered claims.

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [Python 3.10+](https://www.python.org/downloads/)
3. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

```bash
cd agents/langgraph/enterprise-identity/service-invocation

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

export OPENAI_API_KEY="your-key-here"
```

## Running the quickstart

```bash
diagrid login
diagrid dev run -f dev.yaml
```

## Who handles the user token

The user identity travels on the `X-Diagrid-User-Token` header:**

- **Developers building agents** trigger their agent via HTTP setting the following header: `X-Diagrid-User-Token`.
  `OAuthMiddleware` reads it and populates `request.state.diagrid_user`.
- **Users invoking agents** — via `diagrid call invoke`, the UI, or an
  SDK — do not touch it either. The tooling sets it automatically from your
  credentials after `diagrid login`.

The header only appears explicitly in the raw `curl` example below, which is the
fallback for debugging or calling from a client that isn't Diagrid tooling.

## Invoking the agent

From another terminal, once the app is running.

### Primary — Diagrid CLI (no header handling)

The CLI adds `X-Diagrid-User-Token` automatically from `~/.diagrid/creds` after
`diagrid login`. Note the dotted `<appid>.<method>` notation:

```bash
diagrid call invoke post langgraph-identity-agent.invoke \
  --app-id <caller-appid> \
  --data '{"prompt": "How many open opportunities does ACME have in Salesforce?"}'
```

### Alternative — raw HTTP (debugging or non-CLI callers)

Only here does the caller set the header itself:

```bash
curl -X POST http://localhost:3500/v1.0/invoke/langgraph-identity-agent/method/invoke \
  -H "X-Diagrid-User-Token: Bearer <your JWT>" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "How many open opportunities does ACME have in Salesforce?"}'
```

### Negative — no header (expect 401)

```bash
curl -X POST http://localhost:3500/v1.0/invoke/langgraph-identity-agent/method/invoke \
  -H "Content-Type: application/json" \
  -d '{"prompt": "How many open opportunities does ACME have in Salesforce?"}'
```

Expected response: `401` with code `oauth.missing_caller_claims`.

The user identity delivered on the inbound request propagates through the sidecar
to the Salesforce MCP tool call — no token handling in the graph.

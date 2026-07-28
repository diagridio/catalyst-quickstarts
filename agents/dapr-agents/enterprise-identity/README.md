# Enterprise Identity — Dapr Agents `DurableAgent`

This quickstart shows how to give a **raw [Dapr Agents](https://github.com/dapr/dapr-agents)
`DurableAgent`** an enterprise identity: it runs under the calling user's identity,
calls downstream tools **on behalf of (OBO)** that user, and gates destructive
operations behind **human-in-the-loop (HITL)** approval.

## How it fits with the other identity quickstarts

The same identity primitives are available across levels of framework abstraction.
The identity *config* is unified — only the *dispatch* differs.

| Quickstart | Framework | Identity surface | HITL |
|------------|-----------|------------------|------|
| [`langgraph/enterprise-identity/service-invocation/`](../../langgraph/enterprise-identity/service-invocation/) | Vanilla LangGraph | `OAuthConfig` via helper library | ✗ (sync path) |
| [`langgraph/enterprise-identity/workflow-durability/`](../../langgraph/enterprise-identity/workflow-durability/) | LangGraph + `DaprWorkflowGraphRunner` | `OAuthConfig` + `HITLConfig` via runner kwargs | ✓ (durable pause/resume) |
| **`dapr-agents/enterprise-identity/`** (this one) | Raw Dapr Agents `DurableAgent` | `OAuthConfig` + `HITLConfig` via `PluginRegistry` | ✓ (durable pause/resume) |

## What this demonstrates

- **Raw `DurableAgent`**.
- **Unified identity config** — the `OAuthConfig` and `HITLConfig` types are the same
  ones used by the LangGraph quickstarts.
- **`Plugin` protocol + `PluginRegistry`** — lifecycle plugins run as a chain, so you
  can add your own plugins alongside `OAuthPlugin` / `HITLPlugin`.
- **Transparent OBO via the sidecar** — the agent calls downstream MCP tools under the
  calling user's identity; the sidecar performs the token exchange. No token handling
  in application code.
- **HITL** — the `delete_account` tool returns `RequireApproval`, and `HITLPlugin` gates
  resumption on a scoped approver, backed by durable workflow pause/resume.

## Identity setup

Identity is wired in [`main.py`](./main.py): build an `OAuthConfig` and a `HITLConfig`,
then pass `lifecycle_dispatcher=PluginRegistry([OAuthPlugin(oauth), HITLPlugin(hitl)])`
to the `DurableAgent`. `OAuthPlugin` runs the agent under the calling user's identity;
`HITLPlugin` gates any tool that returns `RequireApproval` on a scoped approver.

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [Python 3.10+](https://www.python.org/downloads/)
3. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

Inside the project directory, run the following commands:

**macOS/Linux (bash/zsh):**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Configure the LLM provider

Update `resources/llm-provider.yaml` with your OpenAI API key:

```yaml
metadata:
  - name: key
    value: "YOUR_OPENAI_API_KEY"
```

## Running the quickstart

### 1. Deploy and run on Catalyst

```bash
diagrid login
diagrid dev run -f dev.yaml --project salesforce-agent
```

### 2. Invoke the agent (recommended)

Every inbound call must carry the `X-Diagrid-User-Token` header — that is what the
sidecar's inbound auth middleware reads to establish the user identity, and what
`OAuthPlugin` then enforces. The `diagrid` CLI attaches it automatically from
`~/.diagrid/creds` after `diagrid login`, so no header handling is needed:

```bash
diagrid call invoke post salesforce-agent.invoke \
  --app-id <caller-app-id> \
  --data '{"prompt": "What is the name and owner of account 001XX000ABC?"}'
```

Note the dotted `<app-id>.<method>` notation. The agent runs `query_account` under the
calling user's identity; the sidecar performs the OBO token exchange for any downstream
call transparently.

### 3. Invoke over raw HTTP (debugging)

To call the sidecar directly, supply the header yourself:

```bash
curl -X POST http://localhost:3500/v1.0/invoke/salesforce-agent/method/invoke \
  -H "X-Diagrid-User-Token: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the name and owner of account 001XX000ABC?"}'
```

Without the header, the sidecar skips auth, the agent sees no user identity, and
`OAuthPlugin` rejects the request:

```bash
curl -X POST http://localhost:3500/v1.0/invoke/salesforce-agent/method/invoke \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the name and owner of account 001XX000ABC?"}'
```

### 4. Approve a HITL request

Asking the agent to delete an account makes `delete_account` return `RequireApproval`,
so `HITLPlugin` pauses the durable workflow:

```bash
diagrid call invoke post salesforce-agent.invoke \
  --app-id <caller-app-id> \
  --data '{"prompt": "Delete account 001XX000ABC"}'
```

The paused response carries a workflow instance ID and an approval request ID. Resume
it by raising the approval event with a token from an approver holding the `approver.dev`
scope:

```bash
diagrid call workflow raiseevent \
  --app-id salesforce-agent \
  --instance-id <workflow-instance-id-from-response> \
  --event approval-response-<approval-request-id> \
  --data '{"approved": true, "approver_token": "<approver-jwt>"}'
```

You can also drive the invoke requests from [`test.http`](./test.http) with the VS Code
[REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client)
extension.

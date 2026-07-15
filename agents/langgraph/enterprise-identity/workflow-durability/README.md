# LangGraph + Enterprise Identity — Workflow (Durability) Path

A **Customer Operations Agent** built with LangGraph and run as a durable Dapr
Workflow via python-ai's `DaprWorkflowGraphRunner`. It answers questions about
customers by reading Salesforce through an MCP tool, and — with human approval —
erases records on request.

## What this quickstart demonstrates

- **Durable workflow-backed agent**: each graph node runs under
  `DaprWorkflowGraphRunner`, so progress is checkpointed and survives
  crashes and restarts.
- **User identity in, on the agent's behalf out**: the caller's verified user
  identity is exchanged (OBO) for a downstream token scoped to the target MCP
  server. The exchange happens in the sidecar — no token handling in app code.
- **Human-in-the-loop (HITL)**: the destructive `delete_customer` tool durably
  **pauses** the workflow until an approver holding the `approver.dev` scope
  resolves the request, then **resumes** from where it paused. The sync path
  cannot hold a pause open — this is unique to the workflow path.
- **Full audit chain**: the user → agent → tool/MCP hops are recorded in signed
  workflow history, so the entire lineage is auditable after the fact.

## Identity model

- **Developers building agents never touch the `X-Diagrid-User-Token` header.**
  The runner handles inbound identity internally: it verifies the caller's token,
  makes the identity available to the workflow, and performs the OBO exchange for
  downstream MCP calls. Your graph code only declares `OAuthConfig` and
  `HITLConfig`.
- **Same `OAuthConfig` type as the sync-path RFC** ([AI-702](https://linear.app/diagrid/issue/AI-702),
  [`../service-invocation/`](../service-invocation/)). Whether an agent runs
  vanilla (sync) or under the workflow runner (this example), inbound identity is
  configured the same way — this is the unification story we're validating.

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [Python 3.10+](https://www.python.org/downloads/)
3. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

**macOS/Linux (bash/zsh):**

```bash
cd agents/langgraph/enterprise-identity/workflow-durability

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**

```powershell
cd agents/langgraph/enterprise-identity/workflow-durability

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Set your API key

**macOS/Linux (bash/zsh):**

```bash
export OPENAI_API_KEY="your-key-here"
```

**Windows (PowerShell):**

```powershell
$env:OPENAI_API_KEY = "your-key-here"
```

## Running the quickstart

### 1. Deploy and run

```bash
diagrid login
diagrid dev run -f dev.yaml
```

The agent's app ID is `customer-ops-agent`.

### 2. Invoke the agent

**Primary — CLI (no header handling):**

The CLI adds the `X-Diagrid-User-Token` header automatically from
`~/.diagrid/creds` after `diagrid login`. Note the dotted `<appid>.<method>`
notation for the target.

```bash
diagrid call invoke post customer-ops-agent.invoke \
  --app-id <caller-appid> \
  --data '{"prompt": "List customers in the EMEA region"}'
```

**Alternative — raw HTTP (for debugging):**

Here you set the user token yourself. This is the header the CLI otherwise adds
for you; app code never reads or sets it.

```bash
curl -X POST http://localhost:3500/v1.0/invoke/customer-ops-agent/method/invoke \
  -H "X-Diagrid-User-Token: Bearer <your JWT>" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "List customers in the EMEA region"}'
```

**Without a user token (expect `401`):**

The runner's inbound dependency rejects the call when no user token is present.

```bash
curl -X POST http://localhost:3500/v1.0/invoke/customer-ops-agent/method/invoke \
  -H "Content-Type: application/json" \
  -d '{"prompt": "List customers in the EMEA region"}'
```

### 3. Approve a human-in-the-loop request

Ask the agent to delete a record. The `delete_customer` tool returns
`RequireApproval`, so the workflow **suspends** and the response includes the
workflow instance ID and an approval request ID.

```bash
diagrid call invoke post customer-ops-agent.invoke \
  --app-id <caller-appid> \
  --data '{"prompt": "Delete customer record 001XX000ABCDEFG"}'
```

An approver holding the `approver.dev` scope resumes the workflow by raising the
approval-response event:

```bash
diagrid call workflow raiseevent \
  --app-id customer-ops-agent \
  --instance-id <workflow-instance-id-from-response> \
  --event approval-response-<approval-request-id> \
  --data '{"approved": true, "approver_token": "<approver JWT>"}'
```

Send `{"approved": false, ...}` to reject the deletion instead.

**Two identities are in play here:**

- The inbound `X-Diagrid-User-Token` carries the **original caller's** identity —
  who asked the agent to act. This is what OBO propagates to Salesforce.
- The `approver_token` in the `raiseevent` body carries the **approver's**
  identity — who authorized the destructive action. It's a different principal,
  checked against the tool's `required_approver_scopes` (`approver.dev`), and
  recorded separately in the audit chain.

## Related

- Sync-path counterpart (vanilla LangGraph, no workflow runner):
  [`../service-invocation/`](../service-invocation/) — [AI-702](https://linear.app/diagrid/issue/AI-702)

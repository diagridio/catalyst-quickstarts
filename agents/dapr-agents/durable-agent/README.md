# Dapr Agents Quickstart - Invitations Manager

This quickstart demonstrates how to build a durable agent using [Dapr Agents](https://github.com/dapr/dapr-agents) and Dapr Workflows. The agent acts as an **Invitations Manager** that sends event invitations to guests via email and physical mail.

## What This Quickstart Demonstrates

- **Durable Execution**: Agent state persisted using Dapr Workflows
- **Tool Integration**: Invitation sending tool with structured input/output schemas
- **State Management**: Multiple state stores for execution, memory, and agent registry
- **Conversation Memory**: Maintain context across interactions using Dapr state
- **Pub/Sub Integration**: Ready for orchestrated multi-agent communication
- **REST API**: Trigger agent workflows via HTTP endpoints

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/references/catalyst/catalyst-cli-intro/) installed
2. [Python 3.11–3.13](https://www.python.org/downloads/)
3. [uv](https://docs.astral.sh/uv/getting-started/installation/) installed
4. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

Navigate to the `dapr-agents/durable-agent` directory and install the dependencies using `uv`:

```bash
cd agents/dapr-agents/durable-agent
uv sync
```

### Configure the LLM Provider

Update `resources/llm-provider.yaml` with your OpenAI API key:

```yaml
metadata:
  - name: key
    value: "YOUR_OPENAI_API_KEY"
```

## Running the Quickstart

### 1. Login and Run

1. Login to Catalyst using the Diagrid CLI:

```bash
diagrid login
```

2. Create a new Catalyst project for the quickstart and use it as the default project for the current session:

```bash
diagrid project create durable-agent-quickstart --enable-agent-infrastructure --wait --use
```

3. Create an agent for the project:

```bash
diagrid agent create dapr-agent --wait
```

4. Run the agent with Catalyst:

```bash
uv run diagrid dev run -f dev-python-durable-agent.yaml --approve
```

Wait until the output shows `Uvicorn running on <localhost:port>`.

### 2. Trigger a Durable Agent run

From a new terminal window:

Choose one of the following to trigger the endpoint:

**macOS/Linux (curl):**

```bash
curl -i -X POST http://localhost:8006/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Send invitations to 100 guests for a corporate networking event"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8006/agent/run' -ContentType 'application/json' -Body '{"task": "Send invitations to 100 guests for a corporate networking event"}'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the request. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension.

The agent will:
1. Receive the invitation request
2. Use the `send_invitations` tool to dispatch invitations
3. Return a breakdown of invitations sent via email and physical mail

### 3. Inspecting the Results in Catalyst

Open the [Catalyst dashboard](https://catalyst.diagrid.io/agents) in your browser and navigate to Agents > invitations-manager. Then select the most recent agent workflow run to view output.

## Part of the Event Planning Team

This agent is one of 7 agents in the **Event Planning Team** orchestration scenario. When running together with the orchestrator, the Invitations Manager handles all guest invitation tasks delegated by the Event Coordinator.

See the [Orchestrator README](../orchestrator/README.md) to run all agents together.

| Agent | Framework | Role |
|-------|-----------|------|
| Venue Scout | CrewAI | Find event venues |
| Catering Coordinator | OpenAI Agents | Find catering options |
| Entertainment Planner | ADK | Find entertainment |
| Budget Analyst | Strands | Calculate event budgets |
| Schedule Planner | LangGraph | Check venue availability |
| **Invitations Manager** | Dapr Agents | Send guest invitations |
| Event Coordinator | Dapr Agents | Orchestrate all agents |

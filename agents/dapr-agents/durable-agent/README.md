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

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [Python 3.10+](https://www.python.org/downloads/)
3. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

```bash
cd dapr-agents/durable-agent

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### Configure the LLM Provider

Update `resources/llm-provider.yaml` with your OpenAI API key:

```yaml
metadata:
  - name: key
    value: "YOUR_OPENAI_API_KEY"
```

## Running the Quickstart

### 1. Deploy and Run

```bash
diagrid login
diagrid dev run -f dev-python-durable-agent.yaml
```

### 2. Trigger a Workflow

From another terminal:

```bash
curl -i -X POST http://localhost:8006/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Send invitations to 100 guests for a corporate networking event"}'
```

The agent will:
1. Receive the invitation request
2. Use the `send_invitations` tool to dispatch invitations
3. Return a breakdown of invitations sent via email and physical mail

## Part of the Event Planning Team

This agent is one of 7 agents in the **Event Planning Team** orchestration scenario. When running together with the orchestrator, the Invitations Manager handles all guest invitation tasks delegated by the Event Coordinator.

See [`agents/dev-python-orchestration.yaml`](../../dev-python-orchestration.yaml) to run all agents together.

| Agent | Framework | Role |
|-------|-----------|------|
| Venue Scout | CrewAI | Find event venues |
| Catering Coordinator | OpenAI Agents | Find catering options |
| Entertainment Planner | ADK | Find entertainment |
| Budget Analyst | Strands | Calculate event budgets |
| Schedule Planner | LangGraph | Check venue availability |
| **Invitations Manager** | Dapr Agents | Send guest invitations |
| Event Coordinator | Dapr Agents | Orchestrate all agents |

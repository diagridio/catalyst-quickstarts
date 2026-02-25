# LangGraph Quickstart - Schedule Planner

This quickstart demonstrates how to run a LangGraph graph as a durable Dapr Workflow using the Diagrid Python SDK. The agent acts as a **Schedule Planner** that checks venue availability and helps create event timelines.

## What This Quickstart Demonstrates

- **LangGraph + Dapr Workflows**: Run a compiled LangGraph StateGraph with durable execution per node
- **Dapr Conversation API**: LLM calls via `DaprChatModel` routed through the `llm-provider` Dapr component
- **Tool Integration**: Availability check tool with mock schedule data
- **Conditional Routing**: LangGraph conditional edges for tool-calling loop
- **REST API**: Trigger graph workflows via HTTP endpoints
- **Agent Registry**: Auto-registration in a shared agent registry for orchestration

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [Python 3.10+](https://www.python.org/downloads/)
3. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

```bash
cd langgraph

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
diagrid dev run -f dev-python-langgraph.yaml
```

### 2. Trigger a Workflow

From another terminal:

```bash
curl -i -X POST http://localhost:8005/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Check if the Grand Ballroom is available on March 15th"}'
```

The agent will:
1. Receive the scheduling request
2. Call the LLM to determine the right tool call
3. Use the `check_availability` tool to check venue availability
4. Return available time slots for the requested date

## Part of the Event Planning Team

This agent is one of 7 agents in the **Event Planning Team** orchestration scenario. When running together with the orchestrator, the Schedule Planner handles all scheduling and availability tasks delegated by the Event Coordinator.

See [`agents/dev-python-orchestration.yaml`](../dev-python-orchestration.yaml) to run all agents together.

| Agent | Framework | Role |
|-------|-----------|------|
| Venue Scout | CrewAI | Find event venues |
| Catering Coordinator | OpenAI Agents | Find catering options |
| Entertainment Planner | ADK | Find entertainment |
| Budget Analyst | Strands | Calculate event budgets |
| **Schedule Planner** | LangGraph | Check venue availability |
| Invitations Manager | Dapr Agents | Send guest invitations |
| Event Coordinator | Dapr Agents | Orchestrate all agents |

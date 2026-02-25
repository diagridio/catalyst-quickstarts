# CrewAI Agent Quickstart - Venue Scout

This quickstart demonstrates how to run a CrewAI agent as a durable Dapr Workflow using the Diagrid Python SDK. The agent acts as a **Venue Scout** that searches for event venues based on city, capacity, and budget.

## What This Quickstart Demonstrates

- **CrewAI + Dapr Workflows**: Run a CrewAI agent with durable execution and automatic state persistence
- **Dapr Conversation API**: LLM calls routed through the `llm-provider` Dapr component (no hardcoded API keys in code)
- **Tool Integration**: Venue search tool with mock results
- **REST API**: Trigger agent workflows via HTTP endpoints
- **Agent Registry**: Auto-registration in a shared agent registry for orchestration

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [Python 3.10+](https://www.python.org/downloads/)
3. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

```bash
cd crewai

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
diagrid dev run -f dev-python-crewai.yaml
```

### 2. Trigger a Workflow

From another terminal:

```bash
curl -i -X POST http://localhost:8001/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Find a venue in Austin for 50 people"}'
```

The agent will:
1. Receive the venue search request
2. Use the `search_venues` tool to find available venues
3. Return venue options with pricing and capacity details

## Part of the Event Planning Team

This agent is one of 7 agents in the **Event Planning Team** orchestration scenario. When running together with the orchestrator, the Venue Scout handles all venue-related tasks delegated by the Event Coordinator.

See [`agents/dev-python-orchestration.yaml`](../dev-python-orchestration.yaml) to run all agents together.

| Agent | Framework | Role |
|-------|-----------|------|
| **Venue Scout** | CrewAI | Find event venues |
| Catering Coordinator | OpenAI Agents | Find catering options |
| Entertainment Planner | ADK | Find entertainment |
| Budget Analyst | Strands | Calculate event budgets |
| Schedule Planner | LangGraph | Check venue availability |
| Invitations Manager | Dapr Agents | Send guest invitations |
| Event Coordinator | Dapr Agents | Orchestrate all agents |

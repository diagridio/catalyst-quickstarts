# ADK Agent Quickstart - Entertainment Planner

This quickstart demonstrates how to run a Google ADK (Agent Development Kit) agent as a durable Dapr Workflow using the Diagrid Python SDK. The agent acts as an **Entertainment Planner** that finds entertainment options for events.

## What This Quickstart Demonstrates

- **Google ADK + Dapr Workflows**: Run an ADK LlmAgent with durable execution and automatic state persistence
- **Dapr Conversation API**: LLM calls routed through the `llm-provider` Dapr component (no hardcoded API keys in code)
- **Tool Integration**: Entertainment search tool with mock results
- **REST API**: Trigger agent workflows via HTTP endpoints
- **Agent Registry**: Auto-registration in a shared agent registry for orchestration

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [Python 3.10+](https://www.python.org/downloads/)
3. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

```bash
cd adk

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### Configure the LLM Provider

Update `resources/llm-provider.yaml` with your API key.

## Running the Quickstart

### 1. Deploy and Run

```bash
diagrid login
diagrid dev run -f dev-python-adk.yaml
```

### 2. Trigger a Workflow

From another terminal:

```bash
curl -i -X POST http://localhost:8003/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Find entertainment for a corporate networking event"}'
```

The agent will:
1. Receive the entertainment request
2. Use the `find_entertainment` tool to search for options
3. Return entertainment options with pricing and duration details

## Part of the Event Planning Team

This agent is one of 7 agents in the **Event Planning Team** orchestration scenario. When running together with the orchestrator, the Entertainment Planner handles all entertainment-related tasks delegated by the Event Coordinator.

See the [Orchestrator README](../dapr-agents/orchestrator/README.md) to run all agents together.

| Agent | Framework | Role |
|-------|-----------|------|
| Venue Scout | CrewAI | Find event venues |
| Catering Coordinator | OpenAI Agents | Find catering options |
| **Entertainment Planner** | ADK | Find entertainment |
| Budget Analyst | Strands | Calculate event budgets |
| Schedule Planner | LangGraph | Check venue availability |
| Invitations Manager | Dapr Agents | Send guest invitations |
| Event Coordinator | Dapr Agents | Orchestrate all agents |

# Dapr Agents Orchestrator Quickstart - Event Coordinator

This quickstart demonstrates how to build an **orchestrator agent** using [Dapr Agents](https://github.com/dapr/dapr-agents) that coordinates a team of specialist agents built with different AI frameworks. The Event Coordinator discovers available agents via the shared registry and delegates tasks to plan a complete event.

## What This Quickstart Demonstrates

- **Multi-Agent Orchestration**: A coordinator that discovers and delegates to specialist agents
- **Framework-Agnostic**: Orchestrates agents built with CrewAI, OpenAI Agents, ADK, Strands, LangGraph, and Dapr Agents
- **Agent Registry**: Dynamic agent discovery via a shared Dapr state store
- **Pub/Sub Communication**: Task delegation via Dapr pub/sub messaging
- **Durable Workflows**: Full execution plan persisted across steps

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [Python 3.10+](https://www.python.org/downloads/)
3. An [OpenAI API key](https://platform.openai.com/api-keys)
4. All 6 specialist agents running (see [Running the Full Team](#running-the-full-team) below)

## Setup

```bash
cd dapr-agents/orchestrator

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

## Running the Full Team

The orchestrator requires the specialist agents to be running and registered. Use the combined dev file to start all 7 services at once:

```bash
cd agents/  # Navigate to the agents root directory
diagrid login
diagrid dev run -f dev-python-orchestration.yaml
```

This starts all agents on ports 8001-8007:

| Port | App ID | Agent | Framework |
|------|--------|-------|-----------|
| 8001 | crewai-agent | Venue Scout | CrewAI |
| 8002 | openai-agent | Catering Coordinator | OpenAI Agents |
| 8003 | adk-agent | Entertainment Planner | ADK |
| 8004 | strands-agent | Budget Analyst | Strands |
| 8005 | langgraph-agent | Schedule Planner | LangGraph |
| 8006 | dapr-agent | Invitations Manager | Dapr Agents |
| 8007 | event-orchestrator | Event Coordinator | Dapr Agents |

## Trigger an Orchestration

Once all agents are running, send a task to the orchestrator:

```bash
curl -i -X POST http://localhost:8007/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Plan a company offsite in Austin for 50 people"}'
```

The orchestrator will:
1. Discover all registered agents in the shared registry
2. Create an execution plan with tasks for each specialist
3. Delegate venue search to the Venue Scout (CrewAI)
4. Delegate catering to the Catering Coordinator (OpenAI Agents)
5. Delegate entertainment to the Entertainment Planner (ADK)
6. Delegate budgeting to the Budget Analyst (Strands)
7. Delegate scheduling to the Schedule Planner (LangGraph)
8. Delegate invitations to the Invitations Manager (Dapr Agents)
9. Synthesize all results into a comprehensive event plan

## Running Standalone

To run only the orchestrator (requires agents to be running separately):

```bash
diagrid dev run -f dev-python-orchestrator.yaml
```

## The Event Planning Team

| Agent | Framework | Role |
|-------|-----------|------|
| Venue Scout | CrewAI | Find event venues |
| Catering Coordinator | OpenAI Agents | Find catering options |
| Entertainment Planner | ADK | Find entertainment |
| Budget Analyst | Strands | Calculate event budgets |
| Schedule Planner | LangGraph | Check venue availability |
| Invitations Manager | Dapr Agents | Send guest invitations |
| **Event Coordinator** | Dapr Agents | Orchestrate all agents |

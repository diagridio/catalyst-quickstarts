# Dapr Agents Orchestrator Quickstart - Event Coordinator

This quickstart demonstrates how to build an **orchestrator agent** using [Dapr Agents](https://github.com/dapr/dapr-agents) that coordinates a team of specialist agents built with different AI frameworks. The Event Coordinator discovers available agents via the shared registry and delegates tasks to plan a complete event.

## What This Quickstart Demonstrates

- **Multi-Agent Orchestration**: A coordinator that discovers and delegates to specialist agents
- **Framework-Agnostic**: Orchestrates agents built with CrewAI, OpenAI Agents, ADK, Strands, LangGraph, Pydantic AI, and Dapr Agents
- **Agent Registry**: Dynamic agent discovery via a shared Dapr state store
- **Pub/Sub Communication**: Task delegation via Dapr pub/sub messaging
- **Durable Workflows**: Full execution plan persisted across steps

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [Python 3.10+](https://www.python.org/downloads/)
3. An [OpenAI API key](https://platform.openai.com/api-keys)
4. A [Google API key](https://aistudio.google.com/)
4. All 7 specialist agents running (see [Running the Full Team](#running-the-full-team) below)

## Setup

**macOS/Linux (bash/zsh):**

```bash
cd dapr-agents/orchestrator

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Windows (PowerShell):**

```powershell
cd dapr-agents/orchestrator

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

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

Export your `GOOGLE_API_KEY` and `OPENAI_API_KEY` for adk and other agents respectively:

**macOS/Linux (bash/zsh):**

```bash
export GOOGLE_API_KEY=""
export OPENAI_API_KEY=""
```

**Windows (PowerShell):**

```powershell
$env:GOOGLE_API_KEY = ""
$env:OPENAI_API_KEY = ""
```

## Running the Full Team

The orchestrator requires the specialist agents to be running and registered. Use the combined dev file to start all 8 services at once:

```bash
cd dapr-agents/orchestrator
diagrid login
diagrid dev run -f dev-multi-agent-orchestration.yaml
```

This starts all agents on ports 8001-8008:

| Port | App ID | Agent | Framework |
|------|--------|-------|-----------|
| 8001 | adk-agent | Entertainment Planner | ADK |
| 8002 | crew-agent | Venue Scout | CrewAI |
| 8003 | dapr-agent | Invitations Manager | Dapr Agents |
| 8004 | agent-orchestration-agent | Event Coordinator | Dapr Agents |
| 8005 | langgraph-agent | Schedule Planner | LangGraph |
| 8006 | openai-agent | Catering Coordinator | OpenAI Agents |
| 8007 | pydanticai-agent | Decoration Planner | Pydantic AI |
| 8008 | strands-agent | Budget Analyst | Strands |

## Trigger an Orchestration

Once all agents are running, send a task to the orchestrator:

Choose one of the following to trigger the endpoint:

**macOS/Linux (curl):**

```bash
curl -i -X POST http://localhost:8004/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Plan a company offsite in Austin for 50 people"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8004/agent/run' -ContentType 'application/json' -Body '{"task": "Plan a company offsite in Austin for 50 people"}'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the request. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension.

The orchestrator will:
1. Discover all registered agents in the shared registry
2. Create an execution plan with tasks for each specialist
3. Delegate entertainment to the Entertainment Planner (ADK)
4. Delegate venue search to the Venue Scout (CrewAI)
5. Delegate invitations to the Invitations Manager (Dapr Agents)
6. Delegate scheduling to the Schedule Planner (LangGraph)
7. Delegate catering to the Catering Coordinator (OpenAI Agents)
8. Delegate decorations to the Decoration Planner (Pydantic AI)
9. Delegate budgeting to the Budget Analyst (Strands)
10. Synthesize all results into a comprehensive event plan

## The Event Planning Team

| Agent | Framework | Role |
|-------|-----------|------|
| Entertainment Planner | ADK | Find entertainment |
| Venue Scout | CrewAI | Find event venues |
| Invitations Manager | Dapr Agents | Send guest invitations |
| **Event Coordinator** | Dapr Agents | Orchestrate all agents |
| Schedule Planner | LangGraph | Check venue availability |
| Catering Coordinator | OpenAI Agents | Find catering options |
| Decoration Planner | Pydantic AI | Find decoration packages |
| Budget Analyst | Strands | Calculate event budgets |

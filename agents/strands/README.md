# Strands Agent Quickstart - Budget Analyst

This quickstart demonstrates how to run a Strands agent as a durable Dapr Workflow using the Diagrid Python SDK. The agent acts as a **Budget Analyst** that calculates costs and creates budget breakdowns for events.

## What This Quickstart Demonstrates

- **Strands + Dapr Workflows**: Run a Strands agent with durable execution and automatic state persistence
- **Direct LLM Integration**: Calls OpenAI directly via the Strands SDK (no Dapr conversation component needed)
- **Tool Integration**: Budget calculation tool with mock cost breakdowns
- **REST API**: Trigger agent workflows via HTTP endpoints
- **Agent Registry**: Auto-registration in a shared agent registry for orchestration

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [Python 3.10+](https://www.python.org/downloads/)
3. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

```bash
cd strands

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### Set your API key

This quickstart uses OpenAI, but you can use any LLM provider supported by Strands.

```bash
export OPENAI_API_KEY="your-key-here"
```

## Running the Quickstart

### 1. Deploy and Run

```bash
diagrid login
diagrid dev run -f dev-python-strands.yaml
```

### 2. Trigger a Workflow

From another terminal:

```bash
curl -i -X POST http://localhost:8004/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Calculate the budget for a corporate event with venue, catering, and entertainment"}'
```

The agent will:
1. Receive the budget request
2. Use the `calculate_budget` tool to create a cost breakdown
3. Return a detailed budget with line items, totals, and a recommended buffer

## Crash Recovery Test

The `crash_test.py` file demonstrates durable crash recovery — a capability not offered by Strands natively. It defines 3 tools where tool 2 crashes with `os._exit(1)`:

1. **step_one_calculate** — calculates initial budget (completes successfully)
2. **step_two_analyze** — analyzes costs (crashes before completing)
3. **step_three_finalize** — finalizes the budget report

### First run — trigger and crash

```bash
diagrid dev run -f dev-crash-test.yaml
```

Wait for `Runner started — ready to accept requests`, then from another terminal:

```bash
curl -X POST http://localhost:8001/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Calculate a budget for a corporate retreat with venue, catering, and entertainment"}'
```

You'll see tool 1 complete and the process crash at tool 2.

### Fix and resume

Open `crash_test.py` and comment out the crash line:

```python
# os._exit(1)  # 💥 Simulates a crash — comment out this line before the second run
```

Restart the application:

```bash
diagrid dev run -f dev-crash-test.yaml
```

The workflow **resumes from tool 2** — tool 1 is not re-executed. The Dapr workflow engine replays the saved result from Catalyst instead of re-running the tool.

## Part of the Event Planning Team

This agent is one of 7 agents in the **Event Planning Team** orchestration scenario. When running together with the orchestrator, the Budget Analyst handles all cost estimation tasks delegated by the Event Coordinator.

See the [Orchestrator README](../dapr-agents/orchestrator/README.md) to run all agents together.

| Agent | Framework | Role |
|-------|-----------|------|
| Venue Scout | CrewAI | Find event venues |
| Catering Coordinator | OpenAI Agents | Find catering options |
| Entertainment Planner | ADK | Find entertainment |
| **Budget Analyst** | Strands | Calculate event budgets |
| Schedule Planner | LangGraph | Check venue availability |
| Invitations Manager | Dapr Agents | Send guest invitations |
| Event Coordinator | Dapr Agents | Orchestrate all agents |

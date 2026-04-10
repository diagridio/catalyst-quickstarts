# LangGraph Quickstart - Schedule Planner

This quickstart demonstrates how to run a LangGraph graph as a durable Dapr Workflow using the Diagrid Python SDK. The agent acts as a **Schedule Planner** that checks venue availability and helps create event timelines.

## What This Quickstart Demonstrates

- **LangGraph + Dapr Workflows**: Run a compiled LangGraph StateGraph with durable execution per node
- **Direct LLM Integration**: Calls OpenAI directly via `langchain-openai` (no Dapr conversation component needed)
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
python -m venv .venv
source .venv/bin/activate  # On macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### Set your API key

This quickstart uses OpenAI, but you can use any LLM provider supported by LangGraph.

```bash
export OPENAI_API_KEY="your-key-here"
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

## Crash Recovery Test

The `crash_test.py` file demonstrates durable crash recovery — a capability not offered by LangGraph natively. It defines a 3-node graph where node 2 crashes with `os._exit(1)`:

1. **check_venues** — checks venue availability (completes successfully)
2. **compare_options** — compares options (crashes before completing)
3. **confirm_booking** — confirms the booking

### First run — trigger and crash

```bash
diagrid dev run -f dev-crash-test.yaml
```

Wait for `Runner started — ready to accept requests`, then from another terminal:

```bash
curl -X POST http://localhost:8001/run \
  -H "Content-Type: application/json" \
  -d '{"topic": "company gala on March 15"}'
```

You'll see step 1 complete and the process crash at step 2.

### Fix and resume

Open `crash_test.py` and comment out the crash line:

```python
# os._exit(1)  # 💥 Simulates a crash — comment out this line before the second run
```

Restart the application:

```bash
diagrid dev run -f dev-crash-test.yaml
```

The workflow **resumes from step 2** — step 1 is not re-executed. The Dapr workflow engine replays the saved result from Catalyst instead of re-running the node.

## Part of the Event Planning Team

This agent is one of 7 agents in the **Event Planning Team** orchestration scenario. When running together with the orchestrator, the Schedule Planner handles all scheduling and availability tasks delegated by the Event Coordinator.

See the [Orchestrator README](../dapr-agents/orchestrator/README.md) to run all agents together.

| Agent | Framework | Role |
|-------|-----------|------|
| Venue Scout | CrewAI | Find event venues |
| Catering Coordinator | OpenAI Agents | Find catering options |
| Entertainment Planner | ADK | Find entertainment |
| Budget Analyst | Strands | Calculate event budgets |
| **Schedule Planner** | LangGraph | Check venue availability |
| Invitations Manager | Dapr Agents | Send guest invitations |
| Event Coordinator | Dapr Agents | Orchestrate all agents |

# OpenAI Agents Quickstart - Catering Coordinator

This quickstart demonstrates how to run an OpenAI Agents SDK agent as a durable Dapr Workflow using the Diagrid Python SDK. The agent acts as a **Catering Coordinator** that finds catering options based on cuisine type and guest count.

## What This Quickstart Demonstrates

- **OpenAI Agents SDK + Dapr Workflows**: Run an OpenAI agent with durable execution and automatic state persistence
- **Direct LLM Integration**: Calls OpenAI directly via the OpenAI Agents SDK (no Dapr conversation component needed)
- **Tool Integration**: Catering search tool with mock results
- **REST API**: Trigger agent workflows via HTTP endpoints
- **Agent Registry**: Auto-registration in a shared agent registry for orchestration

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [Python 3.10+](https://www.python.org/downloads/)
3. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

```bash
cd openai-agents

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### Set your API key

This quickstart uses OpenAI, but you can use any LLM provider supported by the OpenAI Agents SDK.

```bash
export OPENAI_API_KEY="your-key-here"
```

## Running the Quickstart

### 1. Deploy and Run

```bash
diagrid login
diagrid dev run -f dev-python-openai.yaml
```

### 2. Trigger a Workflow

From another terminal:

```bash
curl -i -X POST http://localhost:8002/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Find catering for 50 people, Italian cuisine"}'
```

The agent will:
1. Receive the catering request
2. Use the `search_catering` tool to find available options
3. Return catering options with pricing for the requested cuisine and guest count

## Crash Recovery Test

The `crash_test.py` file demonstrates durable crash recovery — a capability not offered by the OpenAI Agents SDK natively. It defines 3 tools where tool 2 crashes with `os._exit(1)`:

1. **step_one_search** — searches for catering options (completes successfully)
2. **step_two_compare** — compares options (crashes before completing)
3. **step_three_confirm** — confirms the booking

### First run — trigger and crash

```bash
diagrid dev run -f dev-crash-test.yaml
```

Wait for `Runner started — ready to accept requests`, then from another terminal:

```bash
curl -X POST http://localhost:8001/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Find catering for a corporate gala"}'
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

This agent is one of 7 agents in the **Event Planning Team** orchestration scenario. When running together with the orchestrator, the Catering Coordinator handles all food and beverage tasks delegated by the Event Coordinator.

See the [Orchestrator README](../dapr-agents/orchestrator/README.md) to run all agents together.

| Agent | Framework | Role |
|-------|-----------|------|
| Venue Scout | CrewAI | Find event venues |
| **Catering Coordinator** | OpenAI Agents | Find catering options |
| Entertainment Planner | ADK | Find entertainment |
| Budget Analyst | Strands | Calculate event budgets |
| Schedule Planner | LangGraph | Check venue availability |
| Invitations Manager | Dapr Agents | Send guest invitations |
| Event Coordinator | Dapr Agents | Orchestrate all agents |

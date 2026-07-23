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

1. [Diagrid CLI](https://docs.diagrid.io/references/catalyst/catalyst-cli-intro/) installed
2. [Python 3.11–3.13](https://www.python.org/downloads/)
3. [uv](https://docs.astral.sh/uv/getting-started/installation/) installed
4. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

Navigate to the `langgraph` directory and install the dependencies using `uv`:

```bash
cd agents/langgraph
uv sync
```

### Set your API key

This quickstart uses OpenAI, but you can use any LLM provider supported by LangGraph.

**macOS/Linux (bash/zsh):**

```bash
export OPENAI_API_KEY="your-key-here"
```

**Windows (PowerShell):**

```powershell
$env:OPENAI_API_KEY = "your-key-here"
```

## Run with Catalyst

### 1. Login and Run

1. Login to Catalyst using the Diagrid CLI:

```bash
diagrid login
```

2. Create a new Catalyst project for the quickstart and use it as the default project for the current session:

```bash
diagrid project create langgraph-quickstart --enable-agent-infrastructure --wait --use
```

3. Create an agent for the project:

```bash
diagrid agent create langgraph-agent --wait
```

4. Run the graph with Catalyst:

```bash
uv run diagrid dev run -f dev-python-langgraph.yaml --approve
```

Wait until the output shows `Uvicorn running on <localhost:port>`.

### 2. Trigger a Workflow

From another terminal:

Choose one of the following to trigger the endpoint:

**macOS/Linux (curl):**

```bash
curl -i -X POST http://localhost:8005/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Check if the Grand Ballroom is available on March 15th"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8005/agent/run' -ContentType 'application/json' -Body '{"task": "Check if the Grand Ballroom is available on March 15th"}'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the request. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension.

The agent will:
1. Receive the scheduling request
2. Call the LLM to determine the right tool call
3. Use the `check_availability` tool to check venue availability
4. Return available time slots for the requested date

### 3. Inspecting the Results in Catalyst

Open the [Catalyst dashboard](https://catalyst.diagrid.io/agents) in your browser and navigate to Agents > schedule-planner. Then select the most recent agent workflow run to view output.

## Crash Recovery Test With Catalyst

The `crash_test.py` file demonstrates durable crash recovery — a capability not offered by LangGraph natively. It defines a 3-node graph where node 2 crashes with `os._exit(1)`:

1. **check_venues** — checks venue availability (completes successfully)
2. **compare_options** — compares options (crashes before completing)
3. **confirm_booking** — confirms the booking

### 1. First run — trigger and crash

```bash
uv run diagrid dev run -f dev-crash-test.yaml --approve
```

Wait for `Uvicorn running on <localhost:port>`, then from another terminal:

Choose one of the following to trigger the endpoint:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:8001/run \
  -H "Content-Type: application/json" \
  -d '{"topic": "company gala on March 15"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/run' -ContentType 'application/json' -Body '{"topic": "company gala on March 15"}'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the request. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension.

Go to the terminal where you started `uv run diagrid dev run`. You'll see step 1 complete and the process crash at step 2.

```text
== APP - langgraph-crash-test == >>> STEP 1: Checking venue availability for 'company gala on March 15'...
== APP - langgraph-crash-test == >>> STEP 1 COMPLETE: Grand Ballroom available on March 15 (2PM-6PM, 6PM-11PM)
...
== APP - langgraph-crash-test == >>> STEP 2: Comparing venue options...
❌ App process "langgraph-crash-test" exited with error code: exit status 1
```

### 2. Fix and resume

Open `crash_test.py` and comment out the crash line (line 30):

```python
# os._exit(1)  # 💥 Simulates a crash — comment out this line before the second run
```

Restart the application:

```bash
uv run diagrid dev run -f dev-crash-test.yaml
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

# ADK Agent Quickstart - Entertainment Planner

This quickstart demonstrates how to run a Google ADK (Agent Development Kit) agent as a durable Dapr Workflow using the Diagrid Python SDK. The agent acts as an **Entertainment Planner** that finds entertainment options for events.

## What This Quickstart Demonstrates

- **Google ADK + Dapr Workflows**: Run an ADK LlmAgent with durable execution and automatic state persistence
- **Direct LLM Integration**: Calls Google AI directly via the ADK SDK (no Dapr conversation component needed)
- **Tool Integration**: Entertainment search tool with mock results
- **REST API**: Trigger agent workflows via HTTP endpoints
- **Agent Registry**: Auto-registration in a shared agent registry for orchestration

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/references/catalyst/catalyst-cli-intro/) installed
2. [Python 3.11–3.13](https://www.python.org/downloads/)
3. [uv](https://docs.astral.sh/uv/getting-started/installation/) installed
4. A [Google API key](https://aistudio.google.com/)

## Setup

Navigate to the `adk` directory and install the dependencies using `uv`:

```bash
cd agents/adk
uv sync
```

### Set your API key

**macOS/Linux (bash/zsh):**

```bash
export GOOGLE_API_KEY="your-key-here"
```

**Windows (PowerShell):**

```powershell
$env:GOOGLE_API_KEY = "your-key-here"
```

## Running the Quickstart

### 1. Login and Run

1. Login to Catalyst using the Diagrid CLI:

```bash
diagrid login
```

2. Create a new Catalyst project for the quickstart and use it as the default project for the current session:

```bash
diagrid project create adk-quickstart --enable-agent-infrastructure --wait --use
```

3. Create an agent for the project:

```bash
diagrid agent create adk-agent --wait
```

4. Run the agent with Catalyst:

```bash
uv run diagrid dev run -f dev-python-adk.yaml --approve
```

Wait until the output shows `Uvicorn running on <localhost:port>`.

### 2. Trigger a Workflow

From another terminal:

Choose one of the following to trigger the endpoint:

**macOS/Linux (curl):**

```bash
curl -i -X POST http://localhost:8003/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Find entertainment for a corporate networking event"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8003/agent/run' -ContentType 'application/json' -Body '{"task": "Find entertainment for a corporate networking event"}'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the request. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension.

The agent will:
1. Receive the entertainment request
2. Use the `find_entertainment` tool to search for options
3. Return entertainment options with pricing and duration details

### 3. Inspecting the Results in Catalyst

Open the [Catalyst dashboard](https://catalyst.diagrid.io/agents) in your browser and navigate to Agents > entertainment-planner. Then select the most recent agent workflow run to view output.

## Crash Recovery Test With Catalyst

The `crash_test.py` file demonstrates durable crash recovery — a capability not offered by Google ADK natively. It defines 3 tools where tool 2 crashes with `os._exit(1)`:

1. **step_one_find** — finds entertainment options (completes successfully)
2. **step_two_compare** — compares options (crashes before completing)
3. **step_three_confirm** — confirms the booking

### First run — trigger and crash

```bash
uv run diagrid dev run -f dev-crash-test.yaml --approve
```

Wait for `Uvicorn running on <localhost:port>`, then from another terminal:

Choose one of the following to trigger the endpoint:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:8001/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Find entertainment for a corporate holiday party"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/run' -ContentType 'application/json' -Body '{"prompt": "Find entertainment for a corporate holiday party"}'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the request. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension.

You'll see tool 1 complete and the process crash at tool 2.

### Fix and resume

Open `crash_test.py` and comment out the crash line:

```python
# os._exit(1)  # 💥 Simulates a crash — comment out this line before the second run
```

Restart the application:

```bash
uv run diagrid dev run -f dev-crash-test.yaml
```

The workflow **resumes from tool 2** — tool 1 is not re-executed. The Dapr workflow engine replays the saved result from Catalyst instead of re-running the tool.

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

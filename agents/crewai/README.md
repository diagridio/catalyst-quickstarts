# CrewAI Agent Quickstart - Venue Scout

This quickstart demonstrates how to run a CrewAI agent as a durable Dapr Workflow using the Diagrid Python SDK. The agent acts as a **Venue Scout** that searches for event venues based on city, capacity, and budget.

## What This Quickstart Demonstrates

- **CrewAI + Dapr Workflows**: Run a CrewAI agent with durable execution and automatic state persistence
- **Direct LLM Integration**: Calls OpenAI directly via the CrewAI SDK (no Dapr conversation component needed)
- **Tool Integration**: Venue search tool with mock results
- **REST API**: Trigger agent workflows via HTTP endpoints
- **Agent Registry**: Auto-registration in a shared agent registry for orchestration

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [Python 3.10+](https://www.python.org/downloads/)
3. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

**macOS/Linux (bash/zsh):**

```bash
cd crewai

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Windows (PowerShell):**

```powershell
cd crewai

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### Set your API key

This quickstart uses OpenAI, but you can use any LLM provider supported by CrewAI.

**macOS/Linux (bash/zsh):**

```bash
export OPENAI_API_KEY="your-key-here"
```

**Windows (PowerShell):**

```powershell
$env:OPENAI_API_KEY = "your-key-here"
```

## Running the Quickstart

### 1. Deploy and Run

```bash
diagrid login
diagrid dev run -f dev-python-crewai.yaml
```

### 2. Trigger a Workflow

From another terminal:

Choose one of the following to trigger the endpoint:

**macOS/Linux (curl):**

```bash
curl -i -X POST http://localhost:8001/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Find a venue in Austin for 50 people"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/agent/run' -ContentType 'application/json' -Body '{"task": "Find a venue in Austin for 50 people"}'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the request. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension.

The agent will:
1. Receive the venue search request
2. Use the `search_venues` tool to find available venues
3. Return venue options with pricing and capacity details

## Crash Recovery Test

The `crash_test.py` file demonstrates durable crash recovery — a capability not offered by CrewAI natively. It defines 3 tools where tool 2 crashes with `os._exit(1)`:

1. **step_one_search** — searches for venues (completes successfully)
2. **step_two_compare** — compares venues (crashes before completing)
3. **step_three_confirm** — confirms the booking

### First run — trigger and crash

```bash
diagrid dev run -f dev-crash-test.yaml
```

Wait for `Runner started — ready to accept requests`, then from another terminal:

Choose one of the following to trigger the endpoint:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:8001/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Find a venue in Austin for a company gala"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/run' -ContentType 'application/json' -Body '{"prompt": "Find a venue in Austin for a company gala"}'
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
diagrid dev run -f dev-crash-test.yaml
```

The workflow **resumes from tool 2** — tool 1 is not re-executed. The Dapr workflow engine replays the saved result from Catalyst instead of re-running the tool.

## Part of the Event Planning Team

This agent is one of 7 agents in the **Event Planning Team** orchestration scenario. When running together with the orchestrator, the Venue Scout handles all venue-related tasks delegated by the Event Coordinator.

See the [Orchestrator README](../dapr-agents/orchestrator/README.md) to run all agents together.

| Agent | Framework | Role |
|-------|-----------|------|
| **Venue Scout** | CrewAI | Find event venues |
| Catering Coordinator | OpenAI Agents | Find catering options |
| Entertainment Planner | ADK | Find entertainment |
| Budget Analyst | Strands | Calculate event budgets |
| Schedule Planner | LangGraph | Check venue availability |
| Invitations Manager | Dapr Agents | Send guest invitations |
| Event Coordinator | Dapr Agents | Orchestrate all agents |

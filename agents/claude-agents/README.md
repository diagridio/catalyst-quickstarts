# Claude Agents Quickstart - Photography Planner

This quickstart demonstrates how to run a [Claude Agent SDK](https://docs.claude.com/en/api/agent-sdk/overview) agent as a durable Dapr Workflow using the Diagrid Python SDK. The agent acts as a **Photography Planner** that finds photography and videography packages based on event type and coverage hours.

## What This Quickstart Demonstrates

- **Claude Agent SDK + Dapr Workflows**: Run a Claude agent with durable execution and automatic state persistence
- **Direct LLM Integration**: Calls Anthropic directly via the Claude Agent SDK (no Dapr conversation component needed)
- **Per-step durability**: Each LLM turn and each tool call runs as a separate Dapr workflow activity, so a crash mid-iteration resumes from the last checkpoint
- **Tool Integration**: Photography search tool with mock results
- **REST API**: Trigger agent workflows via HTTP endpoints
- **Agent Registry**: Auto-registration in a shared agent registry for orchestration

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [Python 3.11–3.13](https://www.python.org/downloads/) (the Diagrid SDK does not yet support 3.14)
3. An [Anthropic API key](https://console.anthropic.com/settings/keys)

## Setup

**macOS/Linux (bash/zsh):**

```bash
cd claude-agents

# Create and activate virtual environment
python3.13 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Windows (PowerShell):**

```powershell
cd claude-agents

# Create and activate virtual environment
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### Set your API key

This quickstart uses Anthropic Claude. You can change the model with the optional `CLAUDE_MODEL` environment variable (defaults to `claude-sonnet-4-6`).

**macOS/Linux (bash/zsh):**

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

**Windows (PowerShell):**

```powershell
$env:ANTHROPIC_API_KEY = "your-key-here"
```

## Running the Quickstart

### 1. Deploy and Run

```bash
diagrid login
diagrid dev run -f dev-python-claude.yaml
```

### 2. Trigger a Workflow

From another terminal:

Choose one of the following to trigger the endpoint:

**macOS/Linux (curl):**

```bash
curl -i -X POST http://localhost:8010/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Find photography for a wedding, 8 hours of coverage"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8010/agent/run' -ContentType 'application/json' -Body '{"task": "Find photography for a wedding, 8 hours of coverage"}'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the request. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension.

The agent will:
1. Receive the photography request
2. Use the `search_photography` tool to find available packages
3. Return photography options with pricing for the requested event type and coverage hours

## Crash Recovery Test

The `crash_test.py` file demonstrates durable crash recovery — a capability not offered by the Claude Agent SDK natively. It defines 3 tools where tool 2 crashes with `os._exit(1)`:

1. **step_one_search** — searches for photography options (completes successfully)
2. **step_two_compare** — compares options (crashes before completing)
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
  -d '{"prompt": "Find photography for a corporate gala"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/run' -ContentType 'application/json' -Body '{"prompt": "Find photography for a corporate gala"}'
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

This agent follows the same durable-runner pattern as the other specialists and can join the **Event Planning Team** orchestration scenario as a Claude-powered Photography Planner, handling photography and videography tasks delegated by the Event Coordinator.

See the [Orchestrator README](../dapr-agents/orchestrator/README.md) to run the agents together.

| Agent | Framework | Role |
|-------|-----------|------|
| Venue Scout | CrewAI | Find event venues |
| Catering Coordinator | OpenAI Agents | Find catering options |
| Entertainment Planner | ADK | Find entertainment |
| Budget Analyst | Strands | Calculate event budgets |
| Schedule Planner | LangGraph | Check venue availability |
| Invitations Manager | Dapr Agents | Send guest invitations |
| **Photography Planner** | Claude Agents | Find photography & videography |
| Event Coordinator | Dapr Agents | Orchestrate all agents |

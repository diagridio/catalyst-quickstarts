# Deep Agents Quickstart - Transportation Planner

This quickstart demonstrates how to run a Deep Agents agent as a durable Dapr Workflow using the Diagrid Python SDK. The agent acts as a **Transportation Planner** that finds transportation options based on event type and guest count.

## What This Quickstart Demonstrates

- **Deep Agents + Dapr Workflows**: Run a Deep Agents agent with durable execution and automatic state persistence
- **Direct LLM Integration**: Calls OpenAI directly via `langchain-openai` (no Dapr conversation component needed)
- **Tool Integration**: Transportation search tool with mock results
- **Pub/Sub Messaging**: Subscribe to a request topic and publish results for event-driven orchestration
- **REST API**: Trigger agent workflows via HTTP endpoints
- **Durable Crash Recovery**: Resume a workflow from the last completed step after a crash (see [Crash Recovery Test With Catalyst](#crash-recovery-test-with-catalyst))
- **Sub-Agent Workflows**: Supervisor/sub-agent orchestration over the Agent Protocol (see [Sub-Agent Workflows](#sub-agent-workflows))

### Role

- **Agent**: `deepagents-agent`
- **Port**: 8009
- **Subscribe topic**: `transportation.requests`
- **Publish topic**: `transportation.results`

### Tools

- `search_transportation(event_type, guest_count)` — Searches for transportation options matching the given event type and guest count.

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/references/catalyst/catalyst-cli-intro/) installed
2. [Python 3.12–3.13](https://www.python.org/downloads/)
3. [uv](https://docs.astral.sh/uv/getting-started/installation/) installed
4. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

Navigate to the `deepagents` directory and install the dependencies using `uv`:

```bash
cd agents/deepagents
uv sync
```

### Set your API key

This quickstart uses OpenAI, but you can use any LLM provider supported by Deep Agents.

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
diagrid project create deepagents-quickstart --enable-agent-infrastructure --wait --use
```

3. Create an agent for the project:

```bash
diagrid agent create deepagents-agent --wait
```

4. Run the agent with Catalyst:

```bash
uv run diagrid dev run -f dev-python-deepagents.yaml --approve
```

Wait until the output shows `Uvicorn running on <localhost:port>`.

### 2. Trigger a Workflow

Choose one of the following to trigger the endpoint:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:8888/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Find transportation for a corporate gala with 200 guests"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8888/agent/run' -ContentType 'application/json' -Body '{"task": "Find transportation for a corporate gala with 200 guests"}'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the request. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension.

### 3. Inspecting the Results in Catalyst

Open the [Catalyst dashboard](https://catalyst.diagrid.io/agents) in your browser and navigate to Agents > transportation-planner. Then select the most recent agent workflow run to view output.

## Crash Recovery Test With Catalyst

The `crash_test.py` file demonstrates durable crash recovery — a capability powered by Dapr Workflows. It defines 3 tools where tool 2 crashes with `os._exit(1)`:

1. **step_one_search** — searches for transportation options (completes successfully)
2. **step_two_compare** — compares options (crashes before completing)
3. **step_three_confirm** — confirms the selection

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
  -d '{"prompt": "Find transportation for a corporate gala"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/run' -ContentType 'application/json' -Body '{"prompt": "Find transportation for a corporate gala"}'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the request. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension.

You'll see tool 1 complete and the process crash at tool 2.

### 2. Fix and resume

Open `crash_test.py` and comment out the crash line:

```python
# os._exit(1)  # 💥 Simulates a crash — comment out this line before the second run
```

Restart the application:

```bash
uv run diagrid dev run -f dev-crash-test.yaml --approve
```

The workflow **resumes from tool 2** — tool 1 is not re-executed. The Dapr workflow engine replays the saved result from Catalyst instead of re-running the tool.

## Sub-Agent Workflows

The `subagent_workflows.py` file demonstrates a supervisor/sub-agent pattern where a supervisor agent orchestrates two sub-agents (researcher and analyst) that each run as independent Dapr workflow-backed processes communicating over the Agent Protocol.

- **Researcher** — searches the web for information on a topic and returns a summary
- **Analyst** — takes research findings and produces a structured analysis report
- **Supervisor** — orchestrates the researcher and analyst sequentially, then synthesizes their results

### Run

```bash
uv run diagrid dev run -f dev-subagent-workflows.yaml --approve
```

This starts three processes:
- `deepagents-researcher` on port 8001
- `deepagents-analyst` on port 8002
- `deepagents-supervisor` which delegates to the other two

The supervisor automatically runs the research and analysis pipeline on startup and prints the final synthesized response.

# ADK Agent Quickstart - Entertainment Planner

This quickstart demonstrates how to run a Google ADK (Agent Development Kit) agent as a durable Dapr Workflow using the Diagrid Python SDK. The agent acts as an **Entertainment Planner** that finds entertainment options for events.

## What This Quickstart Demonstrates

- **Google ADK + Dapr Workflows**: Run an ADK LlmAgent with durable execution and automatic state persistence
- **Direct LLM Integration**: Calls OpenAI through ADK's LiteLLM model wrapper (no Dapr conversation component needed)
- **Tool Integration**: Entertainment search tool with mock results
- **REST API**: Trigger agent workflows via HTTP endpoints
- **Agent Registry**: Auto-registration in a shared agent registry for orchestration

## Prerequisites

1. A [Diagrid Catalyst account](https://catalyst.diagrid.io/)
2. [Diagrid CLI](https://docs.diagrid.io/getting-started/install-cli) installed
3. [Python 3.11–3.13](https://www.python.org/downloads/)
4. [uv](https://docs.astral.sh/uv/getting-started/installation/) installed
5. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

Navigate to the `adk` directory and install the dependencies using `uv`:

```bash
cd agents/adk
uv sync
```

### Set your API key

The agent is a standard ADK `LlmAgent` that reaches OpenAI through ADK's LiteLLM wrapper (`LiteLlm(model="openai/gpt-4o-mini")`), so this quickstart needs only an `OPENAI_API_KEY` and no Google credentials.

**macOS/Linux (bash/zsh):**

```bash
export OPENAI_API_KEY="your-key-here"
```

**Windows (PowerShell):**

```powershell
$env:OPENAI_API_KEY = "your-key-here"
```

## Running the Quickstart

### 1. Login and Run

1. Login to Catalyst using the Diagrid CLI:

```bash
diagrid login
```

2. Create a new Catalyst project for the quickstart and use it as the default project for the current session:

```bash
diagrid project create adk-quickstart --enable-managed-workflow --deploy-managed-kv --deploy-managed-pubsub --wait --use
```

3. Create an agent for the project:

```bash
diagrid agent create entertainment-planner --wait
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

The `crash_test.py` file demonstrates durable crash recovery, a capability not offered by Google ADK natively. It defines 3 tools, where tool 2 deliberately takes about 10 seconds, and a `POST /crash/kill` endpoint that kills the process outright. Nothing is armed: the crash is a request you make, so there is no source edit, no environment variable to unset, and no second run file.

1. **step_one_find**: finds entertainment options. Instant, and completes
2. **step_two_compare**: compares options over ~10 seconds. Kill the app during this
3. **step_three_confirm**: confirms the booking. Instant

The tool order is the point. `step_one_find` completes and Catalyst records its result before `step_two_compare` starts, so the crash lands between two known points and the restart can show that only the interrupted tool ran again. Each tool logs itself as `TOOL 1`, `TOOL 2` and `TOOL 3`, which is how you follow it in the app log.

You also choose the workflow instance ID, so you can find the same run again from a second request or in the Catalyst console.

### 4. Start the app

This is a second app (`crash_test.py`, not `main.py`), so stop the run from step 1 if it is still going: both dev-run files use the same `entertainment-planner` app ID.

```bash
uv run diagrid dev run -f dev-crash-test.yaml --approve
```

Wait for `Uvicorn running on http://0.0.0.0:8001`. The port is pinned in `dev-crash-test.yaml`, so the `localhost:8001` requests below always work as written.

### 5. Run under an ID you own

From another terminal. This request blocks for about 10 seconds while `step_two_compare` runs.

Choose one of the following to trigger the endpoint:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:8001/crash/run \
  -H "Content-Type: application/json" \
  -d '{"id": "party-42", "prompt": "Find entertainment for a corporate holiday party"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/crash/run' -ContentType 'application/json' -Body '{"id": "party-42", "prompt": "Find entertainment for a corporate holiday party"}'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the *Crash Recovery: run the agent under an ID you own* request. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension.

Go to the terminal where you started `uv run diagrid dev run`. `step_one_find` completes and `step_two_compare` announces its window:

```text
== APP - entertainment-planner == >>> TOOL 1: Finding entertainment for '...'...
== APP - entertainment-planner == >>> TOOL 1 COMPLETE: Found 3 entertainment options for ...
== APP - entertainment-planner == >>> TOOL 2: Comparing options over ~10s. KILL THE APP NOW to test crash recovery (POST /crash/kill, or kill -9). It resumes on restart.
```

**Two terminals instead of three.** The request takes an optional `kill_after_seconds`. Send it and the app halts *itself* that many seconds into the run, at a known point inside `step_two_compare`'s window, so you never have to aim a kill at a moving target:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:8001/crash/run \
  -H "Content-Type: application/json" \
  -d '{"id": "party-42", "prompt": "Find entertainment for a corporate holiday party", "kill_after_seconds": 8}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/crash/run' -ContentType 'application/json' -Body '{"id": "party-42", "prompt": "Find entertainment for a corporate holiday party", "kill_after_seconds": 8}'
```

Send this instead of the request above and skip step 6: the app crashes on its own. Leave the field out and nothing changes, and you crash the app yourself. Either way the rest of the walkthrough is identical.

With the field set, step 2 announces the self-kill instead of asking you to kill the app, and the process exits 8 seconds into `step_two_compare`. The request then reports a connection reset, which is exactly what a real crash looks like:

```text
== APP - entertainment-planner == >>> TOOL 1: Finding entertainment for '...'...
== APP - entertainment-planner == >>> TOOL 1 COMPLETE: Found 3 entertainment options for ...
== APP - entertainment-planner == >>> TOOL 2: Comparing options over ~10s, but this process kills itself 8s into the run, as asked by kill_after_seconds. It resumes on restart.
== APP - entertainment-planner == >>> crash: killing this process 8s into the run, as asked by kill_after_seconds
```

Keep the value below `CRASH_DELAY_SECONDS` (10 by default) so the crash lands inside `step_two_compare` rather than after the agent has finished. The clock starts when `step_two_compare` starts, not when the request arrives, so the budget is measured against that tool's own sleep and does not have to cover the model turn and `step_one_find` ahead of it. That is also why the field is safe to send on the re-issue in step 8: the timer only starts when the tool actually runs, and a call that attaches to an existing run replays the recorded result instead of re-invoking it.

### 6. Crash the app

Skip this step if you sent `kill_after_seconds` in step 5. Otherwise, from a third terminal, while `step_two_compare` is still running:

> **`POST /crash/kill` is demo scaffolding. Do not copy it into a real service.**
> It is an unauthenticated endpoint that lets any caller that can reach the port
> terminate the process, and it exists here only to make a crash reproducible on
> demand.

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:8001/crash/kill
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/crash/kill'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the *Crash Recovery: kill the app* request.

The endpoint calls `os._exit(1)`, so the process is gone before it can answer and this request itself reports a connection reset rather than a status code. That is expected: a process that answers politely has not crashed. The blocked request from step 5 sees a reset too.

```text
== APP - entertainment-planner == >>> /crash/kill: killing this process to simulate a worker crash
```

The workflow instance `party-42` is unaffected. It lives in Catalyst, not in the process you just killed.

### 7. Restart the app

Restart with the same command as step 4:

```bash
uv run diagrid dev run -f dev-crash-test.yaml --approve
```

**That is the whole recovery. You do not have to send anything.** The run resumes by itself, and no HTTP request is involved: as soon as the restarted app's worker reconnects, Catalyst hands `party-42` back to it, `step_two_compare` starts over from the beginning, and about 10 seconds later the agent finishes. Watch the app log, where all of this happens before you send anything:

```text
== APP - entertainment-planner == >>> TOOL 2: Comparing options over ~10s. KILL THE APP NOW to test crash recovery (POST /crash/kill, or kill -9). It resumes on restart.
== APP - entertainment-planner == >>> TOOL 2 COMPLETE: Live Jazz Band is the best option
== APP - entertainment-planner == >>> TOOL 3: Confirming booking...
== APP - entertainment-planner == >>> TOOL 3 COMPLETE: Entertainment confirmed with Live Jazz Band
```

`step_one_find` is **not** re-executed: its `TOOL 1` lines do not appear a second time. That tool had completed and Catalyst had recorded its result, so the Dapr workflow engine replayed the saved value instead of running the tool again. Only the tool that was interrupted runs twice.

### 8. Collect the answer

The run recovered on its own, but the crash also killed the request that was waiting for its answer, and that answer had nowhere to go. Once the lines above have appeared, send the **identical** request from step 5 once more to open a new connection to the run that already finished. Because the instance already exists, this call attaches to it rather than starting a second one, and the handler says so:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:8001/crash/run \
  -H "Content-Type: application/json" \
  -d '{"id": "party-42", "prompt": "Find entertainment for a corporate holiday party"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/crash/run' -ContentType 'application/json' -Body '{"id": "party-42", "prompt": "Find entertainment for a corporate holiday party"}'
```

```text
== APP - entertainment-planner == >>> Attaching to the existing run party-42 instead of starting a second one
```

That is the last line of the demo. If you send the request earlier, while `step_two_compare` is still re-running, the attach line lands in the middle of the log instead and the call blocks until the agent finishes.

The reply uses the one JSON shape every crash demo in this repo returns, `{"id", "result", "message"}`. If the run has already finished, the recorded final output of the agent comes back in `result` with `message` null, with status `200`. If the wait budget elapses first, the same shape comes back as a `202` with `result` null and the attach instruction in `message`. That is not a failure: send the same request again to attach again.

The length of `step_two_compare` is configurable through the `CRASH_DELAY_SECONDS` environment variable, which defaults to 10. Set it lower to shorten the window, or higher if you need more time to aim.

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

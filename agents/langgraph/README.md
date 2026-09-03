# LangGraph Quickstart - Schedule Planner

This quickstart demonstrates how to run a LangGraph graph as a durable Dapr Workflow using the Diagrid Python SDK. The agent acts as a **Schedule Planner** that checks venue availability and helps create event timelines.

## What This Quickstart Demonstrates

- **LangGraph + Dapr Workflows**: Run a compiled LangGraph StateGraph with durable execution per node
- **Direct LLM Integration**: Runs on a deterministic canned model by default, so no API key is needed; a real provider is opt-in via `langchain-openai` (no Dapr conversation component needed)
- **Tool Integration**: Availability check tool with mock schedule data
- **Conditional Routing**: LangGraph conditional edges for tool-calling loop
- **REST API**: Trigger graph workflows via HTTP endpoints
- **Agent Registry**: Auto-registration in a shared agent registry for orchestration

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/references/catalyst/catalyst-cli-intro/) installed
2. [Python 3.11–3.13](https://www.python.org/downloads/)
3. [uv](https://docs.astral.sh/uv/getting-started/installation/) installed

## Setup

Navigate to the `langgraph` directory and install the dependencies using `uv`:

```bash
cd agents/langgraph
uv sync
```

<!-- The Catalyst console deep-links to this heading's anchor (#using-a-real-llm-provider).
     Renaming this heading breaks that link silently. -->

### Using a real LLM provider

This quickstart runs offline by default. It uses a canned model, needs no API key, and returns the same tool call and the same answer on every run, whatever task you send. To use a real model instead, set `DIAGRID_QUICKSTART_MODEL` to `openai` and export your key. The example below uses OpenAI, but you can use any LLM provider supported by LangGraph.

**macOS/Linux (bash/zsh):**

```bash
export DIAGRID_QUICKSTART_MODEL="openai"
export OPENAI_API_KEY="your-key-here"
```

**Windows (PowerShell):**

```powershell
$env:DIAGRID_QUICKSTART_MODEL = "openai"
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
diagrid project create langgraph-quickstart --enable-managed-workflow --deploy-managed-kv --deploy-managed-pubsub --wait --use
```

3. Create an agent for the project:

```bash
diagrid agent create schedule-planner --wait
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
2. Call the LLM to determine the right tool call. The canned offline model always returns the same fixed tool call and the same answer, whatever task you send. See [Using a real LLM provider](#using-a-real-llm-provider) to run this step against a real model
3. Use the `check_availability` tool to check venue availability
4. Return available time slots for the requested date

In the terminal running `diagrid dev run`, each graph node is executed as a
durable Dapr activity, one per step. The `tools` step is the `check_availability`
call: the graph only reaches it when the LLM decides to call the tool, so its
absence means the agent answered without checking availability.

```text
== APP - schedule-planner ==   [WORKFLOW] Step 0, pending_nodes=['agent']
== APP - schedule-planner ==   [ACTIVITY] Executing node 'agent' as Dapr activity
== APP - schedule-planner ==   [WORKFLOW] Step 1, pending_nodes=['tools']
== APP - schedule-planner ==   [ACTIVITY] Executing node 'tools' as Dapr activity
== APP - schedule-planner ==   [WORKFLOW] Step 2, pending_nodes=['agent']
== APP - schedule-planner ==   [ACTIVITY] Executing node 'agent' as Dapr activity
== APP - schedule-planner ==   [WORKFLOW] Step 3, pending_nodes=['__end__']
== APP - schedule-planner == durabletask-worker INFO: graph-...: Orchestration completed with status: COMPLETED
```

The request blocks until the workflow finishes and returns the run's outcome.
`status` is `completed` only when the workflow ran to completion — a failed run
returns `"type": "workflow_failed"` with an `error` instead, and no `status`.
The `messages` array carries the conversation, including the tool's reply, and
its exact contents vary with the model:

```text
{
  "instance_id": "graph-e356c042-9f2d068b",
  "type": "workflow_completed",
  "workflow_id": "graph-e356c042-9f2d068b",
  "output": { "messages": [ ... ] },
  "steps": 3,
  "status": "completed"
}
```

### 3. Inspecting the Results in Catalyst

Open the [Catalyst dashboard](https://catalyst.diagrid.io/agents) in your browser and navigate to Agents > schedule-planner. Then select the most recent agent workflow run to view output.

## Crash Recovery Test With Catalyst

The `crash_test.py` file demonstrates durable crash recovery, a capability not offered by LangGraph natively. It defines a 3-node graph whose middle node deliberately takes about 30 seconds, and a `POST /crash/kill` endpoint that kills the process outright. Nothing is armed: the crash is a request you make, so there is no source edit, no environment variable to unset, and no second run file.

1. **check_venues**: checks venue availability. Instant, and completes
2. **compare_options**: compares options over ~30 seconds. Kill the app during this
3. **confirm_booking**: confirms the booking. Instant

The node order is the point. `check_venues` completes and Catalyst records its result before `compare_options` starts, so the crash lands between two known points and the restart can show that only the interrupted node ran again. Each node logs itself as `STEP 1`, `STEP 2` and `STEP 3`, which is how you follow it in the app log.

You also choose the workflow instance ID, so you can find the same run again from a second request or in the Catalyst console.

### 4. Start the app

This is a second app (`crash_test.py`, not `main.py`), so stop the run from step 1 if it is still going: both dev-run files use the same `schedule-planner` app ID.

```bash
uv run diagrid dev run -f dev-crash-test.yaml --approve
```

Wait for `Uvicorn running on http://0.0.0.0:8001`. The port is pinned in `dev-crash-test.yaml`, so the `localhost:8001` requests below always work as written.

### 5. Run under an ID you own

From another terminal. This request blocks for about 30 seconds while `compare_options` runs.

Choose one of the following to trigger the endpoint:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:8001/crash/run \
  -H "Content-Type: application/json" \
  -d '{"id": "gala-42", "topic": "company gala on March 15"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/crash/run' -ContentType 'application/json' -Body '{"id": "gala-42", "topic": "company gala on March 15"}'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the *Crash Recovery: run the graph under an ID you own* request. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension.

Go to the terminal where you started `uv run diagrid dev run`. `check_venues` completes and `compare_options` announces its window:

```text
== APP - schedule-planner == >>> STEP 1: Checking venue availability for 'company gala on March 15'...
== APP - schedule-planner == >>> STEP 1 COMPLETE: Grand Ballroom available on March 15 (2PM-6PM, 6PM-11PM)
== APP - schedule-planner == >>> STEP 2: Comparing venue options over ~30s. KILL THE APP NOW to test crash recovery (POST /crash/kill, or kill -9). It resumes on restart.
```

**Two terminals instead of three.** The request takes an optional `kill_after_seconds`. Send it and the app halts *itself* that many seconds into the run, at a known point inside `compare_options`' window, so you never have to aim a kill at a moving target:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:8001/crash/run \
  -H "Content-Type: application/json" \
  -d '{"id": "gala-42", "topic": "company gala on March 15", "kill_after_seconds": 8}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/crash/run' -ContentType 'application/json' -Body '{"id": "gala-42", "topic": "company gala on March 15", "kill_after_seconds": 8}'
```

Send this instead of the request above and skip step 6: the app crashes on its own. Leave the field out and nothing changes, and you crash the app yourself. Either way the rest of the walkthrough is identical.

Keep the value below `CRASH_DELAY_SECONDS` (30 by default) so the crash lands inside `compare_options` rather than after the graph has finished. The clock starts when `compare_options` starts, not when the request arrives, so the budget is measured against that node's own sleep and does not have to cover the model turn and `check_venues` ahead of it. That is also why the field is safe to send on the re-issue in step 8: the timer only starts when the node actually runs, and a call that attaches to an existing run replays the recorded result instead of re-invoking it.

### 6. Crash the app

Skip this step if you sent `kill_after_seconds` in step 5. Otherwise, from a third terminal, while `compare_options` is still running:

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
== APP - schedule-planner == >>> /crash/kill: killing this process to simulate a worker crash
❌ App process "schedule-planner" exited with error code: exit status 1
```

The workflow instance `gala-42` is unaffected. It lives in Catalyst, not in the process you just killed.

### 7. Restart the app

Restart with the same command as step 4:

```bash
uv run diagrid dev run -f dev-crash-test.yaml --approve
```

**That is the whole recovery. You do not have to send anything.** The run resumes by itself, and no HTTP request is involved: as soon as the restarted app's worker reconnects, Catalyst hands `gala-42` back to it, `compare_options` starts over from the beginning, and about 30 seconds later the graph finishes. Watch the app log, where all of this happens before you send anything:

```text
== APP - schedule-planner == >>> STEP 2: Comparing venue options over ~30s. KILL THE APP NOW to test crash recovery (POST /crash/kill, or kill -9). It resumes on restart.
== APP - schedule-planner == >>> STEP 2 COMPLETE: Grand Ballroom (6PM-11PM) is the best option for 200 guests
== APP - schedule-planner == >>> STEP 3: Confirming booking...
== APP - schedule-planner == >>> STEP 3 COMPLETE: Booking confirmed: Grand Ballroom, March 15, 6PM-11PM
```

`check_venues` is **not** re-executed: its `STEP 1` lines do not appear a second time. That node had completed and Catalyst had recorded its result, so the Dapr workflow engine replayed the saved value instead of running the node again. Only the node that was interrupted runs twice.

### 8. Collect the answer

The run recovered on its own, but the crash also killed the request that was waiting for its answer, and that answer had nowhere to go. Once the lines above have appeared, send the **identical** request from step 5 once more to open a new connection to the run that already finished. Because the instance already exists, this call attaches to it rather than starting a second one, and the handler says so:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:8001/crash/run \
  -H "Content-Type: application/json" \
  -d '{"id": "gala-42", "topic": "company gala on March 15"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/crash/run' -ContentType 'application/json' -Body '{"id": "gala-42", "topic": "company gala on March 15"}'
```

```text
== APP - schedule-planner == >>> Attaching to the existing run gala-42 instead of starting a second one
```

That is the last line of the demo. If you send the request earlier, while `compare_options` is still re-running, the attach line lands in the middle of the log instead and the call blocks until the graph finishes.

The reply uses the one JSON shape every crash demo in this repo returns, `{"id", "result", "message"}`. If the run has already finished, the recorded final output of the graph comes back in `result` with `message` null. If the wait budget elapses first, the same shape comes back as a `202` with `result` null and the attach instruction in `message`. That is not a failure: send the same request again to attach again.

The length of `compare_options` is configurable through the `CRASH_DELAY_SECONDS` environment variable, which defaults to 30. Set it lower to shorten the window, or higher if you need more time to aim.

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

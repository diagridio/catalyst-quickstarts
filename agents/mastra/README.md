# Mastra Quickstart - SRE Agent

This quickstart demonstrates how to run a [Mastra](https://mastra.ai) agent as a durable Dapr Workflow using Diagrid Catalyst's TypeScript SDK (`@diagrid/agent-mastra`). The agent acts as an **SRE Agent** that checks service health, calculates error rates, and tracks incident status.

## What This Quickstart Demonstrates

- **Mastra + Dapr Workflows**: Run a Mastra `Agent`'s control loop as a durable Dapr Workflow — every model call and every tool call is a checkpointed activity
- **Direct LLM Integration**: Calls OpenAI directly through Mastra's own model config (a local Ollama model works too — see [Using a local model instead](#using-a-local-model-instead)); no Dapr conversation component needed
- **Tool Integration**: `checkServiceHealth` and `calculateErrorRate` tools, each executed as its own durable activity
- **Durable Crash Recovery**: Resume a workflow from the last completed activity after a crash — a capability not offered by Mastra natively (see [Crash Recovery Test With Catalyst](#crash-recovery-test-with-catalyst))
- **Agent Registry**: Registers as `sre-agent` in Catalyst's agent registry, viewable from the dashboard

### Role

- **Agent**: `sre-agent`

### Tools

- `checkServiceHealth(service)` — Checks a service's current health status (status, latency, uptime).
- `calculateErrorRate(totalRequests, failedRequests)` — Calculates an error rate percentage from request and failure counts.

## Prerequisites

1. A [Diagrid Catalyst account](https://catalyst.diagrid.io/)
2. [Diagrid CLI](https://docs.diagrid.io/getting-started/install-cli) installed
3. [Node.js 22.13 or newer](https://nodejs.org/en/)
4. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

Navigate to the `mastra` directory and install the dependencies:

```bash
cd agents/mastra
npm install
```

### Set your API key

This quickstart uses OpenAI, but you can use any LLM provider Mastra supports.

**macOS/Linux (bash/zsh):**

```bash
export OPENAI_API_KEY="your-key-here"
```

**Windows (PowerShell):**

```powershell
$env:OPENAI_API_KEY = "your-key-here"
```

### Using a local model instead

To run against a local [Ollama](https://ollama.com) model instead of OpenAI — no API key needed:

```bash
ollama serve &
ollama pull qwen3:0.6b
export OLLAMA_ENDPOINT="http://localhost:11434/v1"
export OLLAMA_MODEL="qwen3:0.6b"   # optional, this is the default
```

## Run with Catalyst

### 1. Login and Run

1. Login to Catalyst using the Diagrid CLI:

```bash
diagrid login
```

2. Create a new Catalyst project for the quickstart and use it as the default project for the current session:

```bash
diagrid project create mastra-quickstart --enable-managed-workflow --deploy-managed-kv --wait --use
```

3. Create an agent for the project:

```bash
diagrid agent create sre-agent --wait
```

4. Run the agent with Catalyst:

```bash
diagrid dev run -f dev-mastra.yaml --approve
```

`main.ts` runs one durable agent turn end-to-end: it starts the Dapr Workflow runtime, sends a single prompt through the agent, waits for the result, prints it, and exits. Unlike the Python agent quickstarts in this repo, there's no HTTP server left running and no second terminal needed to trigger anything — the command above is the whole demo.

Expect output like this:

```text
Model: openai/gpt-4o-mini
Starting the Dapr Workflow runtime...
Registered "dapr.mastra.SreAgent.workflow".
============================================================
Status:     completed
Iterations: 2
Answer:     The checkout-api has an error rate of 2.33%. Its current health
status is degraded, with a latency of 842 ms and an uptime of 99.2%.
============================================================
Runtime shut down.
```

`Iterations: 2` is the proof: one model call asks for the `checkServiceHealth` and `calculateErrorRate` tools, then a second turns their results into the answer above. Each of those two model calls and two tool calls is a separate checkpointed Dapr activity — so a process killed mid-turn resumes from the last completed one instead of restarting. See [Crash Recovery Test With Catalyst](#crash-recovery-test-with-catalyst) for a demonstration.

### 2. Inspecting the Results in Catalyst

Open the [Catalyst dashboard](https://catalyst.diagrid.io/agents) in your browser and navigate to Agents > sre-agent. Then select the most recent agent workflow run to view output.

## Crash Recovery Test With Catalyst

The `crash_test.ts` file demonstrates durable crash recovery, a capability not offered by Mastra natively. It serves the agent over HTTP and looks up an incident's status in three steps, each a separate checkpointed Dapr activity:

1. **Model call 1**: asks for the `checkIncidentStatus` tool. Completes and is checkpointed by Catalyst
2. **checkIncidentStatus**: looks up the incident over ~10 seconds. The crash lands here
3. **Model call 2**: turns the tool's result into the answer

The order is the point. Model call 1 completes and Catalyst records its result before `checkIncidentStatus` starts, so the crash lands between two known points and the restart can show that only the interrupted step ran again. Each step logs itself (`>>> Model call 1`, `>>> STEP 2`, `>>> Model call 2`), which is how you follow it in the app log.

You also choose the workflow instance ID, so you can find the same run again from a second request or in the Catalyst console. Nothing is armed in the source: the crash is something you ask for, so there is no source edit and no environment variable to unset.

### 3. Start the app

This is a second app (`crash_test.ts`, not `main.ts`), so stop the run from step 1 if it is still going: both dev-run files use the same `sre-agent` app ID.

```bash
diagrid dev run -f dev-crash-test.yaml --approve
```

Wait for `Crash demo listening on http://0.0.0.0:8001`. The port is pinned in `dev-crash-test.yaml`, so the `localhost:8001` requests below always work as written.

### 4. Run under an ID you own

From another terminal. The request carries `kill_after_seconds`, so the app halts *itself* that many seconds into `checkIncidentStatus`, at a known point inside its window, and you never have to aim a kill at a moving target.

Choose one of the following to trigger the endpoint:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:8001/crash/run \
  -H "Content-Type: application/json" \
  -d '{"id": "inc-4471", "prompt": "What is the status of incident INC-4471?", "kill_after_seconds": 8}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/crash/run' -ContentType 'application/json' -Body '{"id": "inc-4471", "prompt": "What is the status of incident INC-4471?", "kill_after_seconds": 8}'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the *Crash Recovery: run the agent under an ID you own* request. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension.

Go to the terminal where you started `diagrid dev run`. Model call 1 completes, `checkIncidentStatus` announces the self-kill, and the process exits 8 seconds into it:

```text
== APP - sre-agent == >>> Model call 1 for run inc-4471
== APP - sre-agent == >>> STEP 2 checkIncidentStatus: Checking INC-4471 over ~10s, but this process kills itself 8s into the run, as asked by kill_after_seconds. It resumes on restart.
== APP - sre-agent == >>> crash: killing this process 8s into the run, as asked by kill_after_seconds
```

The request then reports a connection reset, which is exactly what a real crash looks like. The workflow instance `inc-4471` is unaffected: it lives in Catalyst, not in the process that just died.

Keep the value below `CRASH_DELAY_SECONDS` (10 by default) so the crash lands inside `checkIncidentStatus` rather than after the agent has finished. The clock starts when `checkIncidentStatus` starts, not when the request arrives, so the budget does not have to cover model call 1 ahead of it. That is also why the field is safe to send again in step 6: the timer only starts when the tool actually runs, and a call that attaches to an existing run never runs it.

### 5. Restart the app

Restart with the same command as step 3:

```bash
diagrid dev run -f dev-crash-test.yaml --approve
```

**That is the whole recovery. You do not have to send anything.** As soon as the restarted app's worker reconnects, Catalyst hands `inc-4471` back to it, `checkIncidentStatus` starts over from the beginning, and about 10 seconds later model call 2 produces the answer. Watch the app log, where all of this happens before you send anything:

```text
== APP - sre-agent == >>> STEP 2 checkIncidentStatus: Checking INC-4471 over ~10s. KILL THE APP NOW to test crash recovery (POST /crash/kill, or kill -9). It resumes on restart.
== APP - sre-agent == >>> STEP 2 COMPLETE: INC-4471 is mitigated, monitoring for recurrence
== APP - sre-agent == >>> Model call 2 for run inc-4471
```

Model call 1 is **not** made again: its `>>> Model call 1` line does not appear a second time. That call had completed and Catalyst had recorded its result, so the Dapr workflow engine replayed the saved value instead of calling the model (and paying for it) again. Only the step that was interrupted runs twice. The restarted process also starts disarmed, so the re-run `checkIncidentStatus` asks you to kill the app rather than killing it again.

### 6. Collect the answer

The run recovered on its own, but the crash also killed the request that was waiting for its answer. Once the lines above have appeared, send the **identical** request from step 4 once more. Because the instance already exists, this call attaches to it rather than starting a second one, and the handler says so:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:8001/crash/run \
  -H "Content-Type: application/json" \
  -d '{"id": "inc-4471", "prompt": "What is the status of incident INC-4471?", "kill_after_seconds": 8}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/crash/run' -ContentType 'application/json' -Body '{"id": "inc-4471", "prompt": "What is the status of incident INC-4471?", "kill_after_seconds": 8}'
```

```text
== APP - sre-agent == >>> Attaching to the existing run inc-4471 instead of starting a second one
== APP - sre-agent == POST /crash/run 200
```

The reply uses the one JSON shape every crash demo in this repo returns, `{"id", "result", "message"}`. If the run has already finished, the agent's final answer comes back in `result` with `message` null, with status `200`. If the wait budget (`CRASH_WAIT_SECONDS`, 120 by default) elapses first, the same shape comes back as a `202` with `result` null and the attach instruction in `message`. That is not a failure: send the same request again to attach again. A request without an `id` is a `400`, and a run that failed or was terminated is a `500` whose `message` names the reason.

### Optional: crash the app yourself

Leave `kill_after_seconds` out and nothing is armed: `checkIncidentStatus` asks you to kill the app instead, and the rest of the walkthrough is identical. Start the run without the field:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:8001/crash/run \
  -H "Content-Type: application/json" \
  -d '{"id": "inc-4472", "prompt": "What is the status of incident INC-4472?"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/crash/run' -ContentType 'application/json' -Body '{"id": "inc-4472", "prompt": "What is the status of incident INC-4472?"}'
```

Then, from a third terminal, while `checkIncidentStatus` is still running:

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

The endpoint calls `process.exit(1)`, so the process is gone before it can answer and this request itself reports a connection reset rather than a status code. That is expected: a process that answers politely has not crashed.

```text
== APP - sre-agent == >>> /crash/kill: killing this process to simulate a worker crash
```

Then restart (step 5) and collect the answer (step 6) with the same body you started this run with.

The length of `checkIncidentStatus` is configurable through the `CRASH_DELAY_SECONDS` environment variable, which defaults to 10. Set it lower to shorten the window, or higher if you need more time to aim.

## Clean Up

Stop the running application with `Ctrl+C`, then delete the Catalyst project:

```bash
diagrid project delete mastra-quickstart
```

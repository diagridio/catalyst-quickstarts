# Microsoft Agent Framework (.NET) Quickstart - Event Planner

This quickstart demonstrates how to run a Microsoft Agent Framework agent as a durable Dapr Workflow using the `Diagrid.AI.Microsoft.AgentFramework` .NET package. The agent acts as an **Event Planner** with three tools that it calls in sequence, the second of which deliberately takes about 30 seconds. That is the window in which you kill the app to prove the run survives it.

## What This Quickstart Demonstrates

- **Microsoft Agent Framework + Dapr Workflows**: Run a .NET agent with durable execution
- **OpenAI via Microsoft.Extensions.AI**: Calls OpenAI directly through the `Microsoft.Extensions.AI.OpenAI` IChatClient
- **Caller-owned instance ID**: Schedule the agent run under an ID you choose, so you can find the same execution again
- **Crash Recovery**: Kill the app mid-tool with a request; on restart, Catalyst resumes the run without redoing the tools that had already completed
- **REST API**: Trigger the agent via an HTTP endpoint

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/references/catalyst/catalyst-cli-intro/) installed
2. [.NET 10 SDK](https://dotnet.microsoft.com/download/dotnet/10.0)
3. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

Navigate to the `microsoft-dotnet` directory and install the dependencies using `dotnet build`:

```bash
cd agents/microsoft-dotnet
dotnet build
```

### Set your API key

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
diagrid project create dotnet-quickstart --enable-managed-workflow --deploy-managed-kv --deploy-managed-pubsub --wait --use
```

3. Create an agent for the project:

```bash
diagrid agent create event-planner --wait
```

4. Run the agent with Catalyst:

```bash
diagrid dev run -f dev-dotnet-agent.yaml --approve
```

Wait until the output shows `Established gRPC bidirectional stream with Dapr sidecar`.

### 2. Trigger the Agent

From another terminal:

Choose one of the following to trigger the endpoint:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:5050/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Find a venue in Austin for a company gala"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:5050/run' -ContentType 'application/json' -Body '{"prompt": "Find a venue in Austin for a company gala"}'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the request. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension.

The agent will:
1. Call `step_one_search`: finds venues. Instant
2. Call `step_two_compare`: compares them over about 30 seconds
3. Call `step_three_confirm`: confirms the booking. Instant

So this request takes about half a minute. You'll see:

```text
== APP - event-planner == >>> TOOL 1: Searching venues in 'Austin'...
== APP - event-planner == >>> TOOL 1 COMPLETE: Found 3 venues
== APP - event-planner == >>> TOOL 2: Comparing venues over ~30s. KILL THE APP NOW to test crash recovery (POST /crash/kill, or kill -9). It resumes on restart.
== APP - event-planner == >>> TOOL 2 COMPLETE: Grand Ballroom is the best option
== APP - event-planner == >>> TOOL 3: Confirming booking...
== APP - event-planner == >>> TOOL 3 COMPLETE: Booking confirmed for Grand Ballroom
```

### 3. Crash Recovery with Catalyst

Every LLM call and every tool call is a separate Dapr workflow activity, so an activity that has already completed is not re-run after a crash. To see that, kill the app while tool 2 is comparing venues.

Two things make the demo legible. You choose the workflow instance ID, so you can find the same execution again. And killing during tool 2, rather than tool 1, means the crash lands *after* a completion Catalyst has already recorded. If tool 1's lines reappeared after the restart, the run would have started over and there would be nothing to see.

Leave the application from step 1 running.

**Start a run under an ID you own.** From another terminal. This request blocks while tool 2 runs:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:5050/crash/run \
  -H "Content-Type: application/json" \
  -d '{"id": "gala-42", "prompt": "Find a venue in Austin for a company gala"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:5050/crash/run' -ContentType 'application/json' -Body '{"id": "gala-42", "prompt": "Find a venue in Austin for a company gala"}'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the *Crash Recovery: run under an ID you own* request.

**Two terminals instead of three.** The request takes an optional `kill_after_seconds`. Send it and the app halts *itself* that many seconds into the run, at a known point inside tool 2's window, so you never have to aim a kill at a moving target:

```bash
curl -X POST http://localhost:5050/crash/run \
  -H "Content-Type: application/json" \
  -d '{"id": "gala-42", "prompt": "Find a venue in Austin for a company gala", "kill_after_seconds": 8}'
```

In PowerShell, add the same `"kill_after_seconds": 8` to the body. Send this instead of the request above and skip the kill step below: the app crashes on its own. Leave the field out and nothing changes, and you crash the app yourself. Either way the rest of the walkthrough is identical.

Keep the value below `CRASH_DELAY_SECONDS` (30 by default) so the crash lands inside tool 2 rather than after the run has finished. The clock starts when tool 2 starts, not when the request arrives, so the budget is measured against tool 2's own delay and does not have to cover the LLM turn and tool 1 ahead of it. That is also why the field is safe to send on the re-issue below: the timer only starts when tool 2 actually runs, and a call that attaches to an existing run replays the recorded result instead of re-invoking it.

**Crash the app.** Skip this if you sent `kill_after_seconds` above. Otherwise, from a third terminal, while tool 2 is still comparing:

> **`POST /crash/kill` is demo scaffolding. Do not copy it into a real service.**
> It is an unauthenticated endpoint that lets any caller that can reach the port
> terminate the process, and it exists here only to make a crash reproducible on
> demand.


**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:5050/crash/kill
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:5050/crash/kill'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the *Crash Recovery: kill the app while the run above is in flight* request.

The endpoint calls `Process.GetCurrentProcess().Kill()`, which is `SIGKILL` on macOS and Linux and `TerminateProcess` on Windows, so the process is gone before it can answer and this request itself reports a connection reset rather than a status code. That is expected: a process that answers politely has not crashed. The blocked request sees a reset too.

The workflow instance `gala-42` is unaffected. It lives in Catalyst, not in the process you just killed.

**Restart the app.** Start the application again with the same `diagrid dev run` command you used in step 1. The project and the agent already exist, so this is the only command you need:

```bash
diagrid dev run -f dev-dotnet-agent.yaml --approve
```

**That is the whole recovery. You do not have to send anything.** The run is not waiting on you: Catalyst has been retrying the interrupted tool call the entire time the app was down, and it hands the pending work back within a second of the restarted app's worker reconnecting. The log below is usually scrolling before you can type:

```text
== APP - event-planner == >>> TOOL 2: Comparing venues over ~30s. KILL THE APP NOW to test crash recovery (POST /crash/kill, or kill -9). It resumes on restart.
== APP - event-planner == >>> TOOL 2 COMPLETE: Grand Ballroom is the best option
== APP - event-planner == >>> TOOL 3: Confirming booking...
== APP - event-planner == >>> TOOL 3 COMPLETE: Booking confirmed for Grand Ballroom
```

`>>> TOOL 1: Searching venues in 'Austin'...` does **not** appear again, and neither does the LLM call that chose it. Those activities had completed and Catalyst had recorded their results, so the replay took the recorded values. Only the activity that was interrupted runs a second time.

**Collect the answer.** The run recovered on its own, but the crash took the connection that was waiting for its result: the `/crash/run` request you sent before the kill died with the process, and its answer had nowhere to go. Send the **identical** request once more to open a new connection to the run that already finished:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:5050/crash/run \
  -H "Content-Type: application/json" \
  -d '{"id": "gala-42", "prompt": "Find a venue in Austin for a company gala"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:5050/crash/run' -ContentType 'application/json' -Body '{"id": "gala-42", "prompt": "Find a venue in Austin for a company gala"}'
```

Because the instance already exists, this call attaches to the run you started before the crash instead of starting a second one, and the app logs `Attaching to the existing run gala-42` to say so. It resumes nothing, because nothing was waiting: it reads back the answer that run recorded, in `result`.

`/crash/run` always answers in the same JSON shape, `{"id", "result", "message"}`: a `200` carries the agent's answer in `result`, while a `202` (the wait budget elapsed before the run finished) carries the attach instruction in `message` instead. The `202` is not a failure: send the same request again to attach again. A request with a missing or blank `id` is a `400` whose `message` is `id is required`.

> The final sentence the agent writes is composed by the model, so running the demo again under a **new** ID can produce different prose from identical tool results. Re-using `gala-42` cannot: the killed call never returned a body, and the re-issued call replays that instance's recorded output. Either way, the proof to read is the app log and the execution trace in the console, not the prose. The crash demos in the [workflow quickstarts](../../workflow) return a deterministic answer instead, because they run no model at all.

The length of tool 2 is configurable through the `CRASH_DELAY_SECONDS` environment variable, which defaults to 30. Set it lower to shorten the window, or higher if you need more time to aim.

### 4. Inspecting the Results in Catalyst

Open the [Catalyst dashboard](https://catalyst.diagrid.io/agents) in your browser and navigate to Agents > event-planner. Then select the most recent agent workflow run to view output.

For a crash-recovery run you do not have to guess which one is yours: it is the execution named `gala-42`, or whatever ID you passed. The trace shows one execution, not two, with the interrupted tool attempted twice and every earlier activity once.

## Clean Up

Stop the running application with `Ctrl+C`, then delete the Catalyst project:

```bash
diagrid project delete dotnet-quickstart
```

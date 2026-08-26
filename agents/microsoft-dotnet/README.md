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

**Crash the app.** From a third terminal, while tool 2 is still comparing:

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

**Restart and re-issue.** Start the application again with the same `diagrid dev run` command you used in step 1. The project and the agent already exist, so this is the only command you need:

```bash
diagrid dev run -f dev-dotnet-agent.yaml --approve
```

Then send the **identical** `/crash/run` request again. Because the instance already exists, it attaches to the run you started before the crash instead of starting a second one:

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

The run resumes the moment the restarted app's worker reconnects, so the log below may already be scrolling before you send anything. The re-issued request attaches to that run and returns its recorded answer in `result`:

```text
== APP - event-planner == >>> TOOL 2: Comparing venues over ~30s. KILL THE APP NOW to test crash recovery (POST /crash/kill, or kill -9). It resumes on restart.
== APP - event-planner == >>> TOOL 2 COMPLETE: Grand Ballroom is the best option
== APP - event-planner == >>> TOOL 3: Confirming booking...
== APP - event-planner == >>> TOOL 3 COMPLETE: Booking confirmed for Grand Ballroom
```

`>>> TOOL 1: Searching venues in 'Austin'...` does **not** appear again, and neither does the LLM call that chose it. Those activities had completed and Catalyst had recorded their results, so the replay took the recorded values. Only the activity that was interrupted runs a second time.

`/crash/run` always answers in the same JSON shape, `{"id", "result", "message"}`: a `200` carries the agent's answer in `result`, while a `202` (the wait budget elapsed before the run finished) carries the attach instruction in `message` instead. The `202` is not a failure: re-issue the same request to attach again. A request with a missing or blank `id` is a `400` whose `message` is `id is required`.

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

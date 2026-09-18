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

1. [Diagrid CLI](https://docs.diagrid.io/references/catalyst/catalyst-cli-intro/) installed
2. [Node.js 22.13 or newer](https://nodejs.org/en/)
3. An [OpenAI API key](https://platform.openai.com/api-keys)

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

The `crash_test.ts` file demonstrates durable crash recovery. It looks up an incident's status through one tool call, and deliberately crashes the process (`process.exit(1)`) partway through the *second* model call — after the first model call and the `checkIncidentStatus` tool call have both completed and been checkpointed by Catalyst, but before the model call that turns the tool's result into a final answer returns. (Yes, the SRE agent survives its own outage.)

The crash point is decided by an internal counter, not by a request you send or a line you comment out — so there's no source edit, no environment variable to unset, and no separate kill command. Just run the same command twice:

1. **Model call 1** — asks for the `checkIncidentStatus` tool. Completes and is checkpointed by Catalyst.
2. **checkIncidentStatus** — looks up the incident, returns "mitigated, monitoring for recurrence". Completes and is checkpointed.
3. **Model call 2** — this is where the process kills itself, before the call returns.

A state file under `$TMPDIR` counts model calls and tool runs across both runs. That count is the actual proof: the turn needs two model calls and one tool call, so if `checkIncidentStatus` ran only once in total, its result was replayed from Catalyst's workflow history on the second run rather than recomputed.

### First run — trigger and crash

Clear the state file first so this run starts clean:

```bash
rm -f "${TMPDIR:-/tmp}/diagrid-mastra-crash-state.json"
diagrid dev run -f dev-crash-test.yaml --approve
```

```text
============================================================
RUN #1
State file:      /tmp/diagrid-mastra-crash-state.json
Model calls:     0 so far
Tool runs:       0 so far
Already crashed: false
============================================================
>>> Model call 1 (total across runs)
>>> checkIncidentStatus ran (total across runs: 1)

>>> Killing the process during model call 2, before it returns.
>>> Run "npm run crash-test" again — Catalyst will resume this workflow.
```

The workflow instance is unaffected — it lives in Catalyst, not in the process that just died.

### Second run — resume and verify

Run the exact same command again:

```bash
diagrid dev run -f dev-crash-test.yaml --approve
```

```text
============================================================
RUN #2
State file:      /tmp/diagrid-mastra-crash-state.json
Model calls:     1 so far
Tool runs:       1 so far
Already crashed: true
============================================================
>>> Model call 2 (total across runs)

============================================================
Status:      completed
Answer:      The status of incident INC-4471 is mitigated and currently
under monitoring for recurrence.
Model calls: 2 (across all runs)
Tool runs:   1 (across all runs)

✅ Recovery confirmed: checkIncidentStatus ran exactly once across both runs.
   Its result was replayed from Catalyst workflow history, not recomputed.
============================================================
```

No request has to be re-sent and no workflow ID has to be tracked by hand: `crash_test.ts` reuses the same thread ID and workflow ID on both runs, so the second run automatically reattaches to the interrupted instance and waits for it, rather than starting a new one. Catalyst redelivers the pending work the moment this process's worker reconnects — that redelivery is what "resume on restart" means here, and `checkIncidentStatus`'s count staying at 1 is what proves it replayed rather than reran.

# Spring AI Quickstart - Event Planner

This quickstart demonstrates how to run a [Spring AI](https://docs.spring.io/spring-ai/reference/)
agent as a durable Dapr Workflow using the `io.diagrid:diagrid-spring-ai-starter` package. The agent
acts as an **Event Planner** with three tools that it calls in sequence — tool 2 deliberately crashes
the process to demonstrate automatic recovery.

The app itself is **plain Spring AI** — a `ChatClient` bean + three `@Tool` beans + a REST endpoint.
There is no durability code anywhere in it: adding the starter to the classpath is what turns every
`ChatClient.call()` into a checkpointed Dapr Workflow — and, as of 0.2.0, the starter also records the
`ChatClient` bean as a Catalyst agent (registration ships in the starter, no separate dependency).

## What This Quickstart Demonstrates

- **Spring AI + Dapr Workflows**: run a Spring AI agent with durable execution, added by dependency rather than by durability code
- **No model account needed**: the app ships an offline model, so the whole walkthrough runs without an API key
- **Spring AI model providers**: the same `ChatClient` talks to OpenAI through `spring-ai-starter-model-openai` when you ask it to
- **Crash Recovery**: tool 2 crashes the process; on restart, Catalyst resumes the workflow automatically — completed steps are not re-run
- **REST API**: trigger the agent via an HTTP endpoint

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [JDK 21](https://adoptium.net/) or later, and [Maven 3.9+](https://maven.apache.org/download.cgi)
3. *(Optional)* An [OpenAI API key](https://platform.openai.com/api-keys), only if you want to run
   against a real model provider instead of the offline one

## Setup

```bash
cd event-planner

# Build the project (pre-downloads dependencies)
mvn package -DskipTests
```

### Use a real model (optional)

**This quickstart needs no API key.** It is about durable execution rather than model quality, so it
ships an offline model (`CannedChatModel`) that always calls the three tools in order and reports what
the last one returned. That is what makes the crash and the recovery the only moving parts, and it is
why every run gives the same answer.

To run against OpenAI instead, set both variables. The offline model announces itself in the startup
log, so no such line means the app is talking to a real provider.

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

On that path a missing or wrong key no longer stops the app from starting. The provider rejects the
first request instead, and because the model call is a durable activity that failure is retried a few
times before it surfaces.

## Running the Quickstart

### 1. Deploy and Run

Log in, create the Catalyst project with managed workflow enabled (and set it as the default for this session), register the agent, then run:

```bash
diagrid login
diagrid project create spring-ai-quickstart --enable-managed-workflow --deploy-managed-kv --wait --use
diagrid agent create spring-ai-event-planner --wait
diagrid dev run -f dev-spring-ai-event-planner.yaml --approve
```

> `diagrid agent create` is **required**, not optional. It creates the App ID the agent registry files
> this agent under, and the managed `agent-registry` connection is only scoped to App IDs backed by an
> agent. `diagrid dev run` starts fine without it, but the agent registration then fails against a
> connection it cannot load.

### 2. Trigger the Agent

From another terminal:

Choose one of the following to trigger the endpoint:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:8080/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Find a venue in Austin for a company gala"}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8080/run' -ContentType 'application/json' -Body '{"prompt": "Find a venue in Austin for a company gala"}'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the request. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension.

The agent will:
1. Call `step_one_search` — finds venues (completes)
2. Call `step_two_compare` — crashes before completing (process exits)

You'll see:

```text
== APP == >>> TOOL 1: Searching venues in 'Austin'...
== APP == >>> TOOL 1 COMPLETE: Found 3 venues
== APP == >>> TOOL 2: Comparing venues...
```

The process exits — this is expected. (The `curl` call does not return a result: the app died
mid-request. The workflow itself is safe in Catalyst and will resume in the next step.)

## Crash Recovery

Open `EventPlannerTools.java` and comment out the crash line in `step_two_compare`:

```java
// Runtime.getRuntime().halt(1); // 💥 Comment out this line before the second run
```

Restart (the project and agent already exist, so just run):

```bash
diagrid dev run -f dev-spring-ai-event-planner.yaml --approve
```

You do **not** need to trigger the endpoint again — the existing workflow resumes automatically.
`step_one_search` and the first model turn are **replayed from the workflow history** (not re-executed),
and execution continues from `step_two_compare`:

```text
== APP == >>> TOOL 2: Comparing venues...
== APP == >>> TOOL 2 COMPLETE: Grand Ballroom is the best option
== APP == >>> TOOL 3: Confirming booking...
== APP == >>> TOOL 3 COMPLETE: Booking confirmed for Grand Ballroom
```

## How It Works

- `diagrid-spring-ai-starter` auto-configures a `DurableAdvisor` and an in-process Dapr Workflow
  worker. Because the agent is a `ChatClient` **bean** (`EventPlannerAgentConfig`), the starter
  attaches a *per-agent* advisor to that bean and names its workflow after it:
  `spring-ai.spring-ai-event-planner.workflow`. A `ChatClient` built ad hoc from the injected
  `ChatClient.Builder` instead gets the generic advisor and the shared `spring-ai.workflow` name.
- Each `ChatClient.call()` runs as a Dapr Workflow; the model turn and each `@Tool` call run as
  separate **checkpointed activities**. A crash resumes from the last completed step — completed
  activities are replayed from history rather than re-executed.
- The three tools are global `@Tool` beans, so they are rediscovered on the restarted worker and the
  resumed workflow can run the pending activity.
- The **starter** records the agent under the app id in `application.properties`, named after the
  bean (`spring-ai-event-planner`). It derives the workflow name it records from that same bean name,
  so the workflow on the agent record is the workflow that actually runs.
- The **model itself is a durable activity**, which is why this app ships one rather than skipping it:
  the agent's tool choice is the only path into the three tools, so there is no crash to demonstrate
  without a model. [`CannedChatModel`](./src/main/java/io/diagrid/quickstart/springai/eventplanner/CannedChatModel.java)
  supplies that offline. It decides which step to ask for by counting the tool results in the
  conversation rather than from a counter, so the activity is safe to re-enter: after the restart it
  asks for `step_two_compare` again — which is what lets the run finish — instead of starting over at
  step one.

> **A note on idempotency.** A durable activity is *at-least-once*: the tool that was in flight at
> crash time re-runs on recovery. This quickstart's tools are side-effect-free, so re-running is
> harmless. A tool with a real side effect (a booking, a payment) must be made idempotent by the app —
> see the sibling [`crash-recovery`](../crash-recovery) quickstart, which schedules under a
> caller-owned instance id so a retry *attaches* to the existing run instead of doing the work twice.

## Clean Up

Stop the running application with `Ctrl+C`, then delete the Catalyst project:

```bash
diagrid project delete spring-ai-quickstart
```

# Spring AI Quickstart - Event Planner

This quickstart demonstrates how to run a [Spring AI](https://docs.spring.io/spring-ai/reference/)
agent as a durable Dapr Workflow using the `io.diagrid.dapr:dapr-spring-ai-starter` package. The agent
acts as an **Event Planner** with three tools that it calls in sequence — tool 2 deliberately crashes
the process to demonstrate automatic recovery.

The app itself is **plain Spring AI** — a `ChatClient` + three `@Tool` beans + a REST endpoint. There
is no durability code anywhere in it: adding the starter to the classpath is what turns every
`ChatClient.call()` into a checkpointed Dapr Workflow.

## What This Quickstart Demonstrates

- **Spring AI + Dapr Workflows**: run a Spring AI agent with durable execution — by adding one dependency, no code changes
- **OpenAI via Spring AI**: calls OpenAI directly through the `spring-ai-starter-model-openai` `ChatClient`
- **Crash Recovery**: tool 2 crashes the process; on restart, Catalyst resumes the workflow automatically — completed steps are not re-run
- **REST API**: trigger the agent via an HTTP endpoint

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [JDK 21](https://adoptium.net/) or later, and [Maven 3.9+](https://maven.apache.org/download.cgi)
3. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

```bash
cd event-planner

# Build the project (pre-downloads dependencies)
mvn package -DskipTests
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

## Running the Quickstart

### 1. Deploy and Run

```bash
diagrid login
diagrid dev run -f dev-spring-ai-event-planner.yaml --project spring-ai-event-planner --approve
```

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

Restart:

```bash
diagrid dev run -f dev-spring-ai-event-planner.yaml --project spring-ai-event-planner --approve
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

- `dapr-spring-ai-starter` auto-configures a `DurableAdvisor` (attached to every `ChatClient` built
  from the injected `ChatClient.Builder`) and an in-process Dapr Workflow worker.
- Each `ChatClient.call()` runs as a Dapr Workflow; the model turn and each `@Tool` call run as
  separate **checkpointed activities**. A crash resumes from the last completed step — completed
  activities are replayed from history rather than re-executed.
- The three tools are global `@Tool` beans, so they are rediscovered on the restarted worker and the
  resumed workflow can run the pending activity.

> **A note on idempotency.** A durable activity is *at-least-once*: the tool that was in flight at
> crash time re-runs on recovery. This quickstart's tools are side-effect-free, so re-running is
> harmless. A tool with a real side effect (a booking, a payment) must be made idempotent by the app —
> see the sibling [`crash-recovery`](../crash-recovery) quickstart, which schedules under a
> caller-owned instance id so a retry *attaches* to the existing run instead of doing the work twice.

## Clean Up

Stop the running application with `Ctrl+C`, then delete the Catalyst project:

```bash
diagrid project delete spring-ai-event-planner
```

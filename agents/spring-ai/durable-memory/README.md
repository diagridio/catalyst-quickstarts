# Spring AI Quickstart - Durable Memory

This quickstart shows **what durability does and does not cover** when you combine the
`dapr-spring-ai-starter` with Spring AI's memory. It is a durable chat agent whose conversation is
persisted with a `MessageChatMemoryAdvisor` backed by the `dapr-spring-ai-memory` Dapr state store.

The key lesson: **Spring AI runs advisors synchronously, and an advisor's response phase runs only
after a successful call.** The durable Dapr Workflow (the model call and each `@Tool` call) survives a
crash — but the memory advisor that records the assistant's answer runs *on the caller thread, after
the call returns*. Crash mid-call and the workflow lives on, yet the answer was never written to
memory. Only a successful (re-attached) call completes the advisor chain and persists it.

## What This Quickstart Demonstrates

- **Durable memory**: chat memory persisted in a Dapr state store, so conversations survive restarts
- **The synchronous advisor model**: `MessageChatMemoryAdvisor.before()` saves the user message; `after()` saves the assistant reply — and `after()` only runs on success
- **The durability boundary**: the workflow (model + tools) is durable; the caller-side advisor response phase is not
- **Re-attach to complete the chain**: re-issuing the same instance id attaches to the resumed run, succeeds, and *then* the memory advisor records the answer

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [JDK 21](https://adoptium.net/) or later, and [Maven 3.9+](https://maven.apache.org/download.cgi)
3. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

```bash
cd durable-memory
mvn package -DskipTests

export OPENAI_API_KEY="your-key-here"   # PowerShell: $env:OPENAI_API_KEY = "your-key-here"
```

## Running the Quickstart

```bash
diagrid login
diagrid dev run -f dev-spring-ai-durable-memory.yaml --project spring-ai-durable-memory --approve
```

### 1. Start a durable turn (it blocks on a slow tool)

From another terminal — this schedules the booking under an instance id **you own** (`trip-1`) and a
`conversationId` (`alice`). It blocks ~30s while the `commitReservation` tool "commits":

```bash
curl -X POST "http://localhost:8080/chat?id=trip-1&conversationId=alice&message=Book%20a%20flight%20to%20Oslo,%20reference%20OSLO-1"
```

### 2. Look at what memory has so far

In a third terminal, while the call above is still blocked:

```bash
curl "http://localhost:8080/history?conversationId=alice"
```

You see only the **user** question — the memory advisor's `before` phase saved it, but the `after`
phase (which saves the answer) has not run yet:

```json
["USER: Book a flight to Oslo, reference OSLO-1"]
```

### 3. Crash the app mid-call

```bash
curl -X POST "http://localhost:8080/crash/kill"
```

The process dies. The workflow is safe in Catalyst — but the memory advisor's `after` phase never
ran, so the answer was never recorded.

## Recovery — the response advisor only runs on success

Restart the app (no code changes needed):

```bash
diagrid dev run -f dev-spring-ai-durable-memory.yaml --project spring-ai-durable-memory --approve
```

Check memory again — still just the question; the crashed call never persisted an answer:

```bash
curl "http://localhost:8080/history?conversationId=alice"
# ["USER: Book a flight to Oslo, reference OSLO-1"]
```

Now **re-issue the same call with the same instance id**. It attaches to the resumed workflow, the
call returns successfully, and *only now* does the memory advisor's `after` phase record the answer:

```bash
curl -X POST "http://localhost:8080/chat?id=trip-1&conversationId=alice&message=Book%20a%20flight%20to%20Oslo,%20reference%20OSLO-1"

curl "http://localhost:8080/history?conversationId=alice"
```

```json
[
  "USER: Book a flight to Oslo, reference OSLO-1",
  "USER: Book a flight to Oslo, reference OSLO-1",
  "ASSISTANT: Booking OSLO-1 confirmed. Confirmation code: BK-..."
]
```

The **assistant answer appears only after the successful call** — that is "response advisors run after
a success call." Note the user question appears **twice**: the memory advisor's `before` phase runs on
*every* attempt (the crashed one and the re-attach), so it records the question each time. The answer,
written in the `after` phase, is recorded once — on success.

## How It Works

- `DurableAdvisor` (from `dapr-spring-ai-starter`) is a **terminal** advisor: it runs the model + tool
  loop as a Dapr Workflow and returns, short-circuiting the chain. That workflow is what's durable.
- `MessageChatMemoryAdvisor` sits **before** it in the chain. Its `before` phase (retrieve history, add
  the user message) runs on the caller thread going in; its `after` phase (add the assistant reply)
  runs on the caller thread coming back — **only if the durable call returned successfully**.
- On a crash or a `DurableCallTimeoutException`, the `after` phase never runs. The workflow is durable;
  the caller-side advisor response phase is not. Re-attaching with the same instance id
  (`DurableAdvisor.INSTANCE_ID_KEY`) is what lets the full chain complete.
- Chat memory is backed by the Catalyst-managed `agent-memory` store via `dapr-spring-ai-memory`
  (`dapr.spring-ai.memory.statestore=agent-memory`).

> **Design takeaway.** Put anything that must survive a crash *inside* the workflow — as a `@Tool`
> activity, whose result is checkpointed. Advisor response-phase side effects (memory, logging,
> post-processing) are best-effort on top of a successful call; make retries safe with a caller-owned
> instance id (see the [crash-recovery](../crash-recovery) quickstart).

## Clean Up

Stop the app with `Ctrl+C`, then delete the Catalyst project:

```bash
diagrid project delete spring-ai-durable-memory
```

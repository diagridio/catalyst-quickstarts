# Spring AI Quickstart - Crash Recovery

This quickstart demonstrates how to recover a durable [Spring AI](https://docs.spring.io/spring-ai/reference/)
agent from a hard crash using the `io.diagrid:diagrid-spring-ai-starter` package. A booking agent
schedules its work under an **instance id you own**, so if the app is killed mid-call you can re-issue
the same request and **attach** to the still-running workflow instead of starting a second booking.

Where the sibling [`event-planner`](../event-planner) quickstart uses side-effect-free tools (so a
replay is harmless), this one confronts **idempotency** head-on: the tool has a real side effect (a
booking), and a caller-owned instance id is what makes a retry safe.

## What This Quickstart Demonstrates

- **Caller-owned instance id**: schedule a `ChatClient.call()` under an id you choose via `DurableAdvisor.INSTANCE_ID_KEY`
- **Re-attach on recovery**: re-issuing the same id attaches to the resumed workflow — no duplicate work
- **Idempotency**: the confirmation code is derived from the booking reference, so a re-attached call returns the *same* code — visible proof the booking was not redone
- **Crash-safe tools**: a global `@Tool` bean is rediscovered on the restarted worker, so the resumed activity can run it

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [JDK 21](https://adoptium.net/) or later, and [Maven 3.9+](https://maven.apache.org/download.cgi)
3. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

```bash
cd agents/spring-ai/crash-recovery

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

Log in, create the Catalyst project with managed workflow enabled (and set it as the default for this session), register the agent, then run:

```bash
diagrid login
diagrid project create spring-ai-crash-recovery --enable-managed-workflow --deploy-managed-kv --wait --use
diagrid agent create spring-ai-crash-recovery --wait
diagrid dev run -f dev-spring-ai-crash-recovery.yaml --approve
```

### 2. Book under an id you own (blocks ~30s)

From another terminal (**Terminal A**) — this schedules the booking under `trip-42` and blocks while the slow tool "commits":

```bash
curl "http://localhost:8080/crash/book?id=trip-42&reference=ABC123"
```

Watch the app log for `>>> commitReservation(ABC123) — committing over ~30s`.

### 3. Crash the app mid-call

From **Terminal B**, during that window:

```bash
curl -X POST "http://localhost:8080/crash/kill"
```

The app process dies (Terminal A's `curl` sees a reset). The workflow `trip-42` keeps living in Catalyst.

## Recovery — re-attach by instance id

Restart the app (the project and agent already exist, so just run):

```bash
diagrid dev run -f dev-spring-ai-crash-recovery.yaml --approve
```

The durable runtime resumes instance `trip-42`; the pre-crash LLM turn is not re-executed. Now re-issue
the **same** call with the **same** id from **Terminal A**:

```bash
curl "http://localhost:8080/crash/book?id=trip-42&reference=ABC123"
```

It **attaches** to the resumed run (waiting if it is still committing, or returning the recorded answer
if it finished) and returns the **same confirmation code** — no second booking:

```text
Booking ABC123 confirmed. Confirmation code: BK-...
```

## How It Works

- The booking agent is a **named `ChatClient` bean** (`crashRecoveryAgent`), so it runs under its own
  per-agent workflow name. Each call sets a caller-owned instance id via
  `DurableAdvisor.INSTANCE_ID_KEY` — that id is the attach handle a retry re-uses.
- The booking tool (`SlowBookingTools.commitReservation`) is a **global `@Tool` bean** so it is
  re-registered on a restarted worker and the resumed activity can run it (a request-scoped tool would
  be gone after a cold restart). It sleeps ~30s to open the crash window.
- On a re-issue with the same id, the durable runtime attaches to the existing instance instead of
  scheduling a new one. If the call's wait budget elapses it throws `DurableCallTimeoutException` with
  the instance id — re-issue the same id to collect the result.

> **The instance id is a bearer handle you own** — guard it like a primary key. A durable activity is
> *at-least-once*, so make side-effecting tools idempotent by keying off a business value (here, the
> booking reference). To re-run a spent id, purge it first.

## Clean Up

Stop the running application with `Ctrl+C`, then delete the Catalyst project:

```bash
diagrid project delete spring-ai-crash-recovery
```

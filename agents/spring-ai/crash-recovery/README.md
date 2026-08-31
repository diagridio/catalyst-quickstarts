# Spring AI Quickstart - Crash Recovery

This quickstart demonstrates how to recover a durable [Spring AI](https://docs.spring.io/spring-ai/reference/)
agent from a hard crash using the `io.diagrid:diagrid-spring-ai-starter` package. A booking agent
schedules its work under an **instance id you own**. Restarting the app is what recovers the run. The id
is what lets a later call **attach** to that same workflow to read its answer, instead of starting a
second booking.

Where the sibling [`event-planner`](../event-planner) quickstart uses side-effect-free tools (so a
replay is harmless), this one confronts **idempotency** head-on: the tool has a real side effect (a
booking), and a caller-owned instance id is what makes a retry safe.

## What This Quickstart Demonstrates

- **Caller-owned instance id**: schedule a `ChatClient.call()` under an id you choose via `DurableAdvisor.INSTANCE_ID_KEY`
- **Automatic recovery**: restarting the app resumes the run, with no request needed to nudge it
- **Re-attach to read the answer**: a later call with the same id attaches to the recovered workflow, with no duplicate work
- **Idempotency**: the confirmation code is derived from the booking reference, so a re-attached call returns the *same* code: visible proof the booking was not redone
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

From another terminal (**Terminal A**), this schedules the booking under `trip-42` and blocks while the
slow tool "commits":

```bash
curl -X POST "http://localhost:8080/crash/run" \
  -H "Content-Type: application/json" \
  -d '{"id":"trip-42","reference":"ABC123"}'
```

Watch the app log for the `>>> commitReservation(ABC123)` line, which announces the ~30s window and
tells you to kill the app now.

**Two terminals instead of three.** The request takes an optional `kill_after_seconds`. Send it and the
app halts *itself* that many seconds into the booking, at a known point inside the window, so you never
have to aim a kill at a moving target:

```bash
curl -X POST "http://localhost:8080/crash/run" \
  -H "Content-Type: application/json" \
  -d '{"id":"trip-42","reference":"ABC123","kill_after_seconds":8}'
```

Send this instead of the request above and skip step 3: the app crashes on its own. Leave the field out
and nothing changes, and you crash the app yourself from Terminal B. Either way the rest of the
walkthrough is identical.

Keep the value below `crash-recovery.delay-seconds` (30 by default) so the crash lands inside the
booking rather than after it has finished. The clock starts when `commitReservation` starts, not when
the request arrives, so the budget is measured against that tool's own sleep and does not have to cover
the LLM turn ahead of it. That is also why the field is safe to send on the re-issue in *Collect the
answer*: the timer only starts when the tool actually runs, and a call that attaches to an existing run
replays the recorded result instead of re-invoking it.

### 3. Crash the app mid-call

Skip this step if you sent `kill_after_seconds` in step 2. Otherwise, from **Terminal B**, during that
window:

> **`POST /crash/kill` is demo scaffolding. Do not copy it into a real service.**
> It is an unauthenticated endpoint that lets any caller that can reach the port
> terminate the process, and it exists here only to make a crash reproducible on
> demand.


```bash
curl -X POST "http://localhost:8080/crash/kill"
```

The app process dies (Terminal A's `curl` sees a reset). The workflow `trip-42` keeps living in Catalyst.

## Recovery: restart the app

Restart the app (the project and agent already exist, so just run):

```bash
diagrid dev run -f dev-spring-ai-crash-recovery.yaml --approve
```

**That is the whole recovery. You do not have to send anything.** The run is not waiting on you:
Catalyst has been retrying the interrupted tool call the entire time the app was down, and it hands the
pending work back the moment the restarted app's worker reconnects. The durable runtime resumes instance
`trip-42` on its own, and the pre-crash LLM turn is not re-executed. Watch the app log: it is usually
scrolling before Spring Boot has finished starting Tomcat, and always before you could send anything.

## Collect the answer

The run recovered on its own, but the crash took the connection that was waiting for its result:
Terminal A's call died with the process, and its answer had nowhere to go. Send the **same** call with
the **same** id from **Terminal A** once more to open a new connection to the run that already finished:

```bash
curl -X POST "http://localhost:8080/crash/run" \
  -H "Content-Type: application/json" \
  -d '{"id":"trip-42","reference":"ABC123"}'
```

It **attaches** to the recovered run (waiting if it is still committing, or returning the recorded answer
if it finished) and returns the **same confirmation code**, with no second booking. It resumes nothing,
because nothing was waiting. The response is the one JSON shape every crash demo in this repo returns,
`{"id", "result", "message"}`, with the agent's answer in `result`:

```json
{
  "id": "trip-42",
  "result": "Booking ABC123 confirmed. Confirmation code: BK-...",
  "message": null
}
```

The model chooses the wording around it, but the code after `BK-` is derived from the reference, so it
is the same code the killed call would have returned.

If the call's wait budget elapses first, the same shape comes back as a `202` with `result` null and the
attach instruction in `message`. That is not a failure: send the same request with the same id again to
attach again. A request with a missing or blank `id` is a `400` whose `message` is `id is required`.

## How It Works

- The booking agent is a **named `ChatClient` bean** (`crashRecoveryAgent`), so it runs under its own
  per-agent workflow name. Each call sets a caller-owned instance id via
  `DurableAdvisor.INSTANCE_ID_KEY`: that id is the attach handle a retry re-uses.
- The booking tool (`SlowBookingTools.commitReservation`) is a **global `@Tool` bean** so it is
  re-registered on a restarted worker and the resumed activity can run it (a request-scoped tool would
  be gone after a cold restart). It sleeps for `crash-recovery.delay-seconds` (30 by default) to open
  the crash window.
- On a re-issue with the same id, the durable runtime attaches to the existing instance instead of
  scheduling a new one. If the call's wait budget elapses it throws `DurableCallTimeoutException` with
  the instance id, so re-issue the same id to collect the result.

> **The instance id is a bearer handle you own**, so guard it like a primary key. A durable activity is
> *at-least-once*, so make side-effecting tools idempotent by keying off a business value (here, the
> booking reference). To re-run a spent id, purge it first.

### Changing the length of the crash window

The tool's sleep is configurable, like the delay in the sibling crash demos. This app reads a Spring
property rather than an environment variable: `crash-recovery.delay-seconds` in
[`src/main/resources/application.properties`](./src/main/resources/application.properties), which
defaults to 30. Set it lower to shorten the crash window, or higher if you need more time to aim the
second terminal:

```properties
crash-recovery.delay-seconds=10
```

The value is also what the tool's log line reports, so `committing over ~10s` confirms the change took
effect. Keep it comfortably below `diagrid.spring-ai.completion-timeout` (the blocking call's wait
budget, set to 2m in the same file) so the first `/crash/run` is still blocked when you kill the app.

## Clean Up

Stop the running application with `Ctrl+C`, then delete the Catalyst project:

```bash
diagrid project delete spring-ai-crash-recovery
```

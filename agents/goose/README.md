# Goose Quickstart - Release Manager

This quickstart demonstrates how to run a [Goose](https://github.com/aaif-goose/goose) agent as a durable Dapr Workflow using Diagrid's Rust SDK ([`diagrid-goose`](https://crates.io/crates/diagrid-goose)). The agent acts as a **Release Manager** that writes release notes, runs the release checks with its shell tool, and keeps the notes up to date over several turns of one conversation.

## What This Quickstart Demonstrates

- **Goose + Dapr Workflows**: Run a multi-turn Goose conversation as a durable Dapr Workflow, where every turn is a checkpointed activity
- **Unmodified Goose**: Drives the real `goose` CLI over the [Agent Client Protocol](https://agentclientprotocol.com/) (`goose acp`), with no Goose code changes, plugins or forks
- **Goose's own tools**: Goose writes files and runs shell commands with its built-in developer tools, in a scratch directory of its own
- **Session continuity**: Every turn runs in a fresh Goose process that reloads the same Goose session, so the conversation carries over from turn to turn, and across a crash
- **Durable Crash Recovery**: Resume a run from the last completed turn after a crash — a capability not offered by Goose natively (see [Crash Recovery Test With Catalyst](#crash-recovery-test-with-catalyst))

### Role

- **Agent**: `release-manager`

### Tools

There are none to define. Goose ships its own developer tools and decides when to use them: it writes and edits `RELEASE_NOTES.md` with its file tools, and runs the release checks with its shell tool.

## Prerequisites

1. A [Diagrid Catalyst account](https://catalyst.diagrid.io/)
2. [Diagrid CLI](https://docs.diagrid.io/getting-started/install-cli) installed
3. [Rust 1.88 or newer](https://rustup.rs/) (check with `rustc --version`)
4. The [Goose CLI](https://github.com/aaif-goose/goose), v1.54.0 (see [Install Goose](#install-goose))
5. An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

Navigate to the `goose` directory and build the quickstart. The first build compiles the Dapr SDK and its gRPC stack, so it takes a few minutes:

```bash
cd agents/goose
cargo build
```

### Install Goose

This quickstart is validated against Goose v1.54.0. Install exactly that version, and skip Goose's interactive setup: the quickstart configures Goose through the environment instead.

**macOS/Linux (bash/zsh):**

```bash
curl -fsSL https://github.com/aaif-goose/goose/releases/download/stable/download_cli.sh | CONFIGURE=false GOOSE_VERSION=v1.54.0 bash
```

**Windows:** run the same command from Git Bash, or download `goose-x86_64-pc-windows-msvc.zip` from the [v1.54.0 release](https://github.com/aaif-goose/goose/releases/tag/v1.54.0) and put `goose.exe` on your `PATH`.

The installer puts `goose` in `~/.local/bin`. If that directory is not on your `PATH`, add it, or set `GOOSE_BIN` to the binary's full path.

### Set your API key

This quickstart runs Goose on OpenAI's `gpt-4o-mini`, but you can use any provider Goose supports.

**macOS/Linux (bash/zsh):**

```bash
export OPENAI_API_KEY="your-key-here"
```

**Windows (PowerShell):**

```powershell
$env:OPENAI_API_KEY = "your-key-here"
```

### Using another provider

Set `GOOSE_PROVIDER` and `GOOSE_MODEL`, plus that provider's own key. For example, for Anthropic:

**macOS/Linux (bash/zsh):**

```bash
export GOOSE_PROVIDER="anthropic"
export GOOSE_MODEL="claude-sonnet-4-6"
export ANTHROPIC_API_KEY="your-key-here"
```

**Windows (PowerShell):**

```powershell
$env:GOOSE_PROVIDER = "anthropic"
$env:GOOSE_MODEL = "claude-sonnet-4-6"
$env:ANTHROPIC_API_KEY = "your-key-here"
```

The provider and model travel with each run, in the workflow's recorded input. The key never does: Goose reads it from the environment of the process that runs it.

## Run with Catalyst

### 1. Login and Run

1. Login to Catalyst using the Diagrid CLI:

```bash
diagrid login
```

2. Create a new Catalyst project for the quickstart and use it as the default project for the current session:

```bash
diagrid project create goose-quickstart --enable-managed-workflow --wait --use
```

3. Create an agent for the project:

```bash
diagrid agent create release-manager --wait
```

4. Run the agent with Catalyst:

```bash
diagrid dev run -f dev-goose.yaml --approve
```

`src/main.rs` runs one durable, two-turn Goose conversation end-to-end: it starts the Dapr Workflow worker, schedules the conversation, waits for it, prints both turns, and exits. Like the Mastra quickstart, and unlike the Python agent quickstarts in this repo, there's no HTTP server left running and no second terminal needed to trigger anything — the command above is the whole demo.

Expect output like this:

```text
== APP - release-manager == Goose:     goose 1.54.0 on openai/gpt-4o-mini
== APP - release-manager == Workspace: /tmp/goose-quickstart/release-notes-1792460000
== APP - release-manager == Started workflow release-notes-1792460000: 2 Goose turns, one durable activity each.
== APP - release-manager ==
== APP - release-manager == ============================================================
== APP - release-manager == Turn 1
== APP - release-manager ==   you:   Write release notes for version 2.4.0 to RELEASE_NOTES.md: it adds dark mode and fixes the login timeout bug.
== APP - release-manager ==   goose: I've created RELEASE_NOTES.md with the release notes for version 2.4.0.
== APP - release-manager ==
== APP - release-manager == Turn 2
== APP - release-manager ==   you:   Add a "Known issues" section to the release notes saying CSV export is slow for very large files, then reply with the file's full contents.
== APP - release-manager ==   goose: # Release Notes - Version 2.4.0
== APP - release-manager ==
== APP - release-manager ==          ## New Features
== APP - release-manager ==          - Dark mode
== APP - release-manager ==
== APP - release-manager ==          ## Bug Fixes
== APP - release-manager ==          - Fixed the login timeout bug
== APP - release-manager ==
== APP - release-manager ==          ## Known issues
== APP - release-manager ==          - CSV export is slow for very large files
== APP - release-manager ==
== APP - release-manager == Status:  Completed
== APP - release-manager == Turns:   2, all in Goose session 20261020_3
== APP - release-manager == ============================================================
== APP - release-manager == Print the whole conversation with: goose session export --session-id 20261020_3
```

`Turns: 2, all in Goose session ...` is the proof: each turn ran as its own checkpointed Dapr activity, in a fresh `goose acp` process, and turn 2 still knew which file turn 1 had written because its process reloaded the same Goose session. So a process killed mid-conversation resumes from the last completed turn instead of starting over. See [Crash Recovery Test With Catalyst](#crash-recovery-test-with-catalyst) for a demonstration.

Goose did real work, too: `RELEASE_NOTES.md` is in the `Workspace` directory, and the `goose session export` command on the last line prints the whole conversation, tool calls included.

### 2. Inspecting the Results in Catalyst

Open the [Catalyst dashboard](https://catalyst.diagrid.io/agents) in your browser and navigate to Agents > release-manager. Then select the most recent workflow run (`GooseAgentExecution`) to view each turn's input and output.

## Crash Recovery Test With Catalyst

The `src/bin/crash_test.rs` app demonstrates durable crash recovery, a capability not offered by Goose natively. It serves the agent over HTTP and runs a release as three Goose turns in one Goose session, each a separate checkpointed Dapr activity:

1. **Turn 1**: Goose writes the release notes. Completes and is checkpointed by Catalyst
2. **Turn 2**: Goose runs the release checks, a shell command that takes ~10 seconds. The crash lands here
3. **Turn 3**: Goose adds the check results to the release notes

The order is the point. Turn 1 completes and Catalyst records its result before turn 2 starts, so the crash lands between two known points and the restart can show that only the interrupted turn ran again. Each turn logs itself (`>>> TURN 1`, `>>> TURN 2`, `>>> TURN 3`), which is how you follow it in the app log.

You also choose the workflow instance ID, so you can find the same run again from a second request or in the Catalyst console. Nothing is armed in the source: the crash is something you ask for, so there is no source edit and no environment variable to unset.

### 3. Start the app

This is a second app (`crash_test`, not the quickstart), so stop the run from step 1 if it is still going: both dev-run files use the same `release-manager` app ID.

```bash
diagrid dev run -f dev-crash-test.yaml --approve
```

Wait for `Crash demo listening on http://0.0.0.0:8001`. The port is pinned in `dev-crash-test.yaml`, so the `localhost:8001` requests below always work as written.

### 4. Run under an ID you own

From another terminal. The request carries `kill_after_seconds`, so the app halts *itself* that many seconds into turn 2, at a known point inside its window, and you never have to aim a kill at a moving target.

Choose one of the following to trigger the endpoint:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:8001/crash/run \
  -H "Content-Type: application/json" \
  -d '{"id": "release-42", "prompt": "Write release notes for version 2.5.0 to RELEASE_NOTES.md: it adds offline mode and fixes the CSV export crash.", "kill_after_seconds": 8}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/crash/run' -ContentType 'application/json' -Body '{"id": "release-42", "prompt": "Write release notes for version 2.5.0 to RELEASE_NOTES.md: it adds offline mode and fixes the CSV export crash.", "kill_after_seconds": 8}'
```

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above the *Crash Recovery: run the release under an ID you own* request. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension.

Go to the terminal where you started `diagrid dev run`. Turn 1 completes, turn 2 announces the self-kill, and the process exits 8 seconds into it:

```text
== APP - release-manager == >>> TURN 1: Goose is writing the release notes...
== APP - release-manager == >>> TURN 1 COMPLETE: release notes written, Goose session 20261020_4
== APP - release-manager == >>> TURN 2: Goose is running the release checks over ~10s, but this process kills itself 8s into the run, as asked by kill_after_seconds. It resumes on restart.
== APP - release-manager == >>> crash: killing this process 8s into the run, as asked by kill_after_seconds
```

The request then reports a connection reset, which is exactly what a real crash looks like. Goose goes down with the app, in the middle of its shell command. The workflow instance `release-42` is unaffected: it lives in Catalyst, not in the process that just died.

Keep the value below `CRASH_DELAY_SECONDS` (10 by default) so the crash lands inside turn 2 rather than after it. The clock starts when turn 2 starts, not when the request arrives, so the budget does not have to cover turn 1 ahead of it. That is also why the field is safe to send again in step 6: the timer only starts when turn 2 actually runs, and a call that attaches to an existing run never runs it.

### 5. Restart the app

Restart with the same command as step 3:

```bash
diagrid dev run -f dev-crash-test.yaml --approve
```

**That is the whole recovery. You do not have to send anything.** As soon as the restarted app's worker reconnects, Catalyst hands `release-42` back to it and turn 2 starts over in a fresh Goose process. That process reloads the Goose session turn 1 started, finds turn 2's message already in it with no finished reply, and asks the model to finish the interrupted turn rather than sending the message a second time. About 10 seconds later turn 3 runs. Watch the app log, where all of this happens before you send anything:

```text
== APP - release-manager == >>> TURN 2: Goose is running the release checks over ~10s. KILL THE APP NOW to test crash recovery (POST /crash/kill, or kill -9). It resumes on restart.
== APP - release-manager == [2026-10-20T01:11:09Z WARN  diagrid_goose::turn] session 20261020_4: an earlier attempt of this turn was interrupted; resuming it
== APP - release-manager == >>> TURN 2 COMPLETE: release checks finished, Goose session 20261020_4
== APP - release-manager == >>> TURN 3: Goose is adding the check results to the release notes...
== APP - release-manager == >>> TURN 3 COMPLETE: release notes updated, Goose session 20261020_4
```

Turn 1 is **not** run again: its `>>> TURN 1` lines do not appear a second time. That turn had completed and Catalyst had recorded its result, so the Dapr workflow engine replayed the saved value instead of running Goose (and paying for the model) again. Only the turn that was interrupted runs twice, and the Goose session is the same one before and after the crash. The restarted process also starts disarmed, so the re-run turn 2 asks you to kill the app rather than killing it again.

### 6. Collect the answer

The run recovered on its own, but the crash also killed the request that was waiting for its answer. Once the lines above have appeared, send the **identical** request from step 4 once more. Because the instance already exists, this call attaches to it rather than starting a second one, and the handler says so:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:8001/crash/run \
  -H "Content-Type: application/json" \
  -d '{"id": "release-42", "prompt": "Write release notes for version 2.5.0 to RELEASE_NOTES.md: it adds offline mode and fixes the CSV export crash.", "kill_after_seconds": 8}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/crash/run' -ContentType 'application/json' -Body '{"id": "release-42", "prompt": "Write release notes for version 2.5.0 to RELEASE_NOTES.md: it adds offline mode and fixes the CSV export crash.", "kill_after_seconds": 8}'
```

```text
== APP - release-manager == >>> Attaching to the existing run release-42 instead of starting a second one
== APP - release-manager == POST /crash/run 200
```

The reply uses the one JSON shape every crash demo in this repo returns, `{"id", "result", "message"}`. If the run has already finished, Goose's reply to the last turn, the finished release notes, comes back in `result` with `message` null, with status `200`. If the wait budget (`CRASH_WAIT_SECONDS`, 120 by default) elapses first, the same shape comes back as a `202` with `result` null and the attach instruction in `message`. That is not a failure: send the same request again to attach again. A request without an `id` is a `400`, and a run that failed or was terminated is a `500` whose `message` names the reason.

### Optional: crash the app yourself

Leave `kill_after_seconds` out and nothing is armed: turn 2 asks you to kill the app instead, and the rest of the walkthrough is identical. Start the run without the field:

**macOS/Linux (curl):**

```bash
curl -X POST http://localhost:8001/crash/run \
  -H "Content-Type: application/json" \
  -d '{"id": "release-43", "prompt": "Write release notes for version 2.6.0 to RELEASE_NOTES.md: it adds team workspaces."}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri 'http://localhost:8001/crash/run' -ContentType 'application/json' -Body '{"id": "release-43", "prompt": "Write release notes for version 2.6.0 to RELEASE_NOTES.md: it adds team workspaces."}'
```

Then, from a third terminal, while turn 2 is still running:

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

The endpoint calls `std::process::exit(1)`, so the process is gone before it can answer and this request itself reports a connection reset rather than a status code. That is expected: a process that answers politely has not crashed.

```text
== APP - release-manager == >>> /crash/kill: killing this process to simulate a worker crash
```

Then restart (step 5) and collect the answer (step 6) with the same body you started this run with.

The length of turn 2's window is configurable through the `CRASH_DELAY_SECONDS` environment variable, which defaults to 10. Set it lower to shorten the window, or higher if you need more time to aim.

## Good to know

- **Connect with `diagrid_goose::workflow_client()`, not `WorkflowClient::new()`.** The Dapr Rust SDK (`dapr` 0.19.0) connects to its sidecar in plaintext and sends no API token. That works against a local `dapr run` sidecar, but not against Catalyst, which requires TLS and the app's `DAPR_API_TOKEN` on every call. `diagrid-goose`'s `workflow_client()` adds both when the endpoint needs them, and is the plain SDK client otherwise. Use it in your own apps too.
- **Goose runs unattended.** It approves its own tool calls, since nobody is there to ask, so each run gets a scratch directory of its own under your system's temp directory: the `Workspace` line in step 1.
- **Goose keeps its sessions in its own store**, under `~/.local/share/goose` by default (or `GOOSE_PATH_ROOT`), and a resumed turn reloads its session from there. A worker that restarts on another machine needs that store on a volume both can reach.

## Clean Up

Stop the running application with `Ctrl+C`, then delete the Catalyst project:

```bash
diagrid project delete goose-quickstart
```

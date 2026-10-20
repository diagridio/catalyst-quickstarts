"""Suite data for the agents/goose quickstart, crash-recovery flow.

Mirrors agents/goose/README.md, section "## Crash Recovery Test With Catalyst".
Commands are transcribed verbatim from that README with the documented project
name replaced by `{project}`. Log markers are read out of src/bin/crash_test.rs,
because the README quotes them only as sample output.

This suite runs dev-crash-test.yaml, not the README's main flow
(dev-goose.yaml, `cargo run`), which runs one two-turn conversation and exits.
That flow is in UNCOVERED.

goose calls a real model, so nothing here asserts on model prose. Assertions
rest on log markers the app prints itself and on framework-generated response
fields.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

FAMILY = "agents"
NAME = "goose"
LANGUAGE = "rust"

# README "### 1. Login and Run", step 2.
DOCUMENTED_PROJECT = "goose-quickstart"
QUICKSTART_DIR = str(REPO_ROOT / "agents" / "goose")

# README "### 1. Login and Run", steps 2 and 3, verbatim. No --deploy-managed-kv:
# the quickstart uses workflows and nothing else, and its README documents none.
SETUP = (
    "diagrid project create {project} --enable-managed-workflow --wait --use",
    "diagrid agent create release-manager --wait",
)

# README "## Setup". The documented `cd agents/goose` is the working directory.
# Build Quickstart allows it 900s, which a cold build of the Dapr SDK and its
# gRPC stack fits inside.
INSTALL = "cargo build"

# README "### 3. Start the app".
RUN = "diagrid dev run -f dev-crash-test.yaml --approve"

# Empty on purpose. The README documents `diagrid project delete <name>`
# ("## Clean Up"), but the command stops at an interactive confirmation prompt, so
# running it as a documented step waits out Run Process's 10 minute timeout
# without deleting anything. Deleting the ephemeral project is infrastructure:
# ci/teardown-project.sh owns it (it passes --yes). The command is in UNCOVERED.
TEARDOWN = ()

# README "### 3. Start the app": "Wait for `Crash demo listening on http://0.0.0.0:8001`".
READY_MARKERS = ("Crash demo listening on",)

# crash_test.rs serves GET / only once the workflow worker has started (it binds
# the port after start_worker()), on APP_PORT 8001.
HEALTH_PROBES = ((8001, "/"),)

APP_PORT = 8001

# appID from dev-crash-test.yaml; the app (src/bin/crash_test.rs) listens on APP_PORT.
CONNECTED_APPS = (("release-manager", APP_PORT),)

# Catalyst fetching the app's Dapr config through the tunnel. crash_test.rs logs
# one access line per request (`GET /dapr/config 404`), the way uvicorn does for
# the Python siblings, so the probe is visible. Seen in the 2026-10-20 Catalyst
# runs after `Crash demo listening on`. See variables/agents_langgraph.py for the
# measurement behind this gate.
CATALYST_PROBE_MARKERS = ("GET /dapr/config",)

# README "## Setup", "Set your API key". Keep in step with `secrets` in suites.py.
SECRETS = ("OPENAI_API_KEY",)

# README "### 4. Run under an ID you own" uses this id and prompt.
CRASH_ID = "release-42"
CRASH_PROMPT = (
    "Write release notes for version 2.5.0 to RELEASE_NOTES.md: it adds offline "
    "mode and fixes the CSV export crash."
)

# README "### 4.": the self-kill, kept below CRASH_DELAY_SECONDS (10).
KILL_AFTER_SECONDS = 8

# Log markers from crash_test.rs. None depends on model output: the turn lines are
# chosen from each turn's durable input, not from anything Goose said, and the
# Goose session id that follows them is never part of a marker.
#
# Step 1 is turn 1. Both of its lines start with this, and no other line does, so
# after the restart it catches turn 1 starting again, not just finishing again.
STEP1_MARKER = ">>> TURN 1"
# A fragment of the ARMED variant only, so a turn 2 that failed to arm cannot
# satisfy it the way the un-armed line would.
STEP2_ARMED_MARKER = f"but this process kills itself {KILL_AFTER_SECONDS}s into the run, as asked by kill_after_seconds"
SELF_KILL_MARKER = ">>> crash: "
STEP2_DONE_MARKER = ">>> TURN 2 COMPLETE:"
ATTACH_MARKER = ">>> Attaching to the existing run"

# README "### 6. Collect the answer": the identical request from step 4, with
# kill_after_seconds (ignored on attach). 200 with `result` set and `message` null.
REQUESTS = (
    {
        "method": "POST",
        "port": APP_PORT,
        "path": "/crash/run",
        "payload": {
            "id": CRASH_ID,
            "prompt": CRASH_PROMPT,
            "kill_after_seconds": KILL_AFTER_SECONDS,
        },
        "status": 200,
        "field": "result",
        "log_marker": ATTACH_MARKER,
    },
)

# Documented commands this suite does not run, each with its reason.
UNCOVERED = (
    (
        "diagrid project delete goose-quickstart",
        "README '## Clean Up'. It prompts \"Are you sure you want to proceed? "
        "(Y/N)\" and so hangs for the Run Process timeout when run "
        "non-interactively or from a terminal; ci/teardown-project.sh deletes the "
        "ephemeral project with --yes instead.",
    ),
    (
        "diagrid dev run -f dev-goose.yaml --approve",
        "this suite covers the crash-recovery flow; the happy-path main.rs "
        "conversation (cargo run) is not covered here",
    ),
    (
        "curl -fsSL https://github.com/aaif-goose/goose/releases/download/stable/download_cli.sh | CONFIGURE=false GOOSE_VERSION=v1.54.0 bash",
        "README 'Install Goose' is a prerequisite. The e2e-agents job's own "
        "`Install Goose` step runs this same pinned install before the suite.",
    ),
    (
        'curl -X POST http://localhost:8001/crash/run -H "Content-Type: application/json" -d \'{"id": "release-43", "prompt": "Write release notes for version 2.6.0 to RELEASE_NOTES.md: it adds team workspaces."}\'',
        "README 'Optional: crash the app yourself' starts the un-armed run that "
        "the two-terminal POST /crash/kill variant needs. This suite sends "
        "kill_after_seconds instead, so the self-crash path is what runs.",
    ),
    (
        "curl -X POST http://localhost:8001/crash/kill",
        "README 'Optional: crash the app yourself' is the variant the README "
        "offers instead of kill_after_seconds. This suite sends "
        "kill_after_seconds, so the self-crash path is what runs. Covering both "
        "would mean racing a kill against a live window for no extra assertion.",
    ),
)


def get_quickstart():
    """Everything the suite needs, in one flat dict.

    Robot calls this as a keyword: `${qs}=  Get Quickstart`.
    """
    return {
        "family": FAMILY,
        "name": NAME,
        "language": LANGUAGE,
        "dir": QUICKSTART_DIR,
        "setup": list(SETUP),
        "install": INSTALL,
        "run": RUN,
        "teardown": list(TEARDOWN),
        "health_probes": [list(probe) for probe in HEALTH_PROBES],
        "catalyst_probe_markers": list(CATALYST_PROBE_MARKERS),
        "connected_apps": [list(pair) for pair in CONNECTED_APPS],
        "secrets": list(SECRETS),
    }

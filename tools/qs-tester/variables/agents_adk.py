"""Suite data for the agents/adk quickstart, crash-recovery flow.

Mirrors agents/adk/README.md, section "## Crash Recovery Test With Catalyst".
Commands are transcribed verbatim from that README with the documented project
name replaced by `{project}`. Log markers are read out of crash_test.py, because
the README quotes them only in part.

This suite runs dev-crash-test.yaml, not the README's main flow
(dev-python-adk.yaml, POST /agent/run). That flow is in UNCOVERED.

adk calls a real model, so nothing here asserts on model prose. Assertions
rest on log markers the tools print themselves and on framework-generated
response fields.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

FAMILY = "agents"
NAME = "adk"
LANGUAGE = "python"

# README "### 1. Login and Run", step 2.
DOCUMENTED_PROJECT = "adk-quickstart"
QUICKSTART_DIR = str(REPO_ROOT / "agents" / "adk")

# README "### 1. Login and Run", steps 2 and 3, verbatim.
SETUP = (
    "diagrid project create {project} --enable-managed-workflow --deploy-managed-kv --deploy-managed-pubsub --wait --use",
    "diagrid agent create entertainment-planner --wait",
)

# README "## Setup". The documented `cd agents/adk` is the working directory.
INSTALL = "uv sync"

# README "### 4. Start the app".
RUN = "uv run diagrid dev run -f dev-crash-test.yaml --approve"

# Empty: the README documents no cleanup command (no "Clean Up" section), so the
# project is deleted by ci/teardown-project.sh. Inventing a `project delete`
# here would be an undocumented command that doc-sync rejects.
TEARDOWN = ()

# README "### 4. Start the app": "Wait for `Uvicorn running on http://0.0.0.0:8001`".
READY_MARKERS = ("Uvicorn running on",)

# crash_test.py serves GET / once the runner has registered, on appPort 8001.
HEALTH_PROBES = ((8001, "/"),)

APP_PORT = 8001

# appID from dev-crash-test.yaml; the app (crash_test.py) listens on APP_PORT.
CONNECTED_APPS = (("entertainment-planner", APP_PORT),)

# Catalyst fetching the app's Dapr config through the tunnel. The request arriving
# is the signal; a workflow call made before it hangs for good. See
# variables/agents_langgraph.py for the measurement behind this gate.
CATALYST_PROBE_MARKERS = ("GET /dapr/config",)

# README "## Setup", "Set your API key". Keep in step with `secrets` in suites.py.
SECRETS = ("OPENAI_API_KEY",)

# README "### 5. Run under an ID you own" uses this id and prompt.
CRASH_ID = "party-42"
CRASH_PROMPT = "Find entertainment for a corporate holiday party"

# README "### 5.": the self-kill variant, kept below CRASH_DELAY_SECONDS (10).
KILL_AFTER_SECONDS = 8

# Log markers from crash_test.py. Each is a fixed prefix that does not depend on
# model output (the event type and the model's phrasing never enter them).
STEP1_MARKER = ">>> TOOL 1 COMPLETE: Found 3 entertainment options for"
STEP2_ARMED_MARKER = ">>> TOOL 2: Comparing options over ~"
SELF_KILL_MARKER = ">>> crash: "
STEP2_DONE_MARKER = ">>> TOOL 2 COMPLETE:"
ATTACH_MARKER = ">>> Attaching to the existing run"

# README "### 8. Collect the answer": the identical request without
# kill_after_seconds. 200 with `result` set and `message` null.
REQUESTS = (
    {
        "method": "POST",
        "port": APP_PORT,
        "path": "/crash/run",
        "payload": {"id": CRASH_ID, "prompt": CRASH_PROMPT},
        "status": 200,
        "field": "result",
        "log_marker": ATTACH_MARKER,
    },
)

# Documented commands this suite does not run, each with its reason.
UNCOVERED = (
    (
        "uv run diagrid dev run -f dev-python-adk.yaml --approve",
        "this suite covers the crash-recovery flow; the happy-path /agent/run "
        "flow is not covered here",
    ),
    (
        'curl -i -X POST http://localhost:8003/agent/run -H "Content-Type: application/json" -d \'{"task": "Find entertainment for a corporate networking event"}\'',
        "this suite covers the crash-recovery flow; the happy-path /agent/run "
        "flow is not covered here",
    ),
    (
        "curl -X POST http://localhost:8001/crash/kill",
        "README '### 6. Crash the app' is the two-terminal variant, and the "
        "README itself says to skip it when kill_after_seconds is sent. This "
        "suite sends it, so the self-crash path is what runs. Covering both "
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

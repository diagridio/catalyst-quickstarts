"""Suite data for the agents/mastra quickstart, crash-recovery flow.

Mirrors agents/mastra/README.md, section "## Crash Recovery Test With Catalyst".
Commands are transcribed verbatim from that README with the documented project
name replaced by `{project}`. Log markers are read out of crash_test.ts, because
the README quotes them only as sample output.

This suite runs dev-crash-test.yaml, not the README's main flow
(dev-mastra.yaml, `npm start`), which runs one turn and exits. That flow is in
UNCOVERED.

mastra calls a real model, so nothing here asserts on model prose. Assertions
rest on log markers the app prints itself and on framework-generated response
fields.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

FAMILY = "agents"
NAME = "mastra"
LANGUAGE = "javascript"

# README "### 1. Login and Run", step 2.
DOCUMENTED_PROJECT = "mastra-quickstart"
QUICKSTART_DIR = str(REPO_ROOT / "agents" / "mastra")

# README "### 1. Login and Run", steps 2 and 3, verbatim.
SETUP = (
    "diagrid project create {project} --enable-managed-workflow --deploy-managed-kv --wait --use",
    "diagrid agent create sre-agent --wait",
)

# README "## Setup". The documented `cd agents/mastra` is the working directory.
# `npm install`, not `npm ci`: an agent row's INSTALL is compared against the
# README's own bash lines, so `npm ci` would fail doc-sync.
INSTALL = "npm install"

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

# crash_test.ts serves GET / only once the runner has started (it listens after
# runner.start()), on APP_PORT 8001.
HEALTH_PROBES = ((8001, "/"),)

APP_PORT = 8001

# appID from dev-crash-test.yaml; the app (crash_test.ts) listens on APP_PORT.
CONNECTED_APPS = (("sre-agent", APP_PORT),)

# Catalyst fetching the app's Dapr config through the tunnel. crash_test.ts logs
# one access line per request (`GET /dapr/config 404`), the way uvicorn does for
# the Python siblings, so the probe is visible. See variables/agents_langgraph.py
# for the measurement behind this gate.
CATALYST_PROBE_MARKERS = ("GET /dapr/config",)

# README "## Setup", "Set your API key". Keep in step with `secrets` in suites.py.
SECRETS = ("OPENAI_API_KEY",)

# README "### 4. Run under an ID you own" uses this id and prompt.
CRASH_ID = "inc-4471"
CRASH_PROMPT = "What is the status of incident INC-4471?"

# README "### 4.": the self-kill, kept below CRASH_DELAY_SECONDS (10).
KILL_AFTER_SECONDS = 8

# Log markers from crash_test.ts. None depends on model output: the model call
# lines are numbered from the workflow's iteration index and carry the run id we
# chose, and the step 2 markers stop before, or start after, the incident id the
# model passes to the tool.
#
# Step 1 is model call 1. The trailing space stops it matching `Model call 10`.
STEP1_MARKER = ">>> Model call 1 for run "
# A fragment of the ARMED variant only, so a step 2 that failed to arm cannot
# satisfy it the way the un-armed line would.
STEP2_ARMED_MARKER = f"but this process kills itself {KILL_AFTER_SECONDS}s into the run, as asked by kill_after_seconds"
SELF_KILL_MARKER = ">>> crash: "
STEP2_DONE_MARKER = ">>> STEP 2 COMPLETE:"
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
        "diagrid project delete mastra-quickstart",
        "README '## Clean Up'. It prompts \"Are you sure you want to proceed? "
        "(Y/N)\" and so hangs for the Run Process timeout when run "
        "non-interactively or from a terminal; ci/teardown-project.sh deletes the "
        "ephemeral project with --yes instead.",
    ),
    (
        "diagrid dev run -f dev-mastra.yaml --approve",
        "this suite covers the crash-recovery flow; the happy-path main.ts turn "
        "(npm start) is not covered here",
    ),
    (
        "ollama serve &",
        "README 'Using a local model instead' is an alternative to OpenAI; the "
        "suite uses the documented default, OPENAI_API_KEY",
    ),
    (
        "ollama pull qwen3:0.6b",
        "README 'Using a local model instead' is an alternative to OpenAI; the "
        "suite uses the documented default, OPENAI_API_KEY",
    ),
    (
        'curl -X POST http://localhost:8001/crash/run -H "Content-Type: application/json" -d \'{"id": "inc-4472", "prompt": "What is the status of incident INC-4472?"}\'',
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

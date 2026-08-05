"""Data for the agents/langgraph end-to-end suite.

Every command here is transcribed verbatim from agents/langgraph/README.md, with
one substitution: the documented project name becomes `{project}`. The README is
the source of truth. Change the README, change this file, and
`docsync/check_readme_sync.py --all` will tell you if you changed only one.

Unlike the canonical quickstarts, this README documents its own provisioning, so
SETUP runs the documented `project create` and `agent create` rather than the
invented flags in ci/setup-project.sh. The `dev run` command stays bare because
the documented `project create` carries `--use`: reproducing that dependency is
deliberate, so that a regression in `--use` breaks this suite instead of
silently breaking readers.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

FAMILY = "agents"
NAME = "langgraph"
LANGUAGE = "python"

# README "## Run with Catalyst", step 2. Replaced by an ephemeral qs-ci-* name at
# run time; also what doc-sync maps onto `{project}` when comparing.
DOCUMENTED_PROJECT = "langgraph-quickstart"

QUICKSTART_DIR = str(REPO_ROOT / "agents" / "langgraph")

# README "## Run with Catalyst", steps 2 and 3.
SETUP = (
    "diagrid project create {project} --enable-agent-infrastructure --wait --use",
    "diagrid agent create langgraph-agent --wait",
)

# README "## Setup". The documented `cd agents/langgraph` is expressed as the
# working directory instead of a command.
INSTALL = "uv sync"

# README "## Run with Catalyst", step 4. Bare on purpose: see the module docstring.
RUN = "uv run diagrid dev run -f dev-python-langgraph.yaml --approve"

# Empty on purpose: this README documents no cleanup command. It has no
# "## Clean Up" section, unlike agents/microsoft-dotnet (which documents
# `diagrid project delete dotnet-quickstart`) and the canonical READMEs (section
# 7). Deleting the project is therefore infrastructure, not a documented step, and
# ci/teardown-project.sh owns it. Adding a plausible-looking `project delete` here
# would be inventing a documented command, and doc-sync would correctly reject it.
TEARDOWN = ()

# README: "Wait until the output shows `Uvicorn running on <localhost:port>`."
# Truncated before the address, which varies. A tuple because multi-app
# quickstarts announce themselves once per app: dapr-agents/multi-agent-workflow
# runs three. langgraph has one.
READY_MARKERS = ("Uvicorn running on",)

# appPort in dev-python-langgraph.yaml, and the port the documented curl targets.
HEALTH_PORTS = (8005,)

SECRETS = ("OPENAI_API_KEY",)

# The documented calls, in documented order. README "### 2. Trigger a Workflow".
#
# Optional keys a request may carry, unused here:
#   commands    documented commands to run before this request, for flows that
#               interleave CLI and HTTP (mcp-auth grants a tool between two calls)
#   log_marker  a string to wait for in the dev-run output after this request
#
# `field` is None because no README documents a response body for /agent/run, and
# the endpoint is served by DaprWorkflowGraphRunner.serve() from an external
# package, so the field name cannot be read out of this repo. The suite asserts
# the documented status code only. Fill this in from an observed live response,
# with a comment naming that response as the source; guessing a field name
# produces an assertion that looks like coverage and fails for the wrong reason.
# This is the same weak-assertion tradeoff the harness already accepts for the
# undocumented `GET /workflow/status/{id}` bodies.
REQUESTS = (
    {
        "method": "POST",
        "port": 8005,
        "path": "/agent/run",
        "payload": {"task": "Check if the Grand Ballroom is available on March 15th"},
        "status": 200,
        "field": None,
        # The README describes the agent using the `check_availability` tool, and
        # main.py defines it. Model output varies; the tool call is what the
        # quickstart actually promises, so that is what this asserts.
        "log_marker": "check_availability",
    },
)

# Documented commands this suite deliberately does not run, each with its reason.
# doc-sync fails if a documented command is in neither this tuple nor the suite,
# so a new documented step forces a decision instead of being quietly ignored.
UNCOVERED = (
    (
        "uv run diagrid dev run -f dev-crash-test.yaml --approve",
        "crash-recovery flow requires editing crash_test.py to comment out "
        "os._exit(1); source edits are out of scope",
    ),
    (
        "uv run diagrid dev run -f dev-crash-test.yaml",
        "the second half of the same crash-recovery flow",
    ),
)


def get_quickstart():
    """Everything the suite needs, in one flat dict.

    Robot calls this as a keyword: `${qs}=  Get Quickstart`. Mirrors the shape
    quickstarts.get_quickstart returns so the shared keywords need no changes.
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
        "health_ports": list(HEALTH_PORTS),
        "secrets": list(SECRETS),
    }

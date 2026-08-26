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

# README "## Run with Catalyst", steps 2 and 3. `--enable-agent-infrastructure`
# was replaced by the three managed-service flags; the agent is now named for its
# role in the shared event-planning scenario rather than for its framework.
SETUP = (
    "diagrid project create {project} --enable-managed-workflow --deploy-managed-kv --deploy-managed-pubsub --wait --use",
    "diagrid agent create schedule-planner --wait",
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

# (port, path) pairs `Wait Until Apps Healthy` polls for a 200 before asserting
# anything. Port 8005 is the appPort in dev-python-langgraph.yaml, and the port
# the documented curl targets.
#
# The path is NOT `/`, which is what the canonical suites probe. This app serves
# no `/`: main.py builds the graph and calls DaprWorkflowGraphRunner.serve(...),
# and that method (diagrid==0.4.2, pinned in this quickstart's pyproject.toml and
# uv.lock; diagrid/agent/core/workflow/runner.py, serve()) creates a bare
# `FastAPI()` and registers exactly four routes:
#
#   POST /agent/run
#   GET  /agent/run/{workflow_id}
#   GET  /dapr/subscribe                 (only when pubsub_name and subscribe_topic
#   POST /events/{subscribe_topic}        are both passed — main.py passes both)
#
# There is no root route and no /health, so `GET /` returns 404 and a `/` probe
# would wait out the full readiness timeout on a perfectly healthy app.
# `GET /dapr/subscribe` is used instead: it is a route this app really registers
# (runner.serve() adds it because main.py passes pubsub_name="agent-pubsub" and
# subscribe_topic="schedule.requests"), it needs no request body, and it answers
# 200 with the subscription list. Verified by rebuilding that exact route set on
# fastapi==0.136.1 (the version this quickstart's uv.lock pins) and requesting
# each path: `/` -> 404, `/dapr/subscribe` -> 200.
#
# Applies to every entry: one path per port, so an agent quickstart whose apps
# serve different probe paths states them per app here rather than needing a new
# keyword.
HEALTH_PROBES = ((8005, "/dapr/subscribe"),)

# (appID, port) pairs that `diagrid dev run` reports as
# `Connected App ID "<id>" to http://localhost:<port>`. Read from
# dev-python-langgraph.yaml, whose single app has appID schedule-planner on
# appPort 8005.
#
# Required, not optional: `Start Quickstart` records these so `Stop Quickstart`
# can release each local app connection, and a run that skips that leaves a
# trust.diagrid.io endpoint pointing at a dead tunnel, which makes the next run's
# 500s ambiguous.
#
# INFERRED, NOT OBSERVED: the harness README's rule is that the CLI prints the
# connection line for an app with a non-zero appPort, and this app's is 8005. No
# live run has confirmed the line appears for an agent app. If it does not,
# `Wait Until Apps Connected` waits out READINESS_TIMEOUT and the fix is to drop
# the gate rather than to widen the timeout.
CONNECTED_APPS = (("schedule-planner", 8005),)

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
# the status code and nothing else — and note that this README documents no
# status code either, so the 200 below is an assumption too, merely a plausible
# one (unlike the two crash-on-purpose quickstarts, this endpoint is expected to
# return normally). Fill this in from an observed live response,
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

    Robot calls this as a keyword: `${qs}=  Get Quickstart`.

    This is NOT the same dict `quickstarts.get_quickstart(api, language)`
    returns. The two share exactly the five keys the *shared* keywords read —
    `dir`, `install`, `run`, `health_probes` and `connected_apps` (grep
    `${qs}[...]` and `$qs["..."]` across resources/catalyst.resource and
    resources/quickstart.resource for the complete set) — which is what lets
    `Build Quickstart`, `Start Quickstart`, `Wait Until Apps Connected` and
    `Wait Until Apps Healthy` work against either shape unchanged. `language`
    is NOT among them, even though both dicts happen to carry a `language` key
    of their own (this module's `LANGUAGE` constant; the canonical dict's
    `language` parameter): no shared keyword reads either one. Beyond the
    shared five, this dict adds `family`, `name`, `language`, `setup`,
    `teardown` and `secrets`; the canonical one adds `api` and `language`.
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
        "connected_apps": [list(pair) for pair in CONNECTED_APPS],
        "secrets": list(SECRETS),
    }

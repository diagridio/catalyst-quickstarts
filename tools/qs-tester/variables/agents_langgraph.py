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
# (runner.serve() adds it because main.py passes pubsub_name="pubsub" and
# subscribe_topic="schedule.requests"), it needs no request body, and it answers
# 200 with the subscription list. Verified by rebuilding that exact route set on
# fastapi==0.136.1 (the version this quickstart's uv.lock pins) and requesting
# each path: `/` -> 404, `/dapr/subscribe` -> 200.
#
# It proves the app's own server is up and NOTHING about Catalyst — see
# CATALYST_PROBE_MARKERS below, which is the gate that closes that gap.
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
# OBSERVED, as of the 2026-08-27 live run: `diagrid dev run` really does print
# `Connected App ID "schedule-planner" to http://localhost:8005` for an agent app,
# confirming the harness README's appPort rule holds here. `Wait Until Apps
# Connected` passed on it in 36s. Note what that does NOT prove: the line means
# the local dev tunnel is up, not that Catalyst can route the app's workflow
# calls. See CATALYST_PROBE_MARKERS.
CONNECTED_APPS = (("schedule-planner", 8005),)

# Strings that appear in the captured `diagrid dev run` output once Catalyst has
# attached to the app and started probing it back through the dev tunnel. This is
# the last gate `Wait Until Catalyst Attached` waits on, and the only readiness
# signal in this module that says anything about Catalyst rather than about the
# local process.
#
# Why it exists, measured 2026-08-27 against a real project: the documented POST
# fired 25ms after the health probe went green hung for the full 120s client
# timeout and never created a workflow instance (ERR_INSTANCE_ID_NOT_FOUND when
# queried afterwards). It does not recover — twelve retries over 181s all hung —
# so the first request into the window poisons the app's workflow client for good.
# Gated on this marker, the same request answered 200 in ~1s on three consecutive
# runs, with the marker arriving at t+1s, t+3s and t+3s.
#
# `GET /dapr/config` is Catalyst fetching the app's Dapr configuration through the
# tunnel. The app has no such route and answers 404 — irrelevant, because the
# REQUEST ARRIVING is the signal, not the response. uvicorn's access log is what
# makes it visible, which is why this is per-quickstart data and not a constant.
#
# Do NOT replace this with an active probe. Two obvious ones were tried and are
# VACUOUS: the app's own `GET /agent/run/{workflow_id}` answers 404 in 71ms at
# readiness+0 while the POST beside it hangs (different RPCs — `GetInstance` is
# live, `StartInstance` is not), and Catalyst's workflow HTTP API answers 202 in
# the same window while its worker executes work items one second in. Neither
# distinguishes the window at all.
CATALYST_PROBE_MARKERS = ("GET /dapr/config",)

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
        # OBSERVED, 2026-08-28: the response envelope is built by
        # DaprWorkflowGraphRunner (`_run_and_collect` plus langgraph's
        # `_parse_output`) and carries instance_id, type, workflow_id, output,
        # steps and status. `status` is the one worth asserting: it exists ONLY on
        # the completed path — a failed run yields {"type": "workflow_failed",
        # "error": ...} with no `status` key at all, so the presence check
        # `POST And Expect Field` performs is exactly the success/failure
        # discriminator. It is framework-generated, so unlike anything under
        # `output.messages` it does not vary with the model.
        "field": "status",
        # NOT `check_availability`. That string appears in the README's prose and
        # main.py defines the tool, but NOTHING PRINTS IT: `call_tools` invokes the
        # tool without logging, so the old marker could never match a real run —
        # it timed out on the 2026-08-28 run that otherwise succeeded end to end.
        # doc-sync did not catch it because it only requires the marker to appear
        # somewhere in the README, and a prose mention satisfied that.
        #
        # The tools NODE is printed, by the SDK itself:
        # `print(f"  [ACTIVITY] Executing node '{node_name}' as Dapr activity")`
        # in diagrid/agent/langgraph/workflow.py (diagrid 0.4.2, pinned in this
        # quickstart's uv.lock). It is the right assertion for what the README
        # promises: `should_use_tools` routes to `tools` only when the LLM returned
        # a tool call, so an agent that answered without checking availability
        # never reaches this node and the marker never appears.
        "log_marker": "[ACTIVITY] Executing node 'tools' as Dapr activity",
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
    `teardown`, `secrets` and `catalyst_probe_markers`; the canonical one adds `api`
    and `language`.

    `catalyst_probe_markers` is agent-only despite being read by a keyword in
    the shared `catalyst.resource`: `Wait Until Catalyst Attached` guards a
    window only the agent suites enter, because only they start Catalyst
    workflows. The canonical dict does not carry the key and the canonical
    suites never call the keyword, so nothing there breaks.
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

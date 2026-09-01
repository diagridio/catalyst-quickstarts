"""Data for the agents/microsoft-dotnet end-to-end suite.

Every command is transcribed verbatim from agents/microsoft-dotnet/README.md, with
the documented project name replaced by `{project}`. Change the README, change
this file, and `docsync/check_readme_sync.py --all` will say so if you change only
one.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

FAMILY = "agents"
NAME = "microsoft-dotnet"
LANGUAGE = "csharp"

DOCUMENTED_PROJECT = "dotnet-quickstart"
QUICKSTART_DIR = str(REPO_ROOT / "agents" / "microsoft-dotnet")

# README "## Run with Catalyst", steps 2 and 3.
SETUP = (
    "diagrid project create {project} --enable-managed-workflow --deploy-managed-kv --deploy-managed-pubsub --wait --use",
    "diagrid agent create event-planner --wait",
)

# README "## Setup". The documented `cd agents/microsoft-dotnet` is expressed as
# the working directory instead of a command.
INSTALL = "dotnet build"

RUN = "diagrid dev run -f dev-dotnet-agent.yaml --approve"

# README "## Clean Up". Unlike langgraph, this quickstart documents its cleanup,
# so the suite runs it.
TEARDOWN = ("diagrid project delete {project}",)

# README: "Wait until the output shows `Established gRPC bidirectional stream with
# Dapr sidecar`." Not a Uvicorn line: the marker is a property of the framework,
# and this is a .NET app.
READY_MARKERS = ("Established gRPC bidirectional stream with Dapr sidecar",)

# EMPTY ON PURPOSE. Program.cs registers exactly one route, `app.MapPost("/run")`,
# so there is no GET path to probe and `GET /` would 404 for the whole readiness
# timeout on a perfectly healthy app. Readiness rests on the connection gate below
# plus the documented marker above. If a health endpoint is ever added, probe it.
HEALTH_PROBES = ()

# appID and appPort from dev-dotnet-agent.yaml.
CONNECTED_APPS = (("event-planner", 5050),)

# EMPTY, NOT VERIFIED. `Wait Until Catalyst Attached` waits for the first inbound
# request Catalyst makes back through the dev tunnel, which is the point at which
# workflow calls stop hanging. Measured on agents/langgraph 2026-08-27: a call
# made before that hangs forever and twelve retries over 181s never recovered it,
# while the same call gated on the marker answered in ~1s three runs running.
# Nothing about that race is Python-specific, so this suite is very likely exposed
# to it too.
#
# It is empty rather than guessed because the marker is whatever THIS app's
# logging makes visible for an inbound request, and this ASP.NET app's request logging has not been
# checked. A marker that never appears makes the gate time out (loud, and the
# suite fails); a marker matched from the wrong line would let the suite through
# early (silent, and the run hangs). Fill this in by running the quickstart once
# and reading what the app logs when Catalyst probes it.
CATALYST_PROBE_MARKERS = ()

# Empty because the quickstart ships a canned offline model and only calls a real
# provider when DIAGRID_QUICKSTART_MODEL=openai, which is not the path this suite
# covers. Keep it in step with the `secrets` entry in suites.py: the two together
# are the declaration that this suite needs no credential, and one without the
# other is a declaration that lies.
SECRETS = ()

# README "### 2. Trigger the Agent".
#
# OBSERVED, 2026-08-31, against a local OneBox Catalyst project with no model key
# set. `POST /run` returned 200 in ~30s with the body:
#
#     {"response":"Booking confirmed for Grand Ballroom. All steps complete!"}
#
# so `field` is "response". With the canned offline model that body is fixed: the
# final turn echoes step_three_confirm's return string rather than model prose.
#
# `status` is 200 and is no longer a guess either. It used to be one because this
# call ran the crash: the README said of it "The process exits — this is
# expected", so a connection error was likelier than any status code. Both halves
# of that have since changed. The crash moved to POST /crash/run and is armed by
# kill_after_seconds, so /run arms nothing and runs to completion. Tool 2 still
# sleeps ~30s, which is inside `POST And Expect Field`'s 120s budget.
REQUESTS = (
    {
        "method": "POST",
        "port": 5050,
        "path": "/run",
        "payload": {"prompt": "Find a venue in Austin for a company gala"},
        "status": 200,
        "field": "response",
    },
)

# Documented commands this suite deliberately does not run, each with its reason.
UNCOVERED = (
    (
        "dotnet test unit-tests",
        "unit tests for the offline model. This suite drives the running "
        "quickstart against Catalyst; the same assertions do not need making "
        "twice, and the test project is a separate build",
    ),
)


def get_quickstart():
    """Everything the suite needs, in one flat dict."""
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

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

SECRETS = ("OPENAI_API_KEY",)

# README "### 2. Trigger the Agent".
#
# `field` is None because the README documents no response body. Fill it in from
# an observed live response with a comment naming that response as the source.
REQUESTS = (
    {
        "method": "POST",
        "port": 5050,
        "path": "/run",
        "payload": {"prompt": "Find a venue in Austin for a company gala"},
        "status": 200,
        "field": None,
    },
)

# Documented commands this suite deliberately does not run, each with its reason.
UNCOVERED = (
    (
        "diagrid dev run -f dev-dotnet-agent.yaml",
        "the crash-recovery flow's resume step; the crash itself needs a source "
        "edit, so the whole flow is out of scope",
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
        "connected_apps": [list(pair) for pair in CONNECTED_APPS],
        "secrets": list(SECRETS),
    }

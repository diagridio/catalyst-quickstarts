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
# and this is a .NET app. OBSERVED in the 2026-08-28 live run, logged by
# Dapr.Workflow.Worker.Grpc.GrpcProtocolHandler just before "Now listening on".
READY_MARKERS = ("Established gRPC bidirectional stream with Dapr sidecar",)

# EMPTY ON PURPOSE. Program.cs registers exactly one route, `app.MapPost("/run")`,
# so there is no GET path to probe and `GET /` would 404 for the whole readiness
# timeout on a perfectly healthy app. Confirmed by the 2026-08-28 run, where
# Catalyst's own `GET /` probes answer 404 ("Request reached the end of the
# middleware pipeline without being handled by application code"). Readiness rests
# on the connection gate below, the documented marker above and the attach gate.
# If a health endpoint is ever added, probe it.
HEALTH_PROBES = ()

# appID and appPort from dev-dotnet-agent.yaml. OBSERVED 2026-08-28: `diagrid dev
# run` prints `Connected App ID "event-planner" to http://localhost:5050`.
CONNECTED_APPS = (("event-planner", 5050),)

# OBSERVED against a real project, 2026-08-28. `Wait Until Catalyst Attached`
# waits for the first inbound request Catalyst makes back through the dev tunnel,
# which is the point at which workflow calls stop hanging (measured on
# agents/langgraph 2026-08-27: a call made before that hangs forever and twelve
# retries over 181s never recovered it).
#
# This app could not have had a marker at all until 2026-08-28: both appsettings
# files set `"Microsoft.AspNetCore": "Warning"`, which suppresses ASP.NET Core's
# request logging entirely, so no inbound request was ever visible. Both are now
# `"Information"`. Both, not just one: `dotnet run` here uses the Production
# environment (there is no launchSettings.json), but a developer who sets
# ASPNETCORE_ENVIRONMENT=Development must see the same, and the Development file
# overrides the base one.
#
# What the live run actually logs, via Microsoft.AspNetCore.Hosting.Diagnostics,
# right after "Application started":
#
#   Request starting HTTP/1.1 GET http://tunnels-proxy.cloud.r1.diagrid.io:443/ - - -
#   Request starting HTTP/1.1 GET http://tunnels-proxy.cloud.r1.diagrid.io:443/dapr/config - application/json -
#
# TRUNCATED BEFORE THE DOMAIN on purpose. The predicted marker for this suite was
# `...GET http://localhost:5050/`, and it is WRONG: ASP.NET logs the request's
# own Host header, and Catalyst probes through its tunnel proxy, so the host is
# Catalyst's rather than the app's listen address. Had that guess been committed
# it would have timed out against a perfectly healthy quickstart and cost a
# project to discover. `cloud.r1` is region-specific and is dropped for the same
# reason — a project in another region would not match it.
#
# Matching only `http://tunnels-proxy` also keeps the marker inbound-only, which
# is what makes it a gate: it cannot match anything the harness itself sends
# (HEALTH_PROBES is empty here and the documented trigger is a POST to
# localhost), so it cannot go green before Catalyst has attached. It matches both
# the `/` and `/dapr/config` probes, so it does not depend on which arrives
# first.
#
# Note the format differs from agents/langgraph's `GET /dapr/config`: uvicorn
# logs the path alone, ASP.NET logs the full URL. That is precisely why this is
# per-quickstart data rather than a shared constant.
CATALYST_PROBE_MARKERS = ("Request starting HTTP/1.1 GET http://tunnels-proxy",)

SECRETS = ("OPENAI_API_KEY",)

# README "### 2. Trigger the Agent".
#
# No `status`, and that is a transcription rather than a gap. This README
# documents no status code, and of this very call it says "The process exits —
# this is expected": `step_two_compare` calls `Environment.Exit(1)` (Program.cs)
# while the request is in flight, so the app never reaches
# `Results.Ok(new { response = ... })` and the client sees the connection drop.
# A status code here would be an assertion the app cannot satisfy.
#
# `expect` says so explicitly. `POST And Expect The App To Exit` passes only when
# the connection drops; it FAILS on any status code — that is the crash having
# silently stopped happening, which is exactly the bug found on 2026-08-28, when
# Program.cs sat committed with the crash line commented out — and it FAILS
# distinctly on a timeout, because a hang is Catalyst's attach window and not
# this crash. CATALYST_PROBE_MARKERS above is empty, so a hang is a live
# possibility for this suite and must not read as a pass.
#
# `field` is absent for the same reason: there is no response body to name a
# field in.
#
# The log marker is the last line the README documents before the process dies
# (the "You'll see:" block, a `text` fence). `>>> TOOL 1 COMPLETE` would prove
# less — it is `step_two_compare` that carries the crash, so this marker is what
# shows the agent got as far as the tool the quickstart is about.
REQUESTS = (
    {
        "method": "POST",
        "port": 5050,
        "path": "/run",
        "payload": {"prompt": "Find a venue in Austin for a company gala"},
        "expect": "connection-dropped",
        "log_marker": ">>> TOOL 2: Comparing venues...",
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
        "catalyst_probe_markers": list(CATALYST_PROBE_MARKERS),
        "connected_apps": [list(pair) for pair in CONNECTED_APPS],
        "secrets": list(SECRETS),
    }

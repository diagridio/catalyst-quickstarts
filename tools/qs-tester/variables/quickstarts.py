"""Per-(api, language) data for the quickstart end-to-end suites.

Every value here is transcribed from `<api>/<language>/README.md`. The READMEs are
the source of truth: sections 4 and 5 give INSTALL and RUN, section 6 gives the
endpoints, payloads and EXPECTED_BODY values.

Robot suites read this through `get_quickstart(api, language)`.
"""

from pathlib import Path

LANGUAGES = ("csharp", "java", "javascript", "python")
APIS = ("workflow", "state", "pubsub", "invocation")

# This file is tools/qs-tester/variables/quickstarts.py, so the repository root is
# three levels up. Paths must be absolute: Robot runs from tools/qs-tester, so a
# relative "state/python" would resolve to tools/qs-tester/state/python and every
# build and run would fail with "directory does not exist".
REPO_ROOT = Path(__file__).resolve().parents[3]


def quickstart_dir(api, language):
    """Absolute path to the quickstart directory."""
    return str(REPO_ROOT / api / language)


# --- README section 4: install commands -------------------------------------
# Every python entry is the same single whole-workspace sync. `--all-packages` is
# what keeps the multi-app quickstarts safe: a sync scoped to one app would
# uninstall the other's dependencies from the shared venv.
INSTALL = {
    ("workflow", "csharp"): "dotnet build",
    ("workflow", "java"): "mvn clean install",
    ("workflow", "javascript"): "npm ci",
    ("workflow", "python"): "uv sync --all-packages",
    ("state", "csharp"): "dotnet restore",
    ("state", "java"): "mvn clean install",
    ("state", "javascript"): "npm ci",
    ("state", "python"): "uv sync --all-packages",
    ("pubsub", "csharp"): "dotnet restore ./publisher && dotnet restore ./subscriber",
    ("pubsub", "java"): "mvn clean install -f ./publisher && mvn clean install -f ./subscriber",
    ("pubsub", "javascript"): "npm ci --prefix ./publisher && npm ci --prefix ./subscriber",
    ("pubsub", "python"): "uv sync --all-packages",
    ("invocation", "csharp"): "dotnet restore ./client && dotnet restore ./server",
    ("invocation", "java"): "mvn clean install -f ./client && mvn clean install -f ./server",
    ("invocation", "javascript"): "npm ci --prefix ./client && npm ci --prefix ./server",
    ("invocation", "python"): "uv sync --all-packages",
}

# --- README section 5: run commands -----------------------------------------
# `{project}` is the one sanctioned substitution: READMEs document
# `--project <api>-quickstart`, CI passes its ephemeral project name.
_DEV_RUN = "diagrid dev run -f {file} --project {project} --approve"

# Python quickstarts prefix the CLI with `uv run` instead of activating a venv:
# uv puts .venv/bin on PATH, so the bare `uvicorn` command in the dev config
# resolves, and the app inherits it.
_UV_DEV_RUN = "uv run " + _DEV_RUN

RUN = {
    ("workflow", "csharp"): _DEV_RUN.format(file="workflow-quickstart.yaml", project="{project}"),
    ("workflow", "java"): (
        "diagrid dev run --project {project} --id order-workflow --approve -- mvn spring-boot:run"
    ),
    ("workflow", "javascript"): _DEV_RUN.format(file="workflow-quickstart.yaml", project="{project}"),
    ("workflow", "python"): _UV_DEV_RUN.format(file="workflow-quickstart.yaml", project="{project}"),
    ("state", "csharp"): _DEV_RUN.format(file="state-quickstart.yaml", project="{project}"),
    ("state", "java"): _DEV_RUN.format(file="state-quickstart.yaml", project="{project}"),
    ("state", "javascript"): _DEV_RUN.format(file="state-quickstart.yaml", project="{project}"),
    ("state", "python"): _UV_DEV_RUN.format(file="state-quickstart.yaml", project="{project}"),
    ("pubsub", "csharp"): _DEV_RUN.format(file="pubsub-quickstart.yaml", project="{project}"),
    ("pubsub", "java"): _DEV_RUN.format(file="pubsub-quickstart.yaml", project="{project}"),
    ("pubsub", "javascript"): _DEV_RUN.format(file="pubsub-quickstart.yaml", project="{project}"),
    ("pubsub", "python"): _UV_DEV_RUN.format(file="pubsub-quickstart.yaml", project="{project}"),
    ("invocation", "csharp"): _DEV_RUN.format(file="invocation-quickstart.yaml", project="{project}"),
    ("invocation", "java"): _DEV_RUN.format(file="invocation-quickstart.yaml", project="{project}"),
    ("invocation", "javascript"): _DEV_RUN.format(file="invocation-quickstart.yaml", project="{project}"),
    ("invocation", "python"): _UV_DEV_RUN.format(file="invocation-quickstart.yaml", project="{project}"),
}

# --- Apps, ports, and readiness ---------------------------------------------
# HEALTH_PORTS: every port that must answer 200 on `GET /` before asserting.
# Keyed by api only: the apps listen on 5001/5002 regardless of appPort
# (appPort only tells Catalyst to open an inbound connection), so this stays
# uniform across languages even where CONNECTED_APPS below does not.
#
# `GET /` is right *here* because all four canonical implementations really do
# route it: state/python/main.py `@app.get('/')`, state/csharp/Program.cs
# `app.MapGet("/")`, state/javascript/index.js `app.get("/")`, state/java
# Controller.java `@GetMapping(path = "/")`, and the same in the other three APIs.
# get_quickstart pairs each port with "/" for `Wait Until Apps Healthy`; do not
# assume that pairing carries over to a quickstart outside this table — see
# HEALTH_PROBES in variables/agents_langgraph.py.
HEALTH_PORTS = {
    "workflow": (5001,),
    "state": (5001,),
    "pubsub": (5001, 5002),
    "invocation": (5001, 5002),
}

# CONNECTED_APPS: (appID, port) pairs that `diagrid dev run` reports as
# `Connected App ID "<id>" to http://localhost:<port>`. Only apps with a non-zero
# appPort in the dev config produce that line. Keyed by (api, language),
# matching INSTALL and RUN above, because this is NOT uniform per API:
# pubsub's publisher has an appPort in csharp/python but NOT in java/
# javascript (verified against each language's dev config), so java and
# javascript emit only the subscriber's connection line. Do not collapse
# this back to a per-API dict — the divergence is real, not a typo.
CONNECTED_APPS = {
    ("workflow", "csharp"): (),
    ("workflow", "java"): (),
    ("workflow", "javascript"): (),
    ("workflow", "python"): (),
    ("state", "csharp"): (),
    ("state", "java"): (),
    ("state", "javascript"): (),
    ("state", "python"): (),
    ("pubsub", "csharp"): (("publisher", 5001), ("subscriber", 5002)),
    ("pubsub", "java"): (("subscriber", 5002),),
    ("pubsub", "javascript"): (("subscriber", 5002),),
    ("pubsub", "python"): (("publisher", 5001), ("subscriber", 5002)),
    ("invocation", "csharp"): (("server", 5002),),
    ("invocation", "java"): (("server", 5002),),
    ("invocation", "javascript"): (("server", 5002),),
    ("invocation", "python"): (("server", 5002),),
}

# --- README section 6: requests ---------------------------------------------
ORDER_PAYLOAD = {"orderId": 1}
WORKFLOW_PAYLOAD = {"name": "Car", "quantity": 2}

# --- README section 6: expected response bodies -----------------------------
# state 6.1 store, 201 Created
STATE_STORE_BODY = {
    "csharp": {"id": 1, "message": "Order created successfully"},
    "javascript": {"id": 1, "message": "Order created successfully"},
    "python": {"id": 1, "message": "Order created successfully"},
    # java names the id field `orderId`
    "java": {"orderId": 1, "message": "Order created successfully"},
}

# state 6.2 retrieve, 200 OK
STATE_RETRIEVE_BODY = {
    "csharp": {"data": {"orderId": 1}},
    "javascript": {"data": {"orderId": 1}},
    # java carries an extra empty message
    "java": {"data": {"orderId": 1}, "message": ""},
    # python stores the string form of its model
    "python": {"data": "orderId=1"},
}

# pubsub 6.1 publish, 201 Created
PUBSUB_PUBLISH_BODY = {
    "csharp": {"id": 1, "message": "Message published successfully", "topic": "orders"},
    "javascript": {"id": 1, "message": "Message published successfully", "topic": "orders"},
    "python": {"id": 1, "message": "Message published successfully", "topic": "orders"},
    # java returns the id as a string
    "java": {"id": "1", "message": "Message published successfully", "topic": "orders"},
}

# invocation 6.1, 200 OK — identical in all four languages
INVOCATION_BODY = {
    "message": "Invocation successful",
    "orderId": 1,
    "targetApp": "server",
}

# workflow 6.1 start — the key holding the instance id
WORKFLOW_INSTANCE_KEY = {
    "csharp": "instanceId",
    "java": "instanceId",
    "python": "instanceId",
    # javascript returns snake_case
    "javascript": "instance_id",
}

# --- Log markers ------------------------------------------------------------
# Substrings expected in the captured `diagrid dev run` output. Shared
# constants are language-invariant; per-language dicts hold genuine divergence.
# Every truncation point below is deliberate. Where the reason is recoverable
# it is recorded next to the marker (see INVOCATION_CLIENT_MARKER's csharp
# entry for a concrete example: truncated before a status value because that
# language renders an enum where the others render a number). Where no such
# reason is recorded, the truncation is still deliberate — it just has no
# documented rationale beyond "this is the substring that matches."

STATE_SAVE_MARKER = "Save state item successful."
STATE_RETRIEVE_MARKER = "Get state item successful. Order retrieved"

PUBSUB_PUBLISH_MARKER = "Order published: 1"
PUBSUB_RECEIVE_MARKER = {
    "csharp": "Order received: 1",
    "java": "Order received: 1",
    "python": "Order received: 1",
    "javascript": 'Order received: {"orderId":1}',
}

INVOCATION_SERVER_MARKER = "Invocation received with data"
INVOCATION_CLIENT_MARKER = {
    "python": "Invocation successful with status code: 200",
    "javascript": "Invocation successful with status code: 200",
    # csharp logs response.StatusCode, an HttpStatusCode enum that renders as
    # "OK" rather than the numeric code python/javascript log, so this marker
    # is truncated before the status value to match regardless of rendering.
    "csharp": "Invocation successful with status code",
    # different sentence entirely
    "java": "Invoke Successful. Response received: 1",
}

# Workflow notification messages, identical in all four languages. `{id}` is
# the instance id returned by the start call.
WORKFLOW_START_MARKER = "Received order {id} for 2 Car"
WORKFLOW_DONE_MARKER = "Order {id} has completed!"

# --- README section 7: the crash-recovery demo -------------------------------
# csharp, java and python only. javascript has no crash demo, so there is nothing
# for a javascript case to drive.
CRASH_LANGUAGES = ("csharp", "java", "python")

# The instance id is per-language on purpose. All four language tests share one
# ephemeral Catalyst project, so a single shared id would leave the second language
# attaching to the first language's completed run and never crashing anything.
CRASH_INSTANCE_ID = "trip-42-{language}"
CRASH_REFERENCE = "ABC123"

# The delay driven into the app so the suite does not pay 30s per language. Long
# enough that firing the request, seeing the start marker and firing the kill all
# fit inside the window.
CRASH_DELAY_SECONDS = "20"

# Log markers, identical in all three languages: the implementations log the same
# sentences deliberately, so this needs no per-language dict. `{id}` is the
# caller-chosen instance id.
#
# CRASH_RECEIVED_MARKER is the one that matters most, and it is asserted ABSENT
# from the restarted app's log. It belongs to the fast activity, which completed and
# was recorded before the crash, so a replay that re-ran it would mean the crash
# landed before the first persisted completion and the demo proved nothing.
CRASH_RECEIVED_MARKER = "Reservation {id} received for ABC123"
CRASH_COMMITTING_MARKER = "Committing reservation ABC123 over ~"
CRASH_COMMITTED_MARKER = "Committed reservation ABC123. Confirmation code: BK-E0BEBD22"
CRASH_DONE_MARKER = "Reservation {id} has completed!"

# The documented 200 body's `result` field. Derived from the reference alone, so it is
# the same before and after the crash. That sameness is the point of the demo.
CRASH_CONFIRMATION = "Reservation ABC123 confirmed. Confirmation code: BK-E0BEBD22"


def get_quickstart(api, language):
    """Return a flat dict of everything a suite needs for one (api, language).

    Robot calls this as a keyword: `${qs}=  Get Quickstart  state  python`.
    """
    return {
        "api": api,
        "language": language,
        "dir": quickstart_dir(api, language),
        "install": INSTALL[(api, language)],
        "run": RUN[(api, language)],
        # (port, path) pairs, because `Wait Until Apps Healthy` probes a path the
        # app really serves rather than assuming `/`. Every canonical
        # implementation routes `/` (checked in all sixteen; see the HEALTH_PORTS
        # comment above), so the path is "/" for all of them and this preserves
        # exactly the behaviour the keyword had when it hardcoded `/`.
        "health_probes": [[port, "/"] for port in HEALTH_PORTS[api]],
        "connected_apps": [list(pair) for pair in CONNECTED_APPS[(api, language)]],
    }

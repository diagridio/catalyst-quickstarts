# Quickstart End-to-End Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A daily GitHub Actions run that executes all 16 quickstarts (workflow, state, pubsub, invocation × csharp, java, javascript, python) against real ephemeral Diagrid Catalyst projects, asserting the HTTP responses and application log output documented in each quickstart's README.

**Architecture:** A Robot Framework harness at `tools/qs-tester/` holds shared keywords and a per-(API, language) data table. Four suites live next to the quickstarts (`state/tests/quickstart.robot` and siblings), each with four language-tagged tests sharing one body. Each test builds the quickstart with its documented install command, launches its documented `diagrid dev run` command as a background process, waits for readiness, asserts the documented HTTP responses and log markers, then kills the whole process tree. CI runs one matrix leg per language, two legs at a time, each leg creating and deleting its own Catalyst project.

**Tech Stack:** Robot Framework 7.x, `robotframework-requests`, Python 3.12+, `uv` for the harness's own dependencies, the `diagrid` CLI, GitHub Actions.

**Design spec:** `docs/superpowers/specs/2026-07-28-quickstart-e2e-tests-design.md`. Read it before starting — this plan implements it and does not restate its reasoning.

## Global Constraints

- **The READMEs are the source of truth.** Install commands, run commands, endpoints, payloads and expected response bodies come from `<api>/<language>/README.md` sections 4–7, copied verbatim. Never invent an equivalent command.
- **Order ID is `1`** in every request payload (`{"orderId":1}`). `test.rest` uses `4` for state; ignore it.
- **The suites assert only the documented flow.** Do not test `DELETE /order/{id}` or `POST /workflow/terminate/{id}` — no README documents them.
- **Robot Framework pinned `>=7,<8`.**
- **Python `>=3.12`** for the harness (matches every quickstart's `requires-python`).
- **`DIAGRID_API_KEY` arrives as an environment variable.** The `diagrid` CLI has no environment fallback — always pass `--api-key "$DIAGRID_API_KEY"` explicitly, or the CLI attempts an interactive browser login and hangs.
- **Never more than two concurrent Catalyst projects.** `max-parallel: 2` on the CI matrix.
- **Ephemeral project names:** `qs-ci-<lang>-<github_run_id>`.
- **Catalyst managed component names:** `kvstore` (from `--deploy-managed-kv`) and `pubsub`. A second KV store named `statestore` must also be created, because `state/java` expects `kvstore` while the other three expect `statestore`.
- **All commands in this plan run from the repository root** unless a step says otherwise. `robot`/`rebot`/`uv` commands run from `tools/qs-tester/`, so suite paths are written relative to it (`../../state/tests/quickstart.robot`).

---

## File Structure

| File | Responsibility |
|---|---|
| `tools/qs-tester/pyproject.toml` | Harness dependencies and pytest config |
| `tools/qs-tester/README.md` | How to run a leg locally |
| `tools/qs-tester/variables/quickstarts.py` | The whole per-(API, language) data table: install command, run command, ports, appIDs, payloads, expected bodies, log markers. No logic. |
| `tools/qs-tester/resources/process.resource` | Background process lifecycle and the PID-tree teardown. Knows nothing about Catalyst or HTTP. |
| `tools/qs-tester/resources/catalyst.resource` | `diagrid dev run` launch and stop, readiness markers. Depends on `process.resource`. |
| `tools/qs-tester/resources/quickstart.resource` | Build, HTTP health polling, HTTP request + response-body assertions, log-marker assertions. |
| `tools/qs-tester/docsync/check_readme_sync.py` | Assert each README's commands, payloads and expected bodies match `quickstarts.py` |
| `tools/qs-tester/docsync/tests/test_check_readme_sync.py` | Unit tests for the checker's parsing and comparison |
| `tools/qs-tester/ci/setup-project.sh` | Login, create ephemeral project, create `statestore` KV, export `PROJECT` |
| `tools/qs-tester/ci/teardown-project.sh` | Delete the ephemeral project |
| `tools/qs-tester/ci/reap-orphans.sh` | Delete `qs-ci-*` projects older than 6h |
| `state/tests/quickstart.robot` | 4 tests: store and retrieve, tagged per language |
| `invocation/tests/quickstart.robot` | 4 tests: client invokes server |
| `pubsub/tests/quickstart.robot` | 4 tests: publish and receive |
| `workflow/tests/quickstart.robot` | 4 tests: start, run to completion, get status |
| `.github/workflows/e2e-quickstarts.yml` | lint, reap, e2e matrix, report |

Three resource files rather than two (the spec sketched two): process lifecycle is genuinely independent of Catalyst, it is the piece most likely to need debugging in isolation, and separating it keeps `catalyst.resource` readable. This is the one structural deviation from the spec.

---

## Task 1: Harness skeleton and the data table

**Files:**
- Create: `tools/qs-tester/pyproject.toml`
- Create: `tools/qs-tester/variables/quickstarts.py`
- Create: `tools/qs-tester/.gitignore`

**Interfaces:**
- Consumes: nothing.
- Produces: `tools/qs-tester/variables/quickstarts.py` exposing module-level dicts keyed by `(api, language)` tuples, plus a Robot-callable `get_quickstart(api, language)` returning a flat dict. Every later task reads its data from here.

- [ ] **Step 1: Create the harness project file**

Create `tools/qs-tester/pyproject.toml`:

```toml
[project]
name = "qs-tester"
version = "0.1.0"
description = "End-to-end tests for the Catalyst quickstarts (Robot Framework)"
requires-python = ">=3.12"
dependencies = [
    "robotframework>=7,<8",
    "robotframework-requests>=0.9",
]

[dependency-groups]
dev = ["pytest>=8"]

[tool.pytest.ini_options]
pythonpath = ["docsync", "variables"]
testpaths = ["docsync/tests"]
```

- [ ] **Step 2: Create the harness gitignore**

Create `tools/qs-tester/.gitignore`:

```gitignore
.venv/
results/
output.xml
log.html
report.html
*.log
__pycache__/
.pytest_cache/
```

- [ ] **Step 3: Write the data table**

Create `tools/qs-tester/variables/quickstarts.py`. Every string is copied from the corresponding README — do not paraphrase.

```python
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
# The three python entries with `uv venv` run through a shell that then stays
# activated for the run command; see ACTIVATE_VENV below.
INSTALL = {
    ("workflow", "csharp"): "dotnet build",
    ("workflow", "java"): "mvn clean install",
    ("workflow", "javascript"): "npm install",
    ("workflow", "python"): "uv sync",
    ("state", "csharp"): "dotnet restore",
    ("state", "java"): "mvn clean install",
    ("state", "javascript"): "npm install",
    ("state", "python"): "uv venv && . .venv/bin/activate && uv sync",
    ("pubsub", "csharp"): "dotnet restore ./publisher && dotnet restore ./subscriber",
    ("pubsub", "java"): "mvn clean install -f ./publisher && mvn clean install -f ./subscriber",
    ("pubsub", "javascript"): "npm install --prefix ./publisher && npm install --prefix ./subscriber",
    ("pubsub", "python"): (
        "uv venv && . .venv/bin/activate && "
        "uv sync --active --directory publisher && uv sync --active --directory subscriber"
    ),
    ("invocation", "csharp"): "dotnet restore ./client && dotnet restore ./server",
    ("invocation", "java"): "mvn clean install -f ./client && mvn clean install -f ./server",
    ("invocation", "javascript"): "npm install --prefix ./client && npm install --prefix ./server",
    ("invocation", "python"): (
        "uv venv && . .venv/bin/activate && "
        "uv sync --active --directory client && uv sync --active --directory server"
    ),
}

# True where README section 4 documents `uv venv` + activate, meaning the run
# command must execute inside that activated virtual environment.
ACTIVATE_VENV = {
    ("state", "python"),
    ("pubsub", "python"),
    ("invocation", "python"),
}

# --- README section 5: run commands -----------------------------------------
# `{project}` is the one sanctioned substitution: READMEs document
# `--project <api>-quickstart`, CI passes its ephemeral project name.
_DEV_RUN = "diagrid dev run -f {file} --project {project} --approve"

RUN = {
    ("workflow", "csharp"): _DEV_RUN.format(file="workflow-quickstart.yaml", project="{project}"),
    ("workflow", "java"): (
        "diagrid dev run --project {project} --app-id order-workflow --approve -- mvn spring-boot:run"
    ),
    ("workflow", "javascript"): _DEV_RUN.format(file="workflow-quickstart.yaml", project="{project}"),
    ("workflow", "python"): (
        "uv run diagrid dev run -f workflow-quickstart.yaml --project {project} --approve"
    ),
    ("state", "csharp"): _DEV_RUN.format(file="state-quickstart.yaml", project="{project}"),
    ("state", "java"): _DEV_RUN.format(file="state-quickstart.yaml", project="{project}"),
    ("state", "javascript"): _DEV_RUN.format(file="state-quickstart.yaml", project="{project}"),
    ("state", "python"): _DEV_RUN.format(file="state-quickstart.yaml", project="{project}"),
    ("pubsub", "csharp"): _DEV_RUN.format(file="pubsub-quickstart.yaml", project="{project}"),
    ("pubsub", "java"): _DEV_RUN.format(file="pubsub-quickstart.yaml", project="{project}"),
    ("pubsub", "javascript"): _DEV_RUN.format(file="pubsub-quickstart.yaml", project="{project}"),
    ("pubsub", "python"): _DEV_RUN.format(file="pubsub-quickstart.yaml", project="{project}"),
    ("invocation", "csharp"): _DEV_RUN.format(file="invocation-quickstart.yaml", project="{project}"),
    ("invocation", "java"): _DEV_RUN.format(file="invocation-quickstart.yaml", project="{project}"),
    ("invocation", "javascript"): _DEV_RUN.format(file="invocation-quickstart.yaml", project="{project}"),
    ("invocation", "python"): _DEV_RUN.format(file="invocation-quickstart.yaml", project="{project}"),
}

# --- Apps, ports, and readiness ---------------------------------------------
# HEALTH_PORTS: every port that must answer 200 on `GET /` before asserting.
# CONNECTED_APPS: (appID, port) pairs that `diagrid dev run` reports as
# `Connected App ID "<id>" to localhost:<port>`. Only apps with a non-zero
# appPort in the dev config produce that line, so workflow and state have none
# and invocation has only `server`.
HEALTH_PORTS = {
    "workflow": (5001,),
    "state": (5001,),
    "pubsub": (5001, 5002),
    "invocation": (5001, 5002),
}

CONNECTED_APPS = {
    "workflow": (),
    "state": (),
    "pubsub": (("publisher", 5001), ("subscriber", 5002)),
    "invocation": (("server", 5002),),
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
# Truncation points are deliberate: see the design spec's assertion matrix.

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
    # no colon
    "csharp": "Invocation successful with status code 200",
    # different sentence entirely
    "java": "Invoke Successful. Response received: 1",
}

# Workflow notification messages, identical in all four languages. `{id}` is
# the instance id returned by the start call.
WORKFLOW_START_MARKER = "Received order {id} for 2 Car"
WORKFLOW_DONE_MARKER = "Order {id} has completed!"


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
        "activate_venv": (api, language) in ACTIVATE_VENV,
        "health_ports": list(HEALTH_PORTS[api]),
        "connected_apps": [list(pair) for pair in CONNECTED_APPS[api]],
    }
```

- [ ] **Step 4: Verify the table imports and is complete**

Run:

```bash
cd tools/qs-tester && uv sync && uv run python -c "
import os
import quickstarts as q
missing = [(a, l) for a in q.APIS for l in q.LANGUAGES
           if (a, l) not in q.INSTALL or (a, l) not in q.RUN]
assert not missing, f'missing entries: {missing}'
for a in q.APIS:
    for l in q.LANGUAGES:
        d = q.get_quickstart(a, l)
        # Every run command must carry the placeholder the harness substitutes.
        assert '{project}' in d['run'], (a, l, d['run'])
        # Paths must be absolute and real: Robot runs from tools/qs-tester, so a
        # relative path would silently point at a directory that does not exist.
        assert os.path.isabs(d['dir']), (a, l, d['dir'])
        assert os.path.isdir(d['dir']), f'not a directory: {d[\"dir\"]}'
        # The README the data was transcribed from must exist.
        assert os.path.isfile(os.path.join(d['dir'], 'README.md')), d['dir']
print('16/16 entries present, all dirs absolute and existing, all READMEs found')
"
```

Expected: `16/16 entries present, all dirs absolute and existing, all READMEs found`

Note `uv run python -c` resolves `quickstarts` because `pythonpath` includes `variables`. If the import fails, run from `tools/qs-tester` with `PYTHONPATH=variables`.

- [ ] **Step 5: Commit**

```bash
git add tools/qs-tester/pyproject.toml tools/qs-tester/uv.lock \
        tools/qs-tester/.gitignore tools/qs-tester/variables/quickstarts.py
git commit -m "test: add quickstart e2e harness skeleton and data table"
```

---

## Task 2: Process lifecycle keywords

**Files:**
- Create: `tools/qs-tester/resources/process.resource`

**Interfaces:**
- Consumes: nothing.
- Produces: keywords `Start Background Process  ${command}  ${logfile}  ${alias}  ${cwd}=${EMPTY}` (returns a process handle), `Wait Until Log Contains  ${logfile}  ${text}  ${timeout}=60s`, `Log Should Contain  ${logfile}  ${text}`, `Stop Process Tree  ${alias}  ${timeout}=15s` (returns the process result or `None`), and `Run And Expect RC Zero  ${command}  ${cwd}=${EMPTY}  ${timeout}=600s` (returns the result object).

This task has no unit test of its own — Robot resource files are exercised by the suites that import them. Task 3 is where these keywords first run for real. Step 4 below is a smoke check that proves they work before any suite depends on them.

- [ ] **Step 1: Write the resource file**

Create `tools/qs-tester/resources/process.resource`:

```robotframework
*** Comments ***
Process lifecycle keywords. Deliberately knows nothing about Catalyst, HTTP, or
the quickstarts — it is the piece most likely to need debugging in isolation.

The teardown logic is ported from dapr-university-instruqt's
tools/track-tester/resources/dapr.resource. Do not simplify it; the comments
explain why each layer exists.

*** Settings ***
Library    Process
Library    OperatingSystem

*** Keywords ***
Start Background Process
    [Documentation]    Launch ${command} without blocking, merging stdout and stderr
    ...    into ${logfile}. ${alias} lets later keywords refer to the process.
    [Arguments]    ${command}    ${logfile}    ${alias}    ${cwd}=${EMPTY}
    # Truncate first: a log left over from a previous run could otherwise satisfy
    # an assertion before the new process has produced any output at all.
    Create File    ${logfile}    ${EMPTY}
    ${handle}=    Start Process    ${command}    shell=True    alias=${alias}
    ...    cwd=${cwd}    stdout=${logfile}    stderr=STDOUT
    RETURN    ${handle}

Wait Until Log Contains
    [Documentation]    Poll ${logfile} every 2s until it contains ${text}.
    ...    App logging is asynchronous with respect to the HTTP response, so
    ...    every log assertion has to be a wait rather than a single read.
    [Arguments]    ${logfile}    ${text}    ${timeout}=60s
    Wait Until Keyword Succeeds    ${timeout}    2s
    ...    Log Should Contain    ${logfile}    ${text}

Log Should Contain
    [Arguments]    ${logfile}    ${text}
    ${content}=    Get File    ${logfile}
    Should Contain    ${content}    ${text}
    ...    msg=Log ${logfile} does not contain "${text}"

Run And Expect RC Zero
    [Documentation]    Run ${command} to completion and fail unless it exits 0.
    ...    Used for build commands, which are slow: default timeout 600s.
    [Arguments]    ${command}    ${cwd}=${EMPTY}    ${timeout}=600s
    # Omit stdout= so Robot captures to a managed temp file it cleans up.
    # Passing stdout=PIPE would write a stray file literally named "PIPE".
    ${result}=    Run Process    ${command}    shell=True    cwd=${cwd}
    ...    stderr=STDOUT    timeout=${timeout}
    Should Be Equal As Integers    ${result.rc}    0
    ...    msg=Command failed (rc=${result.rc}): ${command}\n${result.stdout}
    RETURN    ${result}

Stop Process Tree
    [Documentation]    Send SIGINT (the README's CTRL+C) to the process group, then
    ...    escalate to a PID-tree SIGKILL if anything survives.
    [Arguments]    ${alias}    ${timeout}=15s
    # group=True so the CLI *and* the app it launched both receive SIGINT, like
    # Ctrl+C in a terminal. Signalling the single PID leaves children unsignalled
    # on Linux and the CLI never exits.
    Send Signal To Process    SIGINT    ${alias}    group=True
    # Do not rely on Robot's on_timeout=kill: it force-kills only the tracked
    # top-level PID. The CLI, its sidecar and the app can survive as orphans,
    # still holding ports 5001/5002 and corrupting the next suite in the leg.
    ${result}=    Wait For Process    ${alias}    timeout=${timeout}    on_timeout=continue
    IF    $result is None
        # A group signal is not enough here. `diagrid dev run` and the app each
        # detach into new process groups, and for the three python quickstarts we
        # launch through a `bash -c '. .venv/bin/activate && ...'` wrapper, so the
        # descendants sit in groups the wrapper's own group can never reach. The
        # only reliable fallback is to walk the real OS parent/child PID tree from
        # the tracked PID, to any depth, and SIGKILL every descendant directly.
        ${pid}=    Get Process Id    ${alias}
        Run Process    bash    -c
        ...    kill_tree() { for c in $(pgrep -P "$1" 2>/dev/null); do kill_tree "$c"; done; kill -9 "$1" 2>/dev/null; }; kill_tree ${pid}
        ${result}=    Wait For Process    ${alias}    timeout=10s    on_timeout=kill
    END
    RETURN    ${result}
```

- [ ] **Step 2: Write a throwaway smoke suite**

Create `tools/qs-tester/resources/tests/smoke.robot`:

```robotframework
*** Settings ***
Resource    ../process.resource
Library     OperatingSystem

*** Test Cases ***
Background Process Writes To Its Log And Can Be Stopped
    Start Background Process    bash -c 'for i in 1 2 3 4 5 6 7 8 9; do echo tick $i; sleep 1; done'
    ...    ${TEMPDIR}/smoke.log    ticker
    Wait Until Log Contains    ${TEMPDIR}/smoke.log    tick 2    timeout=20s
    ${result}=    Stop Process Tree    ticker
    Should Not Be Equal    ${result}    ${None}

Stale Log Content Is Truncated On Start
    Create File    ${TEMPDIR}/stale.log    tick 99
    Start Background Process    bash -c 'sleep 5'    ${TEMPDIR}/stale.log    sleeper
    Log Should Not Contain Stale    ${TEMPDIR}/stale.log    tick 99
    Stop Process Tree    sleeper

Run And Expect RC Zero Fails On Non-Zero Exit
    ${status}=    Run Keyword And Return Status
    ...    Run And Expect RC Zero    bash -c 'exit 3'
    Should Be Equal    ${status}    ${False}

Nested Children Are Killed When SIGINT Is Ignored
    # A parent that traps SIGINT, with a grandchild. Only the PID-tree fallback
    # can clean this up — exactly the diagrid dev run situation.
    Start Background Process
    ...    bash -c 'trap "" INT; bash -c "sleep 300" & echo started; wait'
    ...    ${TEMPDIR}/nested.log    nested
    Wait Until Log Contains    ${TEMPDIR}/nested.log    started    timeout=20s
    ${pid}=    Get Process Id    nested
    ${kids}=    Run Process    bash    -c    pgrep -P ${pid} | head -1
    Stop Process Tree    nested    timeout=5s
    # The grandchild must be gone, not orphaned.
    ${check}=    Run Process    bash    -c    kill -0 ${kids.stdout} 2>/dev/null && echo alive || echo gone
    Should Contain    ${check.stdout}    gone

*** Keywords ***
Log Should Not Contain Stale
    [Arguments]    ${logfile}    ${text}
    ${content}=    Get File    ${logfile}
    Should Not Contain    ${content}    ${text}
```

- [ ] **Step 3: Run the smoke suite to verify it fails before the resource works**

Deliberately break the resource first, to prove the tests are not vacuous. Temporarily change `Create File    ${logfile}    ${EMPTY}` to `Log    skipped` in `process.resource`, then run:

```bash
cd tools/qs-tester && uv run robot --outputdir results/smoke resources/tests/smoke.robot
```

Expected: `Stale Log Content Is Truncated On Start` FAILS. Restore the line afterwards.

- [ ] **Step 4: Run the smoke suite for real**

```bash
cd tools/qs-tester && uv run robot --outputdir results/smoke resources/tests/smoke.robot
```

Expected: 4 tests, all PASS. In particular `Nested Children Are Killed When SIGINT Is Ignored` proves the PID-tree fallback works, which is the whole reason this file exists.

- [ ] **Step 5: Commit**

```bash
git add tools/qs-tester/resources/process.resource tools/qs-tester/resources/tests/smoke.robot
git commit -m "test: add process lifecycle keywords with PID-tree teardown"
```

---

## Task 3: Catalyst and quickstart keywords

**Files:**
- Create: `tools/qs-tester/resources/catalyst.resource`
- Create: `tools/qs-tester/resources/quickstart.resource`

**Interfaces:**
- Consumes: `process.resource` keywords from Task 2; `get_quickstart` from Task 1.
- Produces:
  - `catalyst.resource`: `Start Quickstart  ${qs}  ${project}  ${logfile}` (launches the documented run command under alias `apps`), `Wait Until Apps Connected  ${qs}  ${logfile}`, `Stop Quickstart  ${project}`.
  - `quickstart.resource`: `Build Quickstart  ${qs}`, `Wait Until Apps Healthy  ${qs}`, `POST And Expect  ${port}  ${path}  ${payload}  ${status}  ${expected_body}` (returns the parsed response body), `GET And Expect  ${port}  ${path}  ${status}  ${expected_body}=${NONE}` (returns the parsed body), and `Suite Log File  ${api}` returning the per-suite log path.

- [ ] **Step 1: Write the Catalyst resource**

Create `tools/qs-tester/resources/catalyst.resource`:

```robotframework
*** Comments ***
Launching and stopping a quickstart through the `diagrid dev run` command its
README documents, plus the readiness marker that command emits.

*** Settings ***
Library     Collections
Library     String
Resource    process.resource

*** Keywords ***
Start Quickstart
    [Documentation]    Launch the quickstart's documented run command in the
    ...    background under alias `apps`, substituting the ephemeral project name.
    [Arguments]    ${qs}    ${project}    ${logfile}
    ${command}=    Resolve Project In Command    ${qs}[run]    ${project}
    # The three python quickstarts whose README documents `uv venv` + activate run
    # a bare `diagrid dev run`, so the command must execute inside that activated
    # virtual environment. A shell wrapper is the only way to express that, and it
    # is why Stop Process Tree needs its PID-tree fallback.
    IF    ${qs}[activate_venv]
        ${command}=    Set Variable    bash -c '. .venv/bin/activate && ${command}'
    END
    Log    Starting: ${command}    console=True
    ${handle}=    Start Background Process    ${command}    ${logfile}    apps
    ...    cwd=${qs}[dir]
    RETURN    ${handle}

Resolve Project In Command
    [Documentation]    Substitute the ephemeral project name for the {project}
    ...    placeholder. Deliberately NOT named `Format String` — the String library
    ...    already has a keyword by that name and the collision would be silent.
    [Arguments]    ${template}    ${project}
    ${result}=    Replace String    ${template}    {project}    ${project}
    RETURN    ${result}

Wait Until Apps Connected
    [Documentation]    Wait for `Connected App ID "<id>" to localhost:<port>` for each
    ...    app that has a local app connection. Apps with appPort 0 or no appPort
    ...    (workflow, state, invocation's client) never emit this line, so
    ...    ${qs}[connected_apps] is empty for those and this keyword does nothing.
    [Arguments]    ${qs}    ${logfile}
    FOR    ${app}    IN    @{qs}[connected_apps]
        ${app_id}=    Set Variable    ${app}[0]
        ${port}=    Set Variable    ${app}[1]
        Wait Until Log Contains    ${logfile}
        ...    Connected App ID "${app_id}" to localhost:${port}    timeout=180s
    END

Stop Quickstart
    [Documentation]    CTRL+C equivalent, then release the local app connections.
    ...    Safe to call when the process is already gone.
    [Arguments]    ${project}
    Run Keyword And Ignore Error    Stop Process Tree    apps
    Run Process    diagrid dev stop --project ${project}    shell=True
    ...    stderr=STDOUT    timeout=120s
```

Note `Replace String` comes from `String`, which is a Robot standard library. Add `Library    String` to the `*** Settings ***` block above alongside `Collections`.

- [ ] **Step 2: Write the quickstart resource**

Create `tools/qs-tester/resources/quickstart.resource`:

```robotframework
*** Comments ***
Building a quickstart, waiting for its apps to serve, and asserting documented
HTTP responses. Response bodies are compared as parsed JSON, not as strings, so
key order and whitespace cannot cause a false failure.

*** Settings ***
Library     RequestsLibrary
Library     Collections
Library     OperatingSystem
Resource    process.resource

*** Keywords ***
Build Quickstart
    [Documentation]    Run the install command from the quickstart's README section 4.
    [Arguments]    ${qs}
    Log    Building ${qs}[dir]: ${qs}[install]    console=True
    Run And Expect RC Zero    ${qs}[install]    cwd=${qs}[dir]    timeout=900s

Suite Log File
    [Documentation]    One captured `diagrid dev run` stream per suite. Lives under
    ...    the Robot output dir so CI uploads it with the report.
    [Arguments]    ${api}
    RETURN    ${OUTPUT DIR}/${api}-dev-run.log

Wait Until Apps Healthy
    [Documentation]    Poll `GET /` on every app port until it answers 200. This is
    ...    the only readiness gate for workflow and state, which emit no connection
    ...    marker, so the timeout is generous enough for a JVM or .NET cold start.
    [Arguments]    ${qs}
    FOR    ${port}    IN    @{qs}[health_ports]
        Wait Until Keyword Succeeds    180s    3s    Health Check Returns 200    ${port}
    END

Health Check Returns 200
    [Arguments]    ${port}
    GET    http://localhost:${port}/    expected_status=200    timeout=10

POST And Expect
    [Documentation]    POST ${payload} as JSON and assert the status code and, if
    ...    given, the exact parsed response body.
    [Arguments]    ${port}    ${path}    ${payload}    ${status}    ${expected_body}=${NONE}
    ${response}=    POST    http://localhost:${port}${path}    json=${payload}
    ...    expected_status=${status}    timeout=30
    ${body}=    Set Variable    ${response.json()}
    IF    $expected_body is not None
        Should Be Equal    ${body}    ${expected_body}
        ...    msg=POST ${path} body mismatch.\nExpected: ${expected_body}\nActual:   ${body}
    END
    RETURN    ${body}

GET And Expect
    [Arguments]    ${port}    ${path}    ${status}    ${expected_body}=${NONE}
    ${response}=    GET    http://localhost:${port}${path}
    ...    expected_status=${status}    timeout=30
    ${body}=    Set Variable    ${response.json()}
    IF    $expected_body is not None
        Should Be Equal    ${body}    ${expected_body}
        ...    msg=GET ${path} body mismatch.\nExpected: ${expected_body}\nActual:   ${body}
    END
    RETURN    ${body}
```

- [ ] **Step 3: Verify both resources parse and resolve**

```bash
cd tools/qs-tester && uv run python - <<'PY'
import subprocess, textwrap, pathlib
probe = pathlib.Path("results/probe.robot")
probe.parent.mkdir(parents=True, exist_ok=True)
probe.write_text(textwrap.dedent('''
    *** Settings ***
    Resource    ../resources/catalyst.resource
    Resource    ../resources/quickstart.resource
    Variables   ../variables/quickstarts.py
    Library     ../variables/quickstarts.py

    *** Test Cases ***
    Keywords Resolve
        ${qs}=    Get Quickstart    state    python
        Log    ${qs}[install]
        Log    ${qs}[run]
        Log    ${STATE_STORE_BODY}[python]
'''))
print(subprocess.run(["uv", "run", "robot", "--dryrun",
                      "--outputdir", "results/probe", str(probe)]).returncode)
PY
```

Expected: exit code `0`. A non-zero code means a keyword name or import path is wrong — fix before continuing, because every suite depends on these two files.

- [ ] **Step 4: Commit**

```bash
git add tools/qs-tester/resources/catalyst.resource tools/qs-tester/resources/quickstart.resource
git commit -m "test: add Catalyst launch and quickstart assertion keywords"
```

---

## Task 4: CI scripts for the Catalyst project lifecycle

**Files:**
- Create: `tools/qs-tester/ci/setup-project.sh`
- Create: `tools/qs-tester/ci/teardown-project.sh`
- Create: `tools/qs-tester/ci/reap-orphans.sh`

**Interfaces:**
- Consumes: `DIAGRID_API_KEY` from the environment.
- Produces: `setup-project.sh` exports `PROJECT=qs-ci-<lang>-<run_id>`, writing it to `$GITHUB_ENV` when that variable is set and echoing it either way. `teardown-project.sh` takes the project name as `$1` or reads `$PROJECT`. `reap-orphans.sh` takes no arguments.

- [ ] **Step 1: Write the setup script**

Create `tools/qs-tester/ci/setup-project.sh`:

```bash
#!/usr/bin/env bash
# Create the ephemeral Catalyst project for one matrix leg.
#
# Reads:  DIAGRID_API_KEY (required), LANG_ID (required), GITHUB_RUN_ID (optional)
# Writes: PROJECT to $GITHUB_ENV when running under Actions; always echoes it.
set -euo pipefail

if [ -z "${DIAGRID_API_KEY:-}" ]; then
  echo "::error::DIAGRID_API_KEY is not set. The diagrid CLI has no environment" >&2
  echo "fallback for it, so without this variable the login would block on an" >&2
  echo "interactive browser prompt and the job would hang." >&2
  exit 1
fi

if [ -z "${LANG_ID:-}" ]; then
  echo "::error::LANG_ID is not set (expected one of csharp java javascript python)" >&2
  exit 1
fi

RUN_ID="${GITHUB_RUN_ID:-local$(date +%s)}"
PROJECT="qs-ci-${LANG_ID}-${RUN_ID}"

# --api-key is mandatory: `diagrid login` does not read DIAGRID_API_KEY itself.
diagrid login --api-key "$DIAGRID_API_KEY"

# --wait blocks until the managed services are ready; --use makes it the default
# project so ad-hoc CLI calls in later steps do not need --project.
diagrid project create "$PROJECT" \
  --deploy-managed-kv \
  --deploy-managed-pubsub \
  --enable-managed-workflow \
  --wait --use

# --deploy-managed-kv provisions a store named `kvstore`, which state/java expects.
# The other three state quickstarts default to `statestore`, so provision that too.
# Both are real stores, so no STATESTORE_NAME override is needed anywhere and each
# language exercises its own published default.
diagrid kv create statestore --project "$PROJECT" --wait

echo "PROJECT=$PROJECT"
if [ -n "${GITHUB_ENV:-}" ]; then
  echo "PROJECT=$PROJECT" >> "$GITHUB_ENV"
fi
```

- [ ] **Step 2: Write the teardown script**

Create `tools/qs-tester/ci/teardown-project.sh`:

```bash
#!/usr/bin/env bash
# Delete the ephemeral project. Runs under `if: always()`, so it must not fail
# the job when setup never got far enough to create anything.
set -uo pipefail

PROJECT="${1:-${PROJECT:-}}"

if [ -z "$PROJECT" ]; then
  echo "No project name given and PROJECT is unset; nothing to delete."
  exit 0
fi

if [ -z "${DIAGRID_API_KEY:-}" ]; then
  echo "DIAGRID_API_KEY is unset; cannot authenticate to delete $PROJECT." >&2
  exit 0
fi

diagrid login --api-key "$DIAGRID_API_KEY" || exit 0

echo "Deleting project $PROJECT"
# Deliberately not `set -e`: a delete failure should be visible but must not mask
# the real test failure that is already being reported.
if diagrid project delete "$PROJECT" --yes; then
  echo "Deleted $PROJECT"
else
  echo "::warning::Failed to delete $PROJECT — reap-orphans.sh will collect it."
fi
```

- [ ] **Step 3: Confirm the delete flag name before relying on it**

`diagrid project delete` may spell its non-interactive flag `--yes`, `-y`, or something else; a wrong flag makes teardown hang waiting for confirmation.

Run:

```bash
diagrid project delete --help
```

Expected: a flags list. Find the non-interactive confirmation flag and correct `teardown-project.sh` and `reap-orphans.sh` if it is not `--yes`. Do not skip this step — an interactive prompt in `if: always()` teardown burns the job's remaining time and leaks the project anyway.

- [ ] **Step 4: Write the orphan reaper**

Create `tools/qs-tester/ci/reap-orphans.sh`:

```bash
#!/usr/bin/env bash
# Delete qs-ci-* projects older than 6 hours. Cancelled jobs never run their
# teardown, so without this they accumulate and eventually block new runs
# against the two-concurrent-project limit.
set -uo pipefail

if [ -z "${DIAGRID_API_KEY:-}" ]; then
  echo "::error::DIAGRID_API_KEY is not set" >&2
  exit 1
fi

diagrid login --api-key "$DIAGRID_API_KEY"

CUTOFF=$(( $(date +%s) - 6 * 3600 ))

# `diagrid project list -o json` gives name and creation timestamp per project.
diagrid project list -o json \
  | python3 -c '
import json, sys, datetime
cutoff = int(sys.argv[1])
data = json.load(sys.stdin)
items = data if isinstance(data, list) else data.get("items", data.get("projects", []))
for p in items:
    name = p.get("name") or p.get("metadata", {}).get("name", "")
    if not name.startswith("qs-ci-"):
        continue
    created = p.get("createdAt") or p.get("metadata", {}).get("createdAt", "")
    try:
        ts = datetime.datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()
    except ValueError:
        continue
    if ts < cutoff:
        print(name)
' "$CUTOFF" \
  | while read -r stale; do
      echo "Reaping stale project: $stale"
      diagrid project delete "$stale" --yes || \
        echo "::warning::Could not delete $stale"
    done
```

- [ ] **Step 5: Verify the reaper's JSON parsing against real output**

The script guesses at the JSON shape (`items` / `projects` / bare list, `createdAt` at top level or under `metadata`). Confirm it against the real thing:

```bash
diagrid project list -o json | head -40
```

Then simplify the python block to match the actual shape, deleting the fallbacks that do not apply. Re-run to confirm it prints nothing when no `qs-ci-*` projects are older than 6h:

```bash
bash tools/qs-tester/ci/reap-orphans.sh
```

Expected: login output, then no reaping lines (assuming no stale `qs-ci-*` projects exist).

- [ ] **Step 6: Make the scripts executable and verify the guard clauses**

```bash
chmod +x tools/qs-tester/ci/*.sh
env -u DIAGRID_API_KEY bash tools/qs-tester/ci/setup-project.sh; echo "exit=$?"
```

Expected: the `DIAGRID_API_KEY is not set` error and `exit=1`.

```bash
bash tools/qs-tester/ci/teardown-project.sh; echo "exit=$?"
```

Expected: `No project name given and PROJECT is unset; nothing to delete.` and `exit=0`.

- [ ] **Step 7: Commit**

```bash
git add tools/qs-tester/ci
git commit -m "test: add Catalyst ephemeral project lifecycle scripts"
```

---

## Task 5: The state suite

**Files:**
- Create: `state/tests/quickstart.robot`

**Interfaces:**
- Consumes: all keywords from Tasks 2 and 3, all data from Task 1.
- Produces: the suite shape that Tasks 6, 7 and 8 copy. Suite variable `${PROJECT}` comes from the command line (`--variable PROJECT:<name>`).

- [ ] **Step 1: Write the suite**

Create `state/tests/quickstart.robot`:

```robotframework
*** Comments ***
End-to-end test for the state management quickstart, all four languages.

Mirrors state/<language>/README.md exactly: section 4 installs, section 5 runs,
section 6.1 stores and 6.2 retrieves. DELETE /order/{id} is deliberately absent —
no README documents it, and the suites test the documented flow and nothing more.

Run one language at a time:
  cd tools/qs-tester
  uv run robot --include python --variable PROJECT:my-project \
    --outputdir results/state ../../state/tests/quickstart.robot

*** Settings ***
Resource        ../../tools/qs-tester/resources/catalyst.resource
Resource        ../../tools/qs-tester/resources/quickstart.resource
# quickstarts.py is imported twice on purpose. `Variables` exposes its module-level
# dicts as ${STATE_STORE_BODY} and friends; `Library` exposes get_quickstart as the
# `Get Quickstart` keyword. A Variables import alone would NOT provide the keyword.
Variables       ../../tools/qs-tester/variables/quickstarts.py
Library         ../../tools/qs-tester/variables/quickstarts.py
Library         Collections
Suite Setup     Should Not Be Empty    ${PROJECT}
...             msg=Pass --variable PROJECT:<catalyst-project-name>
Test Teardown   Stop Quickstart    ${PROJECT}

*** Variables ***
${PROJECT}      ${EMPTY}

*** Test Cases ***
Csharp State Quickstart
    [Tags]    csharp
    Run State Quickstart    csharp

Java State Quickstart
    [Tags]    java
    Run State Quickstart    java

Javascript State Quickstart
    [Tags]    javascript
    Run State Quickstart    javascript

Python State Quickstart
    [Tags]    python
    Run State Quickstart    python

*** Keywords ***
Run State Quickstart
    [Arguments]    ${language}
    ${qs}=      Get Quickstart    state    ${language}
    ${log}=     Suite Log File    state
    Build Quickstart            ${qs}
    Start Quickstart            ${qs}    ${PROJECT}    ${log}
    # state's app has appPort 0, so no `Connected App ID` line is ever emitted.
    # The keyword iterates an empty list here; the health check is the real gate.
    Wait Until Apps Connected   ${qs}    ${log}
    Wait Until Apps Healthy     ${qs}

    # README 6.1 — store state
    ${expected_store}=      Get From Dictionary    ${STATE_STORE_BODY}    ${language}
    POST And Expect         5001    /order    ${ORDER_PAYLOAD}    201    ${expected_store}
    Wait Until Log Contains    ${log}    ${STATE_SAVE_MARKER}

    # README 6.2 — retrieve state
    ${expected_get}=        Get From Dictionary    ${STATE_RETRIEVE_BODY}    ${language}
    GET And Expect          5001    /order/1    200    ${expected_get}
    Wait Until Log Contains    ${log}    ${STATE_RETRIEVE_MARKER}
```

- [ ] **Step 2: Dry-run the suite**

```bash
cd tools/qs-tester && uv run robot --dryrun --variable PROJECT:dryrun \
  --outputdir results/dryrun ../../state/tests/quickstart.robot
```

Expected: 4 tests, all PASS (dry run resolves keywords and variables without executing).

- [ ] **Step 3: Run one language against a real project**

```bash
export DIAGRID_API_KEY=...          # your Catalyst API key
export LANG_ID=python
eval "$(bash tools/qs-tester/ci/setup-project.sh | grep '^PROJECT=')"
cd tools/qs-tester && uv run robot --include python --variable PROJECT:$PROJECT \
  --outputdir results/state ../../state/tests/quickstart.robot
```

Expected: 1 test PASS. If the response body assertion fails, read the actual body from the failure message and compare it against `state/python/README.md` section 6 — a mismatch is either a transcription error in `quickstarts.py` (fix the table) or genuine drift between the README and the app (report it, do not paper over it).

- [ ] **Step 4: Confirm the log assertions are not vacuous**

Temporarily change `STATE_SAVE_MARKER` in `quickstarts.py` to `"this string is never logged"` and re-run step 3.

Expected: FAIL at `Wait Until Log Contains` after 60s. Restore the real value. A log assertion that can never fail is worse than no assertion, and this is the only way to know.

- [ ] **Step 5: Run the remaining three languages**

```bash
cd tools/qs-tester && uv run robot --variable PROJECT:$PROJECT \
  --outputdir results/state-all ../../state/tests/quickstart.robot
```

Expected: 4 tests PASS. Then delete the project:

```bash
bash tools/qs-tester/ci/teardown-project.sh "$PROJECT"
```

- [ ] **Step 6: Commit**

```bash
git add state/tests/quickstart.robot
git commit -m "test: add end-to-end suite for the state quickstart"
```

---

## Task 6: The invocation suite

**Files:**
- Create: `invocation/tests/quickstart.robot`

**Interfaces:**
- Consumes: the same keywords and data as Task 5.
- Produces: nothing new.

- [ ] **Step 1: Write the suite**

Create `invocation/tests/quickstart.robot`:

```robotframework
*** Comments ***
End-to-end test for the service invocation quickstart, all four languages.

Mirrors invocation/<language>/README.md: section 6.1 posts an order to the client,
which invokes the server through Catalyst. The client returns 500 if the server is
unreachable, so a 200 with the documented body already proves the round trip; the
log markers additionally prove both processes did the work.

Run one language at a time:
  cd tools/qs-tester
  uv run robot --include python --variable PROJECT:my-project \
    --outputdir results/invocation ../../invocation/tests/quickstart.robot

*** Settings ***
Resource        ../../tools/qs-tester/resources/catalyst.resource
Resource        ../../tools/qs-tester/resources/quickstart.resource
# quickstarts.py is imported twice on purpose. `Variables` exposes its module-level
# dicts as ${STATE_STORE_BODY} and friends; `Library` exposes get_quickstart as the
# `Get Quickstart` keyword. A Variables import alone would NOT provide the keyword.
Variables       ../../tools/qs-tester/variables/quickstarts.py
Library         ../../tools/qs-tester/variables/quickstarts.py
Library         Collections
Suite Setup     Should Not Be Empty    ${PROJECT}
...             msg=Pass --variable PROJECT:<catalyst-project-name>
Test Teardown   Stop Quickstart    ${PROJECT}

*** Variables ***
${PROJECT}      ${EMPTY}

*** Test Cases ***
Csharp Invocation Quickstart
    [Tags]    csharp
    Run Invocation Quickstart    csharp

Java Invocation Quickstart
    [Tags]    java
    Run Invocation Quickstart    java

Javascript Invocation Quickstart
    [Tags]    javascript
    Run Invocation Quickstart    javascript

Python Invocation Quickstart
    [Tags]    python
    Run Invocation Quickstart    python

*** Keywords ***
Run Invocation Quickstart
    [Arguments]    ${language}
    ${qs}=      Get Quickstart    invocation    ${language}
    ${log}=     Suite Log File    invocation
    Build Quickstart            ${qs}
    Start Quickstart            ${qs}    ${PROJECT}    ${log}
    # Only `server` has an appPort, so only its connection marker is emitted —
    # matching the README, which names server and not client.
    Wait Until Apps Connected   ${qs}    ${log}
    Wait Until Apps Healthy     ${qs}

    # README 6.1 — client invokes server. Body is identical in all four languages.
    POST And Expect     5001    /order    ${ORDER_PAYLOAD}    200    ${INVOCATION_BODY}

    Wait Until Log Contains     ${log}    ${INVOCATION_SERVER_MARKER}
    ${client_marker}=   Get From Dictionary    ${INVOCATION_CLIENT_MARKER}    ${language}
    Wait Until Log Contains     ${log}    ${client_marker}
```

- [ ] **Step 2: Dry-run the suite**

```bash
cd tools/qs-tester && uv run robot --dryrun --variable PROJECT:dryrun \
  --outputdir results/dryrun ../../invocation/tests/quickstart.robot
```

Expected: 4 tests, all PASS.

- [ ] **Step 3: Run all four languages against a real project**

```bash
export DIAGRID_API_KEY=...
export LANG_ID=python
eval "$(bash tools/qs-tester/ci/setup-project.sh | grep '^PROJECT=')"
cd tools/qs-tester && uv run robot --variable PROJECT:$PROJECT \
  --outputdir results/invocation ../../invocation/tests/quickstart.robot
```

Expected: 4 tests PASS. The java client marker (`Invoke Successful. Response received: 1`) is the one most likely to be wrong, since it is worded unlike the other three — check `invocation/java/client/src/main/java/com/service/controller/Controller.java` if it fails.

- [ ] **Step 4: Tear down and commit**

```bash
bash tools/qs-tester/ci/teardown-project.sh "$PROJECT"
git add invocation/tests/quickstart.robot
git commit -m "test: add end-to-end suite for the invocation quickstart"
```

---

## Task 7: The pubsub suite

**Files:**
- Create: `pubsub/tests/quickstart.robot`

**Interfaces:**
- Consumes: the same keywords and data as Task 5.
- Produces: nothing new.

- [ ] **Step 1: Write the suite**

Create `pubsub/tests/quickstart.robot`:

```robotframework
*** Comments ***
End-to-end test for the pub/sub quickstart, all four languages.

Mirrors pubsub/<language>/README.md section 6.1, which publishes one order.

The subscriber log marker is not optional decoration: the publisher returns 201 as
soon as the broker accepts the message, and the subscriber exposes no queryable
endpoint, so without that marker a broken subscription or a mis-scoped
subscription.yaml would pass a green test.

Run one language at a time:
  cd tools/qs-tester
  uv run robot --include python --variable PROJECT:my-project \
    --outputdir results/pubsub ../../pubsub/tests/quickstart.robot

*** Settings ***
Resource        ../../tools/qs-tester/resources/catalyst.resource
Resource        ../../tools/qs-tester/resources/quickstart.resource
# quickstarts.py is imported twice on purpose. `Variables` exposes its module-level
# dicts as ${STATE_STORE_BODY} and friends; `Library` exposes get_quickstart as the
# `Get Quickstart` keyword. A Variables import alone would NOT provide the keyword.
Variables       ../../tools/qs-tester/variables/quickstarts.py
Library         ../../tools/qs-tester/variables/quickstarts.py
Library         Collections
Suite Setup     Should Not Be Empty    ${PROJECT}
...             msg=Pass --variable PROJECT:<catalyst-project-name>
Test Teardown   Stop Quickstart    ${PROJECT}

*** Variables ***
${PROJECT}      ${EMPTY}

*** Test Cases ***
Csharp Pubsub Quickstart
    [Tags]    csharp
    Run Pubsub Quickstart    csharp

Java Pubsub Quickstart
    [Tags]    java
    Run Pubsub Quickstart    java

Javascript Pubsub Quickstart
    [Tags]    javascript
    Run Pubsub Quickstart    javascript

Python Pubsub Quickstart
    [Tags]    python
    Run Pubsub Quickstart    python

*** Keywords ***
Run Pubsub Quickstart
    [Arguments]    ${language}
    ${qs}=      Get Quickstart    pubsub    ${language}
    ${log}=     Suite Log File    pubsub
    Build Quickstart            ${qs}
    Start Quickstart            ${qs}    ${PROJECT}    ${log}
    # Both apps have an appPort, so both connection markers are emitted — the
    # README tells the user to wait for exactly these two lines.
    Wait Until Apps Connected   ${qs}    ${log}
    Wait Until Apps Healthy     ${qs}

    # README 6.1 — publish
    ${expected}=    Get From Dictionary    ${PUBSUB_PUBLISH_BODY}    ${language}
    POST And Expect     5001    /order    ${ORDER_PAYLOAD}    201    ${expected}
    Wait Until Log Contains     ${log}    ${PUBSUB_PUBLISH_MARKER}

    # Delivery to the subscriber. Longer timeout than the other markers: this is
    # a round trip through the managed broker, not a local function call.
    ${receive_marker}=  Get From Dictionary    ${PUBSUB_RECEIVE_MARKER}    ${language}
    Wait Until Log Contains     ${log}    ${receive_marker}    timeout=120s
```

- [ ] **Step 2: Dry-run the suite**

```bash
cd tools/qs-tester && uv run robot --dryrun --variable PROJECT:dryrun \
  --outputdir results/dryrun ../../pubsub/tests/quickstart.robot
```

Expected: 4 tests, all PASS.

- [ ] **Step 3: Run all four languages against a real project**

```bash
export DIAGRID_API_KEY=...
export LANG_ID=python
eval "$(bash tools/qs-tester/ci/setup-project.sh | grep '^PROJECT=')"
cd tools/qs-tester && uv run robot --variable PROJECT:$PROJECT \
  --outputdir results/pubsub ../../pubsub/tests/quickstart.robot
```

Expected: 4 tests PASS. The javascript subscriber marker is the JSON form
(`Order received: {"orderId":1}`); if it fails, check the exact serialization in
`pubsub/javascript/subscriber/index.js` and correct `PUBSUB_RECEIVE_MARKER`.

- [ ] **Step 4: Prove the delivery assertion can fail**

This is the single most important verification in the plan, because a vacuous
subscriber assertion would make the pubsub suite meaningless.

Temporarily edit `pubsub/python/subscription.yaml` to point at a topic no one
publishes to:

```yaml
spec:
  topic: nobody-publishes-here
```

Re-run step 3 with `--include python`.

Expected: the POST still returns 201 and the publisher marker still appears, but
the suite FAILS at the subscriber marker after 120s. Revert `subscription.yaml`
afterwards with `git checkout pubsub/python/subscription.yaml`.

- [ ] **Step 5: Tear down and commit**

```bash
bash tools/qs-tester/ci/teardown-project.sh "$PROJECT"
git add pubsub/tests/quickstart.robot
git commit -m "test: add end-to-end suite for the pubsub quickstart"
```

---

## Task 8: The workflow suite

**Files:**
- Create: `workflow/tests/quickstart.robot`

**Interfaces:**
- Consumes: the same keywords and data as Task 5, plus `WORKFLOW_INSTANCE_KEY`, `WORKFLOW_START_MARKER`, `WORKFLOW_DONE_MARKER`.
- Produces: nothing new.

- [ ] **Step 1: Write the suite**

Create `workflow/tests/quickstart.robot`:

```robotframework
*** Comments ***
End-to-end test for the workflow quickstart, all four languages.

Mirrors workflow/<language>/README.md: section 6.1 starts an instance, 6.2 gets
its status. POST /workflow/terminate/{id} is deliberately absent — no README
documents it.

Completion is gated on the log marker `Order <id> has completed!`, not on the
status JSON. Only the python README shows the status body, and what it shows is
`"runtimeStatus":1` — a numeric enum — so a substring check for COMPLETED would
fail there and cannot be confirmed for the other three from any documented source.
The notification messages, by contrast, are identical in all four languages and the
completion one only fires after reserve-inventory, process-payment and
update-inventory have all succeeded.

Run one language at a time:
  cd tools/qs-tester
  uv run robot --include python --variable PROJECT:my-project \
    --outputdir results/workflow ../../workflow/tests/quickstart.robot

*** Settings ***
Resource        ../../tools/qs-tester/resources/catalyst.resource
Resource        ../../tools/qs-tester/resources/quickstart.resource
# quickstarts.py is imported twice on purpose. `Variables` exposes its module-level
# dicts as ${STATE_STORE_BODY} and friends; `Library` exposes get_quickstart as the
# `Get Quickstart` keyword. A Variables import alone would NOT provide the keyword.
Variables       ../../tools/qs-tester/variables/quickstarts.py
Library         ../../tools/qs-tester/variables/quickstarts.py
Library         Collections
Library         String
Suite Setup     Should Not Be Empty    ${PROJECT}
...             msg=Pass --variable PROJECT:<catalyst-project-name>
Test Teardown   Stop Quickstart    ${PROJECT}

*** Variables ***
${PROJECT}      ${EMPTY}

*** Test Cases ***
Csharp Workflow Quickstart
    [Tags]    csharp
    Run Workflow Quickstart    csharp

Java Workflow Quickstart
    [Tags]    java
    Run Workflow Quickstart    java

Javascript Workflow Quickstart
    [Tags]    javascript
    Run Workflow Quickstart    javascript

Python Workflow Quickstart
    [Tags]    python
    Run Workflow Quickstart    python

*** Keywords ***
Run Workflow Quickstart
    [Arguments]    ${language}
    ${qs}=      Get Quickstart    workflow    ${language}
    ${log}=     Suite Log File    workflow
    Build Quickstart            ${qs}
    Start Quickstart            ${qs}    ${PROJECT}    ${log}
    # workflow's app has appPort 0, so no connection marker exists; the health
    # check on 5001 is the only readiness gate.
    Wait Until Apps Connected   ${qs}    ${log}
    Wait Until Apps Healthy     ${qs}

    # README 6.1 — start an instance and read the instance id. javascript returns
    # `instance_id` where the other three return `instanceId`.
    ${body}=            POST And Expect    5001    /workflow/start
    ...                 ${WORKFLOW_PAYLOAD}    200
    ${key}=             Get From Dictionary    ${WORKFLOW_INSTANCE_KEY}    ${language}
    ${instance_id}=     Get From Dictionary    ${body}    ${key}
    Should Not Be Empty    ${instance_id}

    # Both markers interpolate the real instance id, so they prove *this* run's
    # workflow executed rather than merely that some workflow did.
    ${start_marker}=    Replace String    ${WORKFLOW_START_MARKER}    {id}    ${instance_id}
    Wait Until Log Contains     ${log}    ${start_marker}    timeout=120s

    ${done_marker}=     Replace String    ${WORKFLOW_DONE_MARKER}    {id}    ${instance_id}
    Wait Until Log Contains     ${log}    ${done_marker}    timeout=180s

    # README 6.2 — get status. Asserting only what is documented: 200 with a
    # non-empty body, plus python's documented completion flag.
    ${status}=          GET And Expect    5001    /workflow/status/${instance_id}    200
    Should Not Be Empty    ${status}
    IF    '${language}' == 'python'
        Dictionary Should Contain Item    ${status}    isWorkflowCompleted    ${True}
    END
```

- [ ] **Step 2: Dry-run the suite**

```bash
cd tools/qs-tester && uv run robot --dryrun --variable PROJECT:dryrun \
  --outputdir results/dryrun ../../workflow/tests/quickstart.robot
```

Expected: 4 tests, all PASS.

- [ ] **Step 3: Run all four languages against a real project**

```bash
export DIAGRID_API_KEY=...
export LANG_ID=python
eval "$(bash tools/qs-tester/ci/setup-project.sh | grep '^PROJECT=')"
cd tools/qs-tester && uv run robot --variable PROJECT:$PROJECT \
  --outputdir results/workflow ../../workflow/tests/quickstart.robot
```

Expected: 4 tests PASS. `workflow/java` is the leg most likely to fail first: it is the only one using the `--app-id ... -- mvn spring-boot:run` form, because it has no `workflow-quickstart.yaml`.

- [ ] **Step 4: Record the three undocumented status bodies**

For csharp, java and javascript, copy the actual `GET /workflow/status/{id}` response out of `results/workflow/log.html` into the task notes. The spec flags this as a documentation gap; capturing the real shapes here is what allows a follow-up to either tighten these assertions or fix the READMEs.

Do not tighten the assertions in this task — that would change what the suite tests based on one observation.

- [ ] **Step 5: Tear down and commit**

```bash
bash tools/qs-tester/ci/teardown-project.sh "$PROJECT"
git add workflow/tests/quickstart.robot
git commit -m "test: add end-to-end suite for the workflow quickstart"
```

---

## Task 9: doc-sync checker

**Files:**
- Create: `tools/qs-tester/docsync/check_readme_sync.py`
- Create: `tools/qs-tester/docsync/tests/test_check_readme_sync.py`

**Interfaces:**
- Consumes: `quickstarts.py` from Task 1 and the 16 `README.md` files.
- Produces: a CLI `python docsync/check_readme_sync.py <api> <language>` exiting 0 on match and 1 on mismatch, plus `--all` to check all 16. Importable functions `extract_bash_blocks(markdown, section) -> list[str]`, `extract_curl_calls(markdown) -> list[dict]`, `extract_json_blocks(markdown, section) -> list[dict]`, and `check(api, language, repo_root) -> list[str]` returning human-readable mismatch descriptions.

- [ ] **Step 1: Write the failing tests**

Create `tools/qs-tester/docsync/tests/test_check_readme_sync.py`:

```python
import pytest
from check_readme_sync import (
    extract_bash_blocks,
    extract_curl_calls,
    extract_json_blocks,
    normalise_run_command,
)

README = """\
# Quickstart: State Management (Python)

## 1. Prerequisites

- Python 3.12+

## 4. Install Dependencies

```bash
uv venv
source .venv/bin/activate
```

Install dependencies:

```bash
uv sync
```

## 5. Run the application with Catalyst Cloud

```bash
diagrid dev run -f state-quickstart.yaml --project state-quickstart --approve
```

## 6. Call the State API

### 6.1 Store state

**macOS/Linux (curl):**

```bash
curl -i -X POST http://localhost:5001/order -H "Content-Type: application/json" -d '{"orderId":1}'
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:5001/order"
```

The expected response is `201 Created` with this body:

```json
{"id":1,"message":"Order created successfully"}
```

## 7. Clean Up

```bash
diagrid project delete state-quickstart
```
"""


def test_extract_bash_blocks_returns_only_the_named_section():
    assert extract_bash_blocks(README, "4") == [
        "uv venv\nsource .venv/bin/activate",
        "uv sync",
    ]
    assert extract_bash_blocks(README, "5") == [
        "diagrid dev run -f state-quickstart.yaml --project state-quickstart --approve"
    ]


def test_extract_bash_blocks_ignores_powershell():
    blocks = extract_bash_blocks(README, "6")
    assert len(blocks) == 1
    assert blocks[0].startswith("curl -i -X POST")
    assert not any("Invoke-RestMethod" in b for b in blocks)


def test_extract_curl_calls_parses_method_url_and_payload():
    assert extract_curl_calls(README) == [
        {
            "method": "POST",
            "url": "http://localhost:5001/order",
            "payload": {"orderId": 1},
        }
    ]


def test_extract_json_blocks_returns_expected_bodies():
    assert extract_json_blocks(README, "6") == [
        {"id": 1, "message": "Order created successfully"}
    ]


def test_normalise_run_command_replaces_the_documented_project_name():
    documented = "diagrid dev run -f state-quickstart.yaml --project state-quickstart --approve"
    harness = "diagrid dev run -f state-quickstart.yaml --project {project} --approve"
    assert normalise_run_command(documented) == normalise_run_command(harness)


def test_normalise_run_command_keeps_other_differences_visible():
    a = "diagrid dev run -f state-quickstart.yaml --project {project} --approve"
    b = "diagrid dev run -f wrong-file.yaml --project {project} --approve"
    assert normalise_run_command(a) != normalise_run_command(b)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd tools/qs-tester && uv run pytest docsync/tests/test_check_readme_sync.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'check_readme_sync'`.

- [ ] **Step 3: Write the checker**

Create `tools/qs-tester/docsync/check_readme_sync.py`:

```python
"""Assert each quickstart README's commands match what the suites actually run.

The READMEs are the source of truth for the end-to-end suites, so a README edit
that the suites have not followed is drift. This catches that on every PR, with no
credentials and no Catalyst project.

The check runs one way only: every documented command must be covered by the
harness. The suites legitimately do things no README describes — poll a health
endpoint, wait for a readiness marker, create and delete a project — so checking
the reverse direction would flag the harness's own internals.

Usage:
    python docsync/check_readme_sync.py state python
    python docsync/check_readme_sync.py --all
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path

import quickstarts as qs

# A fenced block: ```<lang>\n<body>\n```
_FENCE = re.compile(r"^```(\w*)\n(.*?)^```", re.MULTILINE | re.DOTALL)
# A section heading: `## 4. ...` or `### 6.1 ...`
_HEADING = re.compile(r"^#{2,3} (\d+(?:\.\d+)?)\.? ", re.MULTILINE)


def _section_span(markdown: str, section: str) -> tuple[int, int]:
    """Character span of a numbered section, up to the next same-or-higher heading."""
    starts = [(m.group(1), m.start()) for m in _HEADING.finditer(markdown)]
    for i, (number, start) in enumerate(starts):
        if number != section:
            continue
        for later_number, later_start in starts[i + 1 :]:
            # A subsection (6.1 inside 6) stays part of the parent section.
            if not later_number.startswith(f"{section}."):
                return start, later_start
        return start, len(markdown)
    return 0, 0


def _blocks(markdown: str, section: str, language: str) -> list[str]:
    start, end = _section_span(markdown, section)
    return [
        body.strip()
        for lang, body in (
            (m.group(1), m.group(2)) for m in _FENCE.finditer(markdown[start:end])
        )
        if lang == language
    ]


def extract_bash_blocks(markdown: str, section: str) -> list[str]:
    """Fenced ```bash blocks in a section. PowerShell blocks are ignored:
    every request is documented three ways and the suites use one."""
    return _blocks(markdown, section, "bash")


def extract_json_blocks(markdown: str, section: str) -> list[dict]:
    """Parsed ```json blocks in a section — the documented expected bodies.
    Blocks containing placeholders like <YOUR_INSTANCE_ID> are skipped, since
    they are illustrative rather than assertable."""
    parsed = []
    for block in _blocks(markdown, section, "json"):
        if "<" in block and ">" in block:
            continue
        try:
            parsed.append(json.loads(block))
        except json.JSONDecodeError:
            continue
    return parsed


def extract_curl_calls(markdown: str) -> list[dict]:
    """Method, URL and JSON payload of each documented curl invocation."""
    calls = []
    for block in extract_bash_blocks(markdown, "6"):
        if not block.startswith("curl"):
            continue
        tokens = shlex.split(block)
        method, url, payload = "GET", None, None
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token in ("-X", "--request"):
                method = tokens[i + 1]
                i += 2
            elif token in ("-d", "--data"):
                payload = json.loads(tokens[i + 1])
                i += 2
            elif token in ("-H", "--header"):
                i += 2
            elif token.startswith("http"):
                url = token
                i += 1
            else:
                i += 1
        calls.append({"method": method, "url": url, "payload": payload})
    return calls


def normalise_run_command(command: str) -> str:
    """Collapse the one sanctioned divergence: the READMEs document
    `--project <api>-quickstart`, the harness passes `{project}`."""
    return re.sub(r"--project \S+", "--project PROJECT", command).strip()


def check(api: str, language: str, repo_root: Path) -> list[str]:
    """Return a list of mismatch descriptions; empty means in sync."""
    readme = repo_root / api / language / "README.md"
    if not readme.is_file():
        return [f"{api}/{language}: README.md not found"]
    markdown = readme.read_text()
    problems = []
    where = f"{api}/{language}"

    documented_install = "\n".join(extract_bash_blocks(markdown, "4"))
    harness_install = qs.INSTALL[(api, language)]
    for line in documented_install.splitlines():
        line = line.strip()
        # Activation is expressed as `. .venv/bin/activate` in the harness and
        # `source .venv/bin/activate` in the README; same thing, different spelling.
        if line.startswith("source "):
            line = ". " + line.split(" ", 1)[1]
        if line and line not in harness_install:
            problems.append(
                f"{where}: README install step not in harness: {line!r}\n"
                f"  harness has: {harness_install!r}"
            )

    documented_run = extract_bash_blocks(markdown, "5")
    if not documented_run:
        problems.append(f"{where}: no bash block found in README section 5")
    else:
        want = normalise_run_command(documented_run[0])
        got = normalise_run_command(qs.RUN[(api, language)])
        if want != got:
            problems.append(
                f"{where}: run command differs\n  README:  {want}\n  harness: {got}"
            )

    for call in extract_curl_calls(markdown):
        if call["payload"] is None:
            continue
        known = (qs.ORDER_PAYLOAD, qs.WORKFLOW_PAYLOAD)
        if call["payload"] not in known:
            problems.append(
                f"{where}: documented payload {call['payload']!r} is not one of "
                f"the harness payloads {known!r}"
            )

    expected_bodies = extract_json_blocks(markdown, "6")
    harness_bodies = _harness_bodies(api, language)
    for body in expected_bodies:
        if body not in harness_bodies:
            problems.append(
                f"{where}: README expected body not asserted by the harness:\n"
                f"  {body!r}\n  harness asserts: {harness_bodies!r}"
            )

    return problems


def _harness_bodies(api: str, language: str) -> list[dict]:
    """Every response body the suite for this (api, language) asserts."""
    if api == "state":
        return [qs.STATE_STORE_BODY[language], qs.STATE_RETRIEVE_BODY[language]]
    if api == "pubsub":
        return [qs.PUBSUB_PUBLISH_BODY[language]]
    if api == "invocation":
        return [qs.INVOCATION_BODY]
    # workflow: the start response is documented only with a placeholder instance
    # id, which extract_json_blocks skips, and the status body is not documented
    # concretely except for python's, which the suite asserts by key not by body.
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("api", nargs="?", choices=qs.APIS)
    parser.add_argument("language", nargs="?", choices=qs.LANGUAGES)
    parser.add_argument("--all", action="store_true", help="check all 16")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="repository root (default: three levels above this file)",
    )
    args = parser.parse_args()

    if args.all:
        pairs = [(a, l) for a in qs.APIS for l in qs.LANGUAGES]
    elif args.api and args.language:
        pairs = [(args.api, args.language)]
    else:
        parser.error("give both api and language, or --all")

    problems = []
    for api, language in pairs:
        problems.extend(check(api, language, args.repo_root))

    if problems:
        for problem in problems:
            print(f"::error::{problem}")
        print(f"\n{len(problems)} README/harness mismatch(es) in {len(pairs)} directories")
        return 1

    print(f"All {len(pairs)} README(s) in sync with the harness")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the unit tests to verify they pass**

```bash
cd tools/qs-tester && uv run pytest docsync/tests/test_check_readme_sync.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 5: Run the checker against all 16 real READMEs**

```bash
cd tools/qs-tester && uv run python docsync/check_readme_sync.py --all
```

Expected: `All 16 README(s) in sync with the harness`.

**This was pre-validated while writing the plan.** The extraction regexes were run against `state/python`, `state/java`, `pubsub/javascript` and `workflow/csharp`, and the install/run comparison was run across all 16 directories: zero mismatches. So a clean result here is the expected outcome, not a hope, and any mismatch means Task 1's table was transcribed differently from the plan.

Two behaviours the pre-validation confirmed, worth knowing before you debug anything:

- `state/python` section 4 yields two bash blocks (`uv venv\nsource .venv/bin/activate` and `uv sync`), and the `source ` → `. ` normalisation makes all three lines match the harness string.
- `workflow/*` section 6 yields **no** JSON bodies, because the only documented block is `{"instanceId":"<YOUR_INSTANCE_ID>"}` and `extract_json_blocks` skips placeholder blocks. That is why `_harness_bodies` returns `[]` for workflow — the two agree by design, not by accident.

If it does report mismatches, each is either a transcription error in `quickstarts.py` (fix the table) or an over-strict rule in the checker (fix the rule). Do not weaken a rule to silence a real mismatch — that defeats the purpose of the check.

- [ ] **Step 6: Prove the checker catches drift**

```bash
sed -i.bak 's/uv sync/uv sync --frozen/' state/python/README.md
cd tools/qs-tester && uv run python docsync/check_readme_sync.py state python; echo "exit=$?"
```

Expected: an `::error::` line naming the uncovered install step, and `exit=1`.

Restore: `mv state/python/README.md.bak state/python/README.md`

- [ ] **Step 7: Commit**

```bash
git add tools/qs-tester/docsync
git commit -m "test: add README/harness doc-sync checker"
```

---

## Task 10: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/e2e-quickstarts.yml`

**Interfaces:**
- Consumes: everything from Tasks 1–9. `DIAGRID_API_KEY` from the repository's configured value.
- Produces: artifacts `robot-<lang>` containing `results/`, and `failed-<lang>.txt` naming failed APIs.

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/e2e-quickstarts.yml`:

```yaml
name: E2E quickstart tests

on:
  schedule:
    - cron: '0 5 * * *'   # daily 05:00 UTC
  workflow_dispatch:
    inputs:
      language:
        description: 'Single language to run (blank = all four)'
        required: false
        type: choice
        options: ['', csharp, java, javascript, python]
      api:
        description: 'Single API to run (blank = all four)'
        required: false
        type: choice
        options: ['', workflow, state, pubsub, invocation]
  pull_request:
    paths:
      - 'tools/qs-tester/**'
      - '*/tests/quickstart.robot'
      - '*/*/README.md'
      - '.github/workflows/e2e-quickstarts.yml'

# Do not cancel in progress: a cancelled leg never runs teardown and leaks its
# Catalyst project.
concurrency:
  group: e2e-quickstarts
  cancel-in-progress: false

permissions:
  contents: read
  issues: write

env:
  DIAGRID_CLI_VERSION: '1.36.0'

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - name: Sync harness
        run: (cd tools/qs-tester && uv sync)
      - name: Resolve suites without executing
        run: |
          cd tools/qs-tester
          uv run robot --dryrun --variable PROJECT:dryrun --outputdir results/dryrun \
            ../../workflow/tests/quickstart.robot \
            ../../state/tests/quickstart.robot \
            ../../pubsub/tests/quickstart.robot \
            ../../invocation/tests/quickstart.robot
      - name: Check READMEs match the harness
        run: (cd tools/qs-tester && uv run python docsync/check_readme_sync.py --all)
      - name: Unit-test the doc-sync checker
        run: (cd tools/qs-tester && uv run pytest docsync/tests -q)

  reap:
    if: github.event_name == 'schedule' && github.repository_owner == 'diagridio'
    runs-on: ubuntu-latest
    environment: shared-production
    env:
      DIAGRID_API_KEY: ${{ secrets.DIAGRID_API_KEY }}
    steps:
      - uses: actions/checkout@v4
      - name: Install diagrid CLI
        run: |
          curl -o- https://downloads.diagrid.io/cli/install.sh | bash -s "$DIAGRID_CLI_VERSION"
          sudo mv ./diagrid /usr/local/bin
      - name: Delete qs-ci-* projects older than 6h
        run: bash tools/qs-tester/ci/reap-orphans.sh

  e2e:
    if: github.event_name != 'pull_request' && github.repository_owner == 'diagridio'
    runs-on: ubuntu-latest
    environment: shared-production
    timeout-minutes: 60
    strategy:
      fail-fast: false
      # Never more than two concurrent Catalyst projects. Order pairs each
      # build-heavy language with a fast one so both slots stay busy.
      max-parallel: 2
      matrix:
        lang: [java, javascript, csharp, python]
    env:
      DIAGRID_API_KEY: ${{ secrets.DIAGRID_API_KEY }}
      LANG_ID: ${{ matrix.lang }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5

      - name: Set up .NET
        if: matrix.lang == 'csharp'
        uses: actions/setup-dotnet@v4
        with:
          dotnet-version: '10.0.x'

      - name: Set up Java
        if: matrix.lang == 'java'
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '17'

      - name: Cache Maven repository
        if: matrix.lang == 'java'
        uses: actions/cache@v4
        with:
          path: ~/.m2/repository
          key: maven-qs-${{ github.run_id }}
          restore-keys: maven-qs-

      - name: Set up Node
        if: matrix.lang == 'javascript'
        uses: actions/setup-node@v4
        with:
          node-version: 'lts/*'

      - name: Install diagrid CLI
        run: |
          curl -o- https://downloads.diagrid.io/cli/install.sh | bash -s "$DIAGRID_CLI_VERSION"
          sudo mv ./diagrid /usr/local/bin
          diagrid version

      - name: Sync harness
        run: (cd tools/qs-tester && uv sync)

      - name: Create ephemeral Catalyst project
        run: bash tools/qs-tester/ci/setup-project.sh

      # Pre-warm OUTSIDE the timed Robot build keyword. On a cold ~/.m2 the
      # dependency download alone can exceed the build timeout and get killed
      # mid-download; the timed step should only have to compile.
      - name: Pre-warm Maven dependencies
        if: matrix.lang == 'java'
        run: |
          for dir in workflow/java state/java \
                     pubsub/java/publisher pubsub/java/subscriber \
                     invocation/java/client invocation/java/server; do
            echo "::group::go-offline $dir"
            mvn -q -B -f "$dir/pom.xml" dependency:go-offline || true
            echo "::endgroup::"
          done

      - name: Run quickstart suites
        run: |
          mkdir -p tools/qs-tester/results
          cd tools/qs-tester
          # Run every API even if an earlier one fails, so one nightly run reports
          # all broken APIs for this language. The `if !` guard is exempt from set -e.
          apis="${{ inputs.api }}"
          [ -z "$apis" ] && apis="workflow state pubsub invocation"
          failed=""
          for api in $apis; do
            if ! uv run robot --outputdir "results/$api" \
                 --include "${{ matrix.lang }}" \
                 --variable "PROJECT:$PROJECT" \
                 "../../$api/tests/quickstart.robot"; then
              failed="$failed $api"
            fi
          done
          # Merge into one indexed report. `|| true` because rebot's exit code
          # reflects test failures too.
          uv run rebot --outputdir results --name "quickstarts (${{ matrix.lang }})" \
            results/*/output.xml || true
          if [ -n "$failed" ]; then
            echo "${{ matrix.lang }}:$failed" > results/failed-${{ matrix.lang }}.txt
            echo "::error::Failed APIs (${{ matrix.lang }}):$failed"
            exit 1
          fi

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: robot-${{ matrix.lang }}
          path: tools/qs-tester/results/

      - name: Delete ephemeral Catalyst project
        if: always()
        run: bash tools/qs-tester/ci/teardown-project.sh

  report:
    needs: [lint, e2e]
    if: failure() && github.event_name != 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - name: Download failure summaries
        uses: actions/download-artifact@v4
        continue-on-error: true
        with:
          path: artifacts
      - uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const path = require('path');
            // Each failing leg wrote failed-<lang>.txt (e.g. "python: pubsub")
            // into its artifact; gather them so the issue names exact failures.
            const lines = [];
            const walk = (dir) => {
              for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
                const p = path.join(dir, entry.name);
                if (entry.isDirectory()) walk(p);
                else if (/^failed-.*\.txt$/.test(entry.name)) {
                  const txt = fs.readFileSync(p, 'utf8').trim();
                  if (txt) lines.push(txt);
                }
              }
            };
            if (fs.existsSync('artifacts')) walk('artifacts');
            lines.sort();
            const details = lines.length
              ? lines.map(l => `  - \`${l}\``).join('\n')
              : '  - (no per-API detail captured — check the failing job logs)';
            const legs = [...new Set(lines.map(l => l.split(':')[0].trim()))].filter(Boolean);
            const downloads = (legs.length ? legs : ['<lang>'])
              .map(l => `gh run download ${context.runId} -n robot-${l} -D ./report-${l}`)
              .join('\n');
            const title = 'Quickstart e2e tests failing';
            const runUrl = `${context.serverUrl}/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}`;
            const body = [
              `The quickstart end-to-end tests **failed**.`,
              ``,
              `**Failing legs (\`language: api …\`):**`,
              details,
              ``,
              `- Run: ${runUrl}`,
              `- For a per-language index, download the \`robot-<lang>\` artifact and open`,
              `  \`report.html\` (every API listed, failures in red) or \`log.html\`.`,
              ``,
              `Download the report(s) for the failing leg(s):`,
              '```bash',
              downloads,
              '```',
              ``,
              `_This issue is updated automatically each run._`,
            ].join('\n');
            const existing = await github.rest.issues.listForRepo({
              owner: context.repo.owner, repo: context.repo.repo,
              state: 'open', labels: 'e2e-failure',
            });
            const match = existing.data.find(i => i.title === title);
            if (match) {
              await github.rest.issues.createComment({
                owner: context.repo.owner, repo: context.repo.repo,
                issue_number: match.number, body,
              });
            } else {
              await github.rest.issues.create({
                owner: context.repo.owner, repo: context.repo.repo,
                title, body, labels: ['e2e-failure'],
              });
            }
```

The workflow maps the key into an environment variable with
`DIAGRID_API_KEY: ${{ secrets.DIAGRID_API_KEY }}`. An API key belongs in a secret, but
if this repository stores it as an Actions *variable* instead, change both occurrences
to `${{ vars.DIAGRID_API_KEY }}`. Either way the scripts see it as a plain environment
variable, which is all they require.

- [ ] **Step 2: Validate the workflow file parses**

```bash
python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/e2e-quickstarts.yml')); print('valid YAML')"
```

Expected: `valid YAML`

- [ ] **Step 3: Confirm the CLI installer accepts a pinned version**

The install step passes the version as `bash -s "$DIAGRID_CLI_VERSION"`. Verify that is how the installer takes a version:

```bash
curl -s https://downloads.diagrid.io/cli/install.sh | head -40
```

Expected: a script whose argument handling you can read. If it takes the version differently (an env var, or no pinning at all), correct both install steps. If pinning is not supported, drop `DIAGRID_CLI_VERSION` and note in `tools/qs-tester/README.md` that the CLI floats.

- [ ] **Step 4: Create the issue label**

```bash
gh label create e2e-failure --description "Quickstart e2e test failures" --color B60205 || \
  echo "label already exists"
```

- [ ] **Step 5: Commit and push the branch**

```bash
git add .github/workflows/e2e-quickstarts.yml
git commit -m "ci: add daily e2e quickstart test workflow"
git push -u origin HEAD
```

- [ ] **Step 6: Trigger one leg manually and confirm it goes green**

```bash
gh workflow run e2e-quickstarts.yml --ref "$(git branch --show-current)" -f language=python
gh run watch
```

Expected: the `lint` job passes, and the `python` leg passes all four APIs.

If the leg fails, download the report and read it rather than guessing:

```bash
gh run download "$(gh run list --workflow=e2e-quickstarts.yml --limit 1 --json databaseId -q '.[0].databaseId')" \
  -n robot-python -D ./report-python
open ./report-python/report.html
```

- [ ] **Step 7: Confirm no project was leaked**

```bash
diagrid project list | grep qs-ci- || echo "no leaked projects"
```

Expected: `no leaked projects`. If one survives, teardown did not run — check the `if: always()` step's log before continuing.

- [ ] **Step 8: Run the full matrix, then commit the README**

```bash
gh workflow run e2e-quickstarts.yml --ref "$(git branch --show-current)"
gh run watch
```

Expected: all four legs pass, and at most two run concurrently. Confirm the concurrency cap by checking the run's timeline in the Actions UI — two legs should start and the other two should queue.

---

## Task 11: Harness README

**Files:**
- Create: `tools/qs-tester/README.md`

**Interfaces:**
- Consumes: the finished harness.
- Produces: nothing.

- [ ] **Step 1: Write the README**

Create `tools/qs-tester/README.md`:

```markdown
# qs-tester

End-to-end tests for the `workflow`, `state`, `pubsub`, and `invocation` quickstarts,
built on [Robot Framework](https://robotframework.org/). The tests run the *actual*
commands each quickstart's README documents and assert the responses and log output
that README promises, so drift between the docs, the code, and Catalyst is caught
automatically.

Design: `docs/superpowers/specs/2026-07-28-quickstart-e2e-tests-design.md`.

## Layout

- `resources/process.resource` — background process lifecycle and PID-tree teardown.
- `resources/catalyst.resource` — `diagrid dev run` launch, stop, readiness markers.
- `resources/quickstart.resource` — build, health polling, HTTP assertions.
- `variables/quickstarts.py` — the per-(API, language) table. **Everything in it is
  transcribed from a README.** Change a README, change this file.
- `docsync/check_readme_sync.py` — asserts the two stay in agreement.
- `ci/` — Catalyst project lifecycle scripts.

Each suite lives next to the quickstarts it tests: `state/tests/quickstart.robot`,
`pubsub/tests/quickstart.robot`, and so on. Each has four tests tagged `csharp`,
`java`, `javascript`, `python`.

## Running locally

`robot`, `rebot`, `uv` and the doc-sync checker all run from `tools/qs-tester/`, so
suite paths are relative to it (`../../state/tests/quickstart.robot`).

### One-time setup

```bash
export DIAGRID_API_KEY=...     # a Catalyst API key
(cd tools/qs-tester && uv sync)
```

### Create a project and run a suite

Every suite needs a Catalyst project. `ci/setup-project.sh` creates a throwaway one
and prints its name:

```bash
export LANG_ID=python
eval "$(bash tools/qs-tester/ci/setup-project.sh | grep '^PROJECT=')"

cd tools/qs-tester
uv run robot --include python --variable PROJECT:$PROJECT \
  --outputdir results/state ../../state/tests/quickstart.robot
```

Delete it when you are done — these are not free:

```bash
bash tools/qs-tester/ci/teardown-project.sh "$PROJECT"
```

### Selecting languages and APIs

Each suite has four tests tagged by language. Filter with `--include` / `--exclude`
(repeatable, `--include` ORs):

```bash
# one language, one API
uv run robot --include python --variable PROJECT:$PROJECT \
  ../../state/tests/quickstart.robot

# two languages
uv run robot --include csharp --include java --variable PROJECT:$PROJECT \
  ../../pubsub/tests/quickstart.robot

# all four APIs, one language, one combined report
uv run robot --include python --variable PROJECT:$PROJECT --name "Quickstarts (python)" \
  ../../workflow/tests/quickstart.robot ../../state/tests/quickstart.robot \
  ../../pubsub/tests/quickstart.robot ../../invocation/tests/quickstart.robot
```

Only one language at a time per project: all four languages of a given quickstart
share appIDs (`order-app`, `publisher`/`subscriber`, `client`/`server`,
`order-workflow`) and ports 5001/5002, so two languages cannot run concurrently in
one project or on one machine.

### Checks that need no Catalyst project

```bash
cd tools/qs-tester

# resolve syntax, keywords and variables without running anything
uv run robot --dryrun --variable PROJECT:dryrun ../../*/tests/quickstart.robot

# assert the READMEs and the harness still agree
uv run python docsync/check_readme_sync.py --all

# unit-test the doc-sync checker itself
uv run pytest docsync/tests -q
```

## When a suite fails

Open `results/<api>/log.html` — it shows every keyword with its arguments and the
captured HTTP response. The `diagrid dev run` output is captured to
`results/<api>/<api>-dev-run.log`; log-marker failures are usually clearest there.

Two failure shapes worth recognising:

- **A response body mismatch** is either a transcription error in
  `variables/quickstarts.py` or genuine drift between a README and its app. Check
  the README before changing the table.
- **A log marker timing out** usually means the wording changed in the app. The
  marker table records which markers are language-invariant and which are not;
  see the design spec's assertion matrix for why each is truncated where it is.

## Adding a language or API

1. Add its entries to every dict in `variables/quickstarts.py`, transcribed from the
   new README.
2. Add a tagged test case to the relevant suite calling the existing keyword.
3. Run `uv run python docsync/check_readme_sync.py --all` — it will tell you what you
   missed.
4. Add the language to the CI matrix in `.github/workflows/e2e-quickstarts.yml`, and a
   runtime-setup step for it.

## Limitations

- doc-sync is a string presence and equality check, not a proof of execution. It
  catches a README edit the suites have not followed; it does not guarantee every
  documented command is executed and asserted.
- The suites test only the documented flow. `DELETE /order/{id}` and
  `POST /workflow/terminate/{id}` exist in every implementation but are documented
  in no README, so they are untested. Documenting them brings them under test.
- Three of the four workflow READMEs never show the status response body, so the
  status assertion is 200-plus-non-empty for those, and stricter only for python.
```

- [ ] **Step 2: Verify every command in the README works**

Run each fenced command from the "Checks that need no Catalyst project" section:

```bash
cd tools/qs-tester
uv run robot --dryrun --variable PROJECT:dryrun ../../*/tests/quickstart.robot
uv run python docsync/check_readme_sync.py --all
uv run pytest docsync/tests -q
```

Expected: all three succeed. A README in a testing harness that documents a command that does not work is the same bug this whole harness exists to catch.

- [ ] **Step 3: Commit**

```bash
git add tools/qs-tester/README.md
git commit -m "docs: add qs-tester harness README"
```

---

## Task 12: Enable the schedule

**Files:**
- Modify: `.github/workflows/e2e-quickstarts.yml` (no change if the full matrix already passed)

- [ ] **Step 1: Confirm a full matrix run is green**

```bash
gh run list --workflow=e2e-quickstarts.yml --limit 5
```

Expected: the most recent full run (no `language` input) succeeded on all four legs. Do not proceed otherwise — enabling a schedule on a red workflow means a drift issue every morning that everyone learns to ignore.

- [ ] **Step 2: Confirm the deliberate-break checks were all done**

Verify each of these happened during Tasks 5–9, and redo any that did not:

| Check | Task | Proves |
|---|---|---|
| Broken state log marker fails the suite | 5, step 4 | state log assertions are not vacuous |
| Mis-scoped `subscription.yaml` fails the suite | 7, step 4 | pubsub delivery is genuinely verified |
| Edited README fails doc-sync | 9, step 6 | doc-sync catches drift |
| Nested SIGINT-ignoring children get killed | 2, step 4 | teardown cannot leak orphans |

A green suite proves nothing until each of these has failed on purpose once.

- [ ] **Step 3: Open the pull request**

```bash
gh pr create --title "Add end-to-end tests for the quickstarts" --body "$(cat <<'EOF'
Adds Robot Framework end-to-end tests for the workflow, state, pubsub and
invocation quickstarts in all four languages, run daily against ephemeral
Diagrid Catalyst projects.

Each test runs the commands its quickstart's README documents and asserts the
responses and log output that README promises. The READMEs are the source of
truth; `tools/qs-tester/docsync/check_readme_sync.py` keeps the two in sync and
runs on every PR without needing credentials.

Design: `docs/superpowers/specs/2026-07-28-quickstart-e2e-tests-design.md`
Plan: `docs/superpowers/plans/2026-07-28-quickstart-e2e-tests.md`

The schedule (05:00 UTC daily) is live on merge. A failure opens or comments on a
single issue labelled `e2e-failure`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: After merge, confirm the first scheduled run**

The next morning, check that the scheduled run fired and that no `qs-ci-*` projects were left behind:

```bash
gh run list --workflow=e2e-quickstarts.yml --limit 3
diagrid project list | grep qs-ci- || echo "no leaked projects"
```

Expected: a run triggered by `schedule`, and no leaked projects.

---

## Follow-up issues to file (not part of this plan)

The design spec's "Known issues" section lists drift found while designing. None is fixed by this plan; file them separately so the test PR stays reviewable:

1. `pubsub/python/publisher/main.py` catches `grpc.RpcError` without importing `grpc` — the error path raises `NameError` instead of returning 500.
2. `state/java` expects the KV store named `kvstore` while the other three expect `statestore`; CI provisions both to work around it.
3. `state/javascript` keys on `order<id>` where the other three key on the bare id.
4. `workflow/javascript` returns `instance_id` where the other three return `instanceId`.
5. `workflow/java` has no `workflow-quickstart.yaml`, unlike the other three.
6. Three of four workflow READMEs describe a status response body they never show; python's shows `"runtimeStatus":1` where the prose says "completed".
7. `test.rest` uses order ID `4` for state while the READMEs use `1`.
8. `DELETE /order/{id}` and `POST /workflow/terminate/{id}` are undocumented and therefore untested.
9. Log wording diverges across languages for the same operation (capital-S `Publish Successful` in .NET, `Invoke Successful. Response received` in java's invocation client, a missing colon in java's invocation server). Harmonising these would collapse the marker table to invariants only.

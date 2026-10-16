*** Comments ***
End-to-end test for the agents/langgraph quickstart (python only: this
quickstart has one implementation, unlike the canonical four-language APIs).

Mirrors agents/langgraph/README.md: "## Setup" installs, "## Run with Catalyst"
provisions and runs, "### 2. Trigger a Workflow" triggers. This README documents
no cleanup command, so deleting the project is infrastructure here. The second
test case covers "## Crash Recovery Test With Catalyst" (see CRASH_* in
variables/agents_langgraph.py).

The request loop below is the shape every agent-family suite uses, including ones
whose documented flow interleaves CLI commands with HTTP calls: a request may
carry `commands` to run first and a `log_marker` to wait for afterwards.

Run it:
  export DIAGRID_API_KEY=... OPENAI_API_KEY=...
  eval "$(bash tools/qs-tester/ci/project-name.sh agents-langgraph | grep '^PROJECT=')"
  bash tools/qs-tester/ci/login.sh
  cd tools/qs-tester
  uv run robot --variable PROJECT:$PROJECT --outputdir results/agents-langgraph \
    ../../agents/langgraph/tests/quickstart.robot
  bash ci/teardown-project.sh "$PROJECT"

*** Settings ***
Resource        ../../../tools/qs-tester/resources/catalyst.resource
Resource        ../../../tools/qs-tester/resources/quickstart.resource
# Imported twice on purpose, same as the canonical suites: `Variables` exposes
# the module-level names (@{REQUESTS}, @{READY_MARKERS}), `Library` exposes
# get_quickstart as a keyword. Neither import alone gives both.
Variables       ../../../tools/qs-tester/variables/agents_langgraph.py
Library         ../../../tools/qs-tester/variables/agents_langgraph.py
Library         Collections
Suite Setup     Should Not Be Empty    ${PROJECT}
...             msg=Pass --variable PROJECT:<catalyst-project-name>
Test Teardown   Clean Up Quickstart

*** Variables ***
${PROJECT}      ${EMPTY}

*** Test Cases ***
Python Langgraph Quickstart
    [Tags]    python    langgraph    agents
    ${qs}=      Get Quickstart
    ${log}=     Suite Log File    agents-langgraph    python

    # A missing model key must fail here, before a project is created, rather
    # than as a 401 from OpenAI several minutes later.
    FOR    ${secret}    IN    @{qs}[secrets]
        Require Env Var    ${secret}    agents/langgraph
    END

    Build Quickstart            ${qs}
    # README "## Run with Catalyst" steps 2-3, run verbatim.
    Run Documented Commands     ${qs}[setup]    ${PROJECT}    cwd=${qs}[dir]
    Start Quickstart            ${qs}    ${PROJECT}    ${log}

    Wait Until Apps Connected   ${qs}    ${log}
    # @{READY_MARKERS} and @{REQUESTS} come from the `Variables` import, NOT from
    # ${qs}, and that is deliberate: a --variablefile override replaces a variable
    # file's value but cannot touch what a Python keyword returned. Reading these
    # from ${qs} would make the mutation check run with the real markers, pass, and
    # prove nothing. One marker per app that announces itself.
    FOR    ${marker}    IN    @{READY_MARKERS}
        Wait Until Ready Marker    ${log}    ${marker}
    END
    Wait Until Apps Healthy     ${qs}

    # The three gates above are all satisfied by the local process: the tunnel is
    # up, uvicorn is serving, and the app answers its own health route. None of
    # them means Catalyst has attached, and a workflow call made before it has
    # HANGS — permanently, not transiently: the 2026-08-27 run died 120s into a
    # documented POST that never created an instance, and twelve retries over 181s
    # never recovered it. Gated on this marker the same POST answered in ~1s.
    # Read from ${qs}, not from an imported name, because unlike @{READY_MARKERS}
    # this is infrastructure and not an assertion: there is nothing here for a
    # mutation check to break.
    FOR    ${marker}    IN    @{qs}[catalyst_probe_markers]
        Wait Until Catalyst Attached    ${log}    ${marker}
    END

    # The documented calls, in documented order. README "### 2. Trigger a Workflow".
    # `commands` and `log_marker` are optional per request: a flow that interleaves
    # CLI and HTTP (mcp-auth grants a tool between two calls) expresses that here
    # rather than needing its own bespoke suite.
    # Every optional key is read with a default, so a request that needs none of
    # them stays a five-key dict instead of carrying explicit nulls.
    FOR    ${request}    IN    @{REQUESTS}
        # `Evaluate`, not `Get From Dictionary ... default=`: the default has to be an
        # empty SEQUENCE. A ${EMPTY} default is an empty string, and Run Documented
        # Commands would fail iterating it with "not list or list-like" for every
        # request that carries no commands, which is most of them.
        ${commands}=    Evaluate    $request.get('commands', ())
        Run Documented Commands    ${commands}    ${PROJECT}    cwd=${qs}[dir]
        ${field}=       Get From Dictionary    ${request}    field          default=${NONE}
        # POST-only on purpose: every documented agent trigger is a POST. A
        # documented GET belongs in `GET And Expect` from quickstart.resource, and
        # a suite that needs one should branch on ${request}[method] here.
        Should Be Equal    ${request}[method]    POST
        ...    msg=Only POST requests are handled here; use GET And Expect for a documented GET.
        POST And Expect Field    ${request}[port]    ${request}[path]    ${request}[payload]
        ...    ${request}[status]    ${field}
        ${marker}=      Get From Dictionary    ${request}    log_marker     default=${NONE}
        IF    $marker is not None
            Wait Until Log Contains    ${log}    ${marker}
        END
    END

Python Langgraph Crash Recovery
    [Documentation]    README "## Crash Recovery Test With Catalyst": "### 4" starts
    ...    the crash app, "### 5" runs under an id you own with kill_after_seconds,
    ...    "### 7" restarts, "### 8" collects the answer. The two-terminal
    ...    POST /crash/kill variant ("### 6") is in UNCOVERED in the data module.
    ...
    ...    langgraph is a graph with no model, so this asserts only on log markers
    ...    the nodes print and on framework-generated fields, and needs no key.
    ...
    ...    NOT YET RUN LIVE: no Catalyst project was available when this was written,
    ...    so only the dry run and doc-sync have passed.
    [Tags]    python    langgraph    agents    crash-recovery
    # The happy-path case's run file, connections and health probe belong to
    # main.py on 8005. This case runs crash_test.py on 8001, so override them.
    ${qs}=      Get Quickstart
    ${apps}=    Evaluate    [list(app) for app in $CRASH_CONNECTED_APPS]
    ${probes}=  Evaluate    [list(probe) for probe in $CRASH_HEALTH_PROBES]
    Set To Dictionary    ${qs}    run=${CRASH_RUN}    connected_apps=${apps}
    ...    health_probes=${probes}
    ${log}=     Suite Log File    agents-langgraph    python-crash

    Build Quickstart            ${qs}
    # README "## Run with Catalyst" steps 2-3. When the happy-path case ran first
    # the project and the agent already exist (this README documents no cleanup,
    # so its teardown leaves them), and these commands then fail as already-exists.
    # Only that failure is tolerated; anything else (auth, quota, bad flags) fails
    # the test. See `Run Setup Command Tolerating Existing`.
    #
    # This case's UNCOVERED entry for CRASH_RUN in the data module claims this case
    # runs that command. If this case is ever removed, that entry becomes a false
    # claim and must go with it (doc-sync will then demand a real decision).
    FOR    ${command}    IN    @{qs}[setup]
        Run Setup Command Tolerating Existing    ${command}    ${PROJECT}    ${qs}[dir]
    END
    Start Quickstart            ${qs}    ${PROJECT}    ${log}

    Wait Until Apps Connected   ${qs}    ${log}
    FOR    ${marker}    IN    @{READY_MARKERS}
        Wait Until Ready Marker    ${log}    ${marker}
    END
    Wait Until Apps Healthy     ${qs}

    # A workflow call made before Catalyst has attached hangs for good.
    FOR    ${marker}    IN    @{qs}[catalyst_probe_markers]
        Wait Until Catalyst Attached    ${log}    ${marker}
    END

    # A missing id is a 400 in the shared {id, result, message} shape. Checked here
    # because it needs a started app and a second start is expensive. It schedules
    # nothing, so it cannot disturb the crash below.
    ${empty}=   Create Dictionary
    ${bad}=     POST And Expect    ${CRASH_APP_PORT}    /crash/run    ${empty}    400
    FOR    ${key}    IN    id    result    message
        Dictionary Should Contain Key    ${bad}    ${key}
        ...    msg=400 body is missing "${key}": ${bad}
    END
    Should Be Equal    ${bad}[result]    ${NONE}
    Should Not Be Empty    ${bad}[message]

    # README "### 5", the kill_after_seconds variant. The process halts itself, so
    # this call never gets a response and its outcome proves nothing; the port check
    # below is the crash assertion.
    ${payload}=    Create Dictionary
    ...    id=${CRASH_ID}    topic=${CRASH_TOPIC}    kill_after_seconds=${KILL_AFTER_SECONDS}
    Run Keyword And Ignore Error
    ...    POST    http://localhost:${CRASH_APP_PORT}/crash/run    json=${payload}    timeout=120

    # Step 1 completed before the crash, so there is something to resume.
    Wait Until Log Contains     ${log}    ${STEP1_MARKER}          timeout=120s
    Wait Until Log Contains     ${log}    ${STEP2_ARMED_MARKER}    timeout=60s
    # The app halted itself for the documented reason, not something else.
    Wait Until Log Contains     ${log}    ${SELF_KILL_MARKER}      timeout=60s

    # The assertion that the process really died. Stop Process Tree below would
    # otherwise substitute for a kill that never fired. It also gates on the port
    # being free before the relaunch. The shared keyword is meaningful here only
    # because crash_test.py serves `GET /` with 200: a live app passes the GET, so
    # the keyword fails until the process is gone. (It would be vacuous for an app
    # whose GET / is a 404, which is why the dotnet suite uses a TCP check.)
    Wait Until Keyword Succeeds    30s    2s    App Port Is Closed    ${CRASH_APP_PORT}

    # The CLI parent is still up; take the tree down so the alias can be rebound.
    Run Keyword And Ignore Error    Stop Process Tree    apps

    # README "### 7. Restart the app": the same run command, nothing else.
    ${log_again}=    Suite Log File    agents-langgraph    python-crash-recovery
    Start Quickstart            ${qs}    ${PROJECT}    ${log_again}
    Wait Until Apps Connected   ${qs}    ${log_again}
    Wait Until Apps Healthy     ${qs}

    # "You do not have to send anything": Catalyst hands the run back on reconnect
    # and the interrupted node finishes on its own, about 10s after it restarts.
    Wait Until Log Contains     ${log_again}    ${STEP2_DONE_MARKER}    timeout=180s

    # README "### 8. Collect the answer": the same call with the same id attaches to
    # the finished run. 200, `result` set, `message` null.
    FOR    ${request}    IN    @{CRASH_REQUESTS}
        Should Be Equal    ${request}[method]    POST
        ...    msg=Only POST requests are handled here; use GET And Expect for a documented GET.
        ${body}=    POST And Expect Field
        ...    ${request}[port]    ${request}[path]    ${request}[payload]
        ...    ${request}[status]    ${request}[field]
        Should Not Be Equal    ${body}[result]    ${NONE}
        ...    msg=Re-issued /crash/run returned no result
        Should Be Equal    ${body}[message]    ${NONE}
        ...    msg=A 200 must carry no attach instruction
        Wait Until Log Contains    ${log_again}    ${request}[log_marker]    timeout=30s
    END

    # "check_venues is not re-executed": its STEP 1 line must not appear a second
    # time in the recovery run's log.
    Log Should Not Contain    ${log_again}    ${STEP1_MARKER}

*** Keywords ***
Run Setup Command Tolerating Existing
    [Documentation]    Run one documented setup command; tolerate ONLY a failure
    ...    that says the thing already exists, fail on anything else.
    ...
    ...    ASSUMED AND UNVERIFIED: the diagrid CLI's wording for an existing project
    ...    or agent is not recorded anywhere in this repo (ci scripts, resources,
    ...    READMEs, other suites), so the match below is the narrowest one that can
    ...    be justified: the case-insensitive phrase "already exist" in the failure
    ...    text (covers "already exists" and "already exist"). If the CLI words it
    ...    differently, a full run fails loudly here on the second case instead of
    ...    silently passing; fix the pattern from the real message, which this
    ...    keyword puts in the failure output.
    [Arguments]    ${command}    ${project}    ${cwd}
    ${status}    ${message}=    Run Keyword And Ignore Error
    ...    Run Documented Commands    ${{[$command]}}    ${project}    cwd=${cwd}
    IF    '${status}' == 'PASS'    RETURN
    ${lowered}=    Convert To Lower Case    ${message}
    Should Contain    ${lowered}    already exist
    ...    msg=Setup command failed with something other than "already exists": ${message}
    Log    Tolerated, already provisioned: ${command}    console=True

Clean Up Quickstart
    [Documentation]    Stop the apps, then run whatever cleanup the README
    ...    documents. `Stop Quickstart` also calls `diagrid dev stop`, which
    ...    releases the local app connections.
    ...
    ...    langgraph's TEARDOWN is empty, because its README documents no cleanup
    ...    command, so the loop is a no-op here and ci/teardown-project.sh deletes
    ...    the project. The call stays because other agent quickstarts do document
    ...    deletion (agents/microsoft-dotnet documents `diagrid project delete`),
    ...    and this keyword is the template they copy.
    Run Keyword And Ignore Error    Stop Quickstart    ${PROJECT}
    ${qs}=    Get Quickstart
    Run Keyword And Ignore Error
    ...    Run Documented Commands    ${qs}[teardown]    ${PROJECT}

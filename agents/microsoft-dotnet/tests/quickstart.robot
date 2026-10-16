*** Comments ***
End-to-end test for the agents/microsoft-dotnet quickstart (csharp only: this
quickstart has one implementation, unlike the canonical four-language APIs).

Mirrors agents/microsoft-dotnet/README.md: "## Setup" installs, "## Run with
Catalyst" provisions and runs, "### 2. Trigger the Agent" triggers, and
"## Clean Up" documents a project delete that prompts, so it is in UNCOVERED and
ci/teardown-project.sh deletes the project. The
second test case covers "### 3. Crash Recovery with Catalyst" (see CRASH_* names
in variables/agents_microsoft_dotnet.py); the two-terminal POST /crash/kill
variant is in UNCOVERED there.

The request loop below is the shape every agent-family suite uses, including ones
whose documented flow interleaves CLI commands with HTTP calls: a request may
carry `commands` to run first and a `log_marker` to wait for afterwards.

Run it:
  export DIAGRID_API_KEY=... OPENAI_API_KEY=...
  eval "$(bash tools/qs-tester/ci/project-name.sh agents-microsoft-dotnet | grep '^PROJECT=')"
  bash tools/qs-tester/ci/login.sh
  cd tools/qs-tester
  uv run robot --variable PROJECT:$PROJECT --outputdir results/agents-microsoft-dotnet \
    ../../agents/microsoft-dotnet/tests/quickstart.robot
  bash ci/teardown-project.sh "$PROJECT"

*** Settings ***
Resource        ../../../tools/qs-tester/resources/catalyst.resource
Resource        ../../../tools/qs-tester/resources/quickstart.resource
# Imported twice on purpose, same as the canonical suites: `Variables` exposes
# the module-level names (@{REQUESTS}, @{READY_MARKERS}), `Library` exposes
# get_quickstart as a keyword. Neither import alone gives both.
Variables       ../../../tools/qs-tester/variables/agents_microsoft_dotnet.py
Library         ../../../tools/qs-tester/variables/agents_microsoft_dotnet.py
Library         Collections
Suite Setup     Should Not Be Empty    ${PROJECT}
...             msg=Pass --variable PROJECT:<catalyst-project-name>
Test Teardown   Clean Up Quickstart

*** Variables ***
${PROJECT}      ${EMPTY}
# Wait before the crash case runs the app ID again after the first case's `dev stop`.
# A guess, not a measured value: see the comment in the crash case.
${APP_CONNECTION_SETTLE}    20s

*** Test Cases ***
Csharp Microsoft-Dotnet Quickstart
    [Tags]    csharp    microsoft-dotnet    agents
    ${qs}=      Get Quickstart
    ${log}=     Suite Log File    agents-microsoft-dotnet    csharp

    # A missing model key must fail here, before a project is created, rather
    # than as a 401 from OpenAI several minutes later.
    FOR    ${secret}    IN    @{qs}[secrets]
        Require Env Var    ${secret}    agents/microsoft-dotnet
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
    # HEALTH_PROBES is empty: this app serves no GET route (Program.cs registers
    # only `app.MapPost("/run")`), so `Wait Until Apps Healthy` is a no-op here.
    # The connection gate above plus the readiness marker are the only readiness
    # signals for this suite. Do not "fix" this by adding a `/` probe.
    Wait Until Apps Healthy     ${qs}

    # The documented marker above proves Dapr connectivity, not that the HTTP
    # port is open — Kestrel binds after it. See SERVING_MARKER in the data
    # module for the ordering this closes.
    Wait Until Log Contains     ${log}    ${SERVING_MARKER}    timeout=180s

    # CATALYST_PROBE_MARKERS is empty for this suite, so this loop is a no-op. It
    # stays because the gap it guards is real here too: every gate above is
    # satisfied by the local process, and a workflow call made before Catalyst has
    # attached hangs unrecoverably (measured on agents/langgraph, 2026-08-27).
    # Giving this suite the gate is a data change in its variables module, not a
    # change here — see CATALYST_PROBE_MARKERS there for what has to be observed
    # first.
    FOR    ${marker}    IN    @{qs}[catalyst_probe_markers]
        Wait Until Catalyst Attached    ${log}    ${marker}
    END

    # The documented calls, in documented order. README "### 2. Trigger the Agent".
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

Csharp Microsoft-Dotnet Crash Recovery
    [Documentation]    README "### 3. Crash Recovery with Catalyst": run under an id
    ...    you own with kill_after_seconds, restart with the same run command, then
    ...    re-issue the same request to collect the answer. The two-terminal
    ...    POST /crash/kill variant is in UNCOVERED in the data module.
    ...
    ...    The quickstart ships a canned offline model, so this asserts only on log
    ...    markers the tools print and on framework-generated fields, and needs no key.
    ...
    ...    Run live on 2026-10-16: PASS 2/2 (happy path 58s, this case 121s), canned
    ...    offline model, no key. This case first failed at `project create` ("already
    ...    exists") because the README's `diagrid project delete` stops at an
    ...    interactive Y/N prompt and never deleted the project; it passed after the
    ...    case decided from `diagrid project get` (skip SETUP, wait
    ...    APP_CONNECTION_SETTLE). The 20s settle wait was not shown to be necessary
    ...    for this app. No mutation check has been run (ci/check_mutation.py) for
    ...    this case.
    [Tags]    csharp    microsoft-dotnet    agents    crash-recovery
    ${qs}=      Get Quickstart
    ${log}=     Suite Log File    agents-microsoft-dotnet    csharp-crash

    # The UNCOVERED entry for POST /crash/kill in the data module claims this case
    # sends kill_after_seconds instead. If this case is removed, that entry becomes
    # a false claim and must go with it.
    #
    # `dotnet build` is incremental and near-instant when the first case has already
    # built.
    #
    # The project survives the first case BY DESIGN: TEARDOWN is empty (the
    # documented `diagrid project delete` prompts for confirmation, so it is in
    # UNCOVERED) and ci/teardown-project.sh deletes the project after the suite.
    # So re-running SETUP here would fail with 'A project named "..." already
    # exists'. Decide from state, the way the langgraph suite does: if
    # `diagrid project get` succeeds, skip SETUP; otherwise run it and let any
    # failure fail the test.
    #
    # In the normal path the first case also ran `diagrid dev stop --id` moments
    # ago, and a `dev run` for the same app ID started within ~1-2s of that fails
    # with "local app connection not found with the given id" (reproduced for
    # langgraph, not yet for this app), so wait out the release first.
    Build Quickstart            ${qs}
    ${exists}=    Project Exists    ${PROJECT}
    IF    not ${exists}
        Run Documented Commands     ${qs}[setup]    ${PROJECT}    cwd=${qs}[dir]
    ELSE
        Log    Project ${PROJECT} already exists, skipping SETUP    console=True
        Wait For Released App Connection
    END
    Start Quickstart            ${qs}    ${PROJECT}    ${log}

    Wait Until Apps Connected   ${qs}    ${log}
    FOR    ${marker}    IN    @{READY_MARKERS}
        Wait Until Ready Marker    ${log}    ${marker}
    END
    Wait Until Apps Healthy     ${qs}
    # Kestrel binds after the Dapr marker; see SERVING_MARKER in the data module.
    Wait Until Log Contains     ${log}    ${SERVING_MARKER}    timeout=180s
    FOR    ${marker}    IN    @{qs}[catalyst_probe_markers]
        Wait Until Catalyst Attached    ${log}    ${marker}
    END

    # A missing id is a 400 in the shared {id, result, message} shape. Checked here
    # because it needs a started app and a second start is expensive. It schedules
    # nothing, so it cannot disturb the crash below.
    ${empty}=   Create Dictionary
    ${bad}=     POST And Expect    ${APP_PORT}    /crash/run    ${empty}    400
    FOR    ${key}    IN    id    result    message
        Dictionary Should Contain Key    ${bad}    ${key}
        ...    msg=400 body is missing "${key}": ${bad}
    END
    Should Be Equal    ${bad}[result]    ${NONE}
    Should Not Be Empty    ${bad}[message]

    # README "### 3", the kill_after_seconds variant. The process halts itself, so
    # this call never gets a response and its outcome proves nothing; the port check
    # below is the crash assertion.
    ${payload}=    Create Dictionary
    ...    id=${CRASH_ID}    prompt=${CRASH_PROMPT}    kill_after_seconds=${KILL_AFTER_SECONDS}
    Run Keyword And Ignore Error
    ...    POST    http://localhost:${APP_PORT}/crash/run    json=${payload}    timeout=120

    # Tool 1 completed before the crash, so there is something to resume.
    Wait Until Log Contains     ${log}    ${STEP1_MARKER}          timeout=120s
    Wait Until Log Contains     ${log}    ${STEP2_ARMED_MARKER}    timeout=60s
    # The app halted itself for the documented reason, not something else.
    Wait Until Log Contains     ${log}    ${SELF_KILL_MARKER}      timeout=60s

    # The assertion that the process really died, so Stop Process Tree below cannot
    # substitute for a kill that never fired. It also gates on the port being free
    # before the relaunch. Not the shared `App Port Is Closed`: that does GET / and
    # passes on any non-2xx, and this app maps no GET route, so a live app answers
    # 404 and the shared keyword would pass at once. `Port Refuses Connections` only
    # succeeds on a refused TCP connect.
    Wait Until Keyword Succeeds    30s    2s    Port Refuses Connections    ${APP_PORT}

    # Let the first `diagrid dev run` finish shutting itself down after the crash. Signalling it
    # mid-shutdown interrupted its cleanup and left ~/.diagrid/tuns/<project>:<app id> behind, so the
    # restart failed with "file ... already exists for App ID" (seen on the first live mastra run).
    # Stop Process Tree below then only mops up anything still alive.
    Wait For Process    apps    timeout=30s    on_timeout=continue
    Run Keyword And Ignore Error    Stop Process Tree    apps

    # README "### 3", "Restart the app": the same run command, nothing else.
    ${log_again}=    Suite Log File    agents-microsoft-dotnet    csharp-crash-recovery
    Start Quickstart            ${qs}    ${PROJECT}    ${log_again}
    Wait Until Apps Connected   ${qs}    ${log_again}
    Wait Until Log Contains     ${log_again}    ${SERVING_MARKER}    timeout=180s

    # "You do not have to send anything": Catalyst hands the run back on reconnect
    # and the interrupted tool finishes on its own, about 10s after it restarts.
    Wait Until Log Contains     ${log_again}    ${STEP2_DONE_MARKER}    timeout=180s

    # README "### 3", "Collect the answer": the same call with the same id attaches
    # to the finished run. 200, `result` set, `message` null.
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

    # "TOOL 1 does not appear again": its line must not be in the recovery run's log.
    Log Should Not Contain    ${log_again}    ${STEP1_MARKER}

*** Keywords ***
Project Exists
    [Documentation]    True when `diagrid project get ${project}` exits 0, the same
    ...    test ci/teardown-project.sh uses. A non-zero exit counts as "does not
    ...    exist", so a failed lookup (auth, network) falls through to running SETUP,
    ...    where any failure fails the test. No dependence on CLI message wording.
    ...    (Same keyword as in agents/langgraph/tests/quickstart.robot.)
    [Arguments]    ${project}
    ${result}=    Run Process    diagrid project get ${project}    shell=True
    ...    stderr=STDOUT    timeout=120s
    RETURN    ${result.rc == 0}

Wait For Released App Connection
    [Documentation]    Sleep ${APP_CONNECTION_SETTLE} so the app connection released
    ...    by the previous case's `diagrid dev stop --id` is really gone before the
    ...    same app ID is run again. A fixed, unmeasured wait: tune it with
    ...    --variable APP_CONNECTION_SETTLE:<seconds>s. (Same keyword as in
    ...    agents/langgraph/tests/quickstart.robot.)
    Log    Waiting ${APP_CONNECTION_SETTLE} for the previous app connection to be released    console=True
    Sleep    ${APP_CONNECTION_SETTLE}

Port Refuses Connections
    [Documentation]    Succeed only when a TCP connect to ${port} is REFUSED, which is
    ...    what a port with no listener does. A timeout or any other error fails, so
    ...    the gate cannot pass on something other than a dead process.
    [Arguments]    ${port}
    ${status}    ${message}=    Run Keyword And Ignore Error
    ...    Evaluate    socket.create_connection(('localhost', ${port}), timeout=3).close()    modules=socket
    Should Be Equal    ${status}    FAIL
    ...    msg=Port ${port} accepted a connection, so the app did not die
    Should Contain    ${message}    ConnectionRefusedError
    ...    msg=Port ${port} did not refuse the connection (needed a refusal, got: ${message})

Clean Up Quickstart
    [Documentation]    Stop the apps, then run whatever cleanup the README
    ...    documents. `Stop Quickstart` also calls `diagrid dev stop`, which
    ...    releases the local app connections.
    ...
    ...    microsoft-dotnet's TEARDOWN is empty: the README's `diagrid project
    ...    delete` ("## Clean Up") stops at an interactive prompt, so it is in
    ...    UNCOVERED and ci/teardown-project.sh deletes the ephemeral project
    ...    (with --yes). `Run Keyword And Ignore Error` guards both calls:
    ...    `Stop Process Tree` is not idempotent against a process that has
    ...    already exited, and a failed stop must not prevent whatever cleanup
    ...    TEARDOWN holds from running.
    Run Keyword And Ignore Error    Stop Quickstart    ${PROJECT}
    ${qs}=    Get Quickstart
    Run Keyword And Ignore Error
    ...    Run Documented Commands    ${qs}[teardown]    ${PROJECT}

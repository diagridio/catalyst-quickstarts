*** Comments ***
End-to-end test for the agents/microsoft-dotnet quickstart (csharp only: this
quickstart has one implementation, unlike the canonical four-language APIs).

Mirrors agents/microsoft-dotnet/README.md: "## Setup" installs, "## Run with
Catalyst" provisions and runs, "### 2. Trigger the Agent" triggers, and
"## Clean Up" documents the project delete this suite's teardown runs. The
crash-recovery flow ("### 3. Crash Recovery with Catalyst") is deliberately
absent; see UNCOVERED in variables/agents_microsoft_dotnet.py for why.

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
        # This quickstart's documented trigger kills the app mid-request — README
        # "### 2. Trigger the Agent": "Call `step_two_compare` — crashes before
        # completing (process exits)", and "The process exits — this is expected".
        # So there is no status code to assert here and `expect` says so, rather
        # than the suite carrying a status the app can never return. A request
        # without `expect` takes the ordinary path, so this stays the same shared
        # loop the other agent suites use.
        ${expect}=      Get From Dictionary    ${request}    expect    default=${NONE}
        IF    '${expect}' == 'connection-dropped'
            POST And Expect The App To Exit
            ...    ${request}[port]    ${request}[path]    ${request}[payload]
        ELSE
            POST And Expect Field    ${request}[port]    ${request}[path]    ${request}[payload]
            ...    ${request}[status]    ${field}
        END
        ${marker}=      Get From Dictionary    ${request}    log_marker     default=${NONE}
        IF    $marker is not None
            Wait Until Log Contains    ${log}    ${marker}
        END
    END

*** Keywords ***
Clean Up Quickstart
    [Documentation]    Stop the apps, then run whatever cleanup the README
    ...    documents. `Stop Quickstart` also calls `diagrid dev stop`, which
    ...    releases the local app connections.
    ...
    ...    microsoft-dotnet's TEARDOWN documents `diagrid project delete`
    ...    ("## Clean Up"), so this loop really deletes the ephemeral project.
    ...    `Run Keyword And Ignore Error` guards both calls: `Stop Process Tree`
    ...    is not idempotent against a process that has already exited, and a
    ...    failed stop must not prevent the documented delete from running.
    Run Keyword And Ignore Error    Stop Quickstart    ${PROJECT}
    ${qs}=    Get Quickstart
    Run Keyword And Ignore Error
    ...    Run Documented Commands    ${qs}[teardown]    ${PROJECT}

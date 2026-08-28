*** Comments ***
End-to-end test for the agents/langgraph quickstart (python only: this
quickstart has one implementation, unlike the canonical four-language APIs).

Mirrors agents/langgraph/README.md: "## Setup" installs, "## Run with Catalyst"
provisions and runs, "### 2. Trigger a Workflow" triggers. This README documents
no cleanup command, so deleting the project is infrastructure here. The
crash-recovery flow is deliberately absent; see UNCOVERED in
variables/agents_langgraph.py for why.

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

*** Keywords ***
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

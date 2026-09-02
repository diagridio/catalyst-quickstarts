*** Comments ***
End-to-end test for the agents/spring-ai/event-planner quickstart (java only:
this quickstart has one implementation).

Mirrors agents/spring-ai/event-planner/README.md: "## Setup" installs, "### 1.
Deploy and Run" provisions and runs, "### 2. Trigger the Agent" triggers, and
"## Clean Up" documents the project delete this suite's teardown runs. The
crash-recovery flow ("## Crash Recovery") is deliberately absent; see
UNCOVERED in variables/agents_spring_ai_event_planner.py for why.

The request loop below is the shape every agent-family suite uses, including ones
whose documented flow interleaves CLI commands with HTTP calls: a request may
carry `commands` to run first and a `log_marker` to wait for afterwards.

Run it:
  export DIAGRID_API_KEY=...
  eval "$(bash tools/qs-tester/ci/project-name.sh agents-spring-ai-event-planner | grep '^PROJECT=')"
  bash tools/qs-tester/ci/login.sh
  cd tools/qs-tester
  uv run robot --variable PROJECT:$PROJECT --outputdir results/agents-spring-ai-event-planner \
    ../../agents/spring-ai/event-planner/tests/quickstart.robot
  bash ci/teardown-project.sh "$PROJECT"

*** Settings ***
# One level deeper than the other agent suites: this quickstart lives at
# agents/<group>/<name>/tests/quickstart.robot, three directory levels below
# agents/, so it takes an extra ../ to reach tools/qs-tester.
Resource        ../../../../tools/qs-tester/resources/catalyst.resource
Resource        ../../../../tools/qs-tester/resources/quickstart.resource
# Imported twice on purpose, same as the canonical suites: `Variables` exposes
# the module-level names (@{REQUESTS}, @{READY_MARKERS}), `Library` exposes
# get_quickstart as a keyword. Neither import alone gives both.
Variables       ../../../../tools/qs-tester/variables/agents_spring_ai_event_planner.py
Library         ../../../../tools/qs-tester/variables/agents_spring_ai_event_planner.py
Library         Collections
Suite Setup     Should Not Be Empty    ${PROJECT}
...             msg=Pass --variable PROJECT:<catalyst-project-name>
Test Teardown   Clean Up Quickstart

*** Variables ***
${PROJECT}      ${EMPTY}

*** Test Cases ***
Java Spring-Ai-Event-Planner Quickstart
    [Tags]    java    spring-ai-event-planner    agents
    ${qs}=      Get Quickstart
    ${log}=     Suite Log File    agents-spring-ai-event-planner    java

    # Empty for this quickstart (canned offline model), but kept so that adding a
    # secret to the data module cannot silently skip the check.
    FOR    ${secret}    IN    @{qs}[secrets]
        Require Env Var    ${secret}    agents/spring-ai/event-planner
    END

    Build Quickstart            ${qs}
    # README "### 1. Deploy and Run", run verbatim.
    Run Documented Commands     ${qs}[setup]    ${PROJECT}    cwd=${qs}[dir]
    Start Quickstart            ${qs}    ${PROJECT}    ${log}

    Wait Until Apps Connected   ${qs}    ${log}
    # @{READY_MARKERS} and @{REQUESTS} come from the `Variables` import, NOT from
    # ${qs}, and that is deliberate: a --variablefile override replaces a variable
    # file's value but cannot touch what a Python keyword returned. Reading these
    # from ${qs} would make the mutation check run with the real markers, pass, and
    # prove nothing.
    #
    # Both READY_MARKERS and HEALTH_PROBES are empty for this quickstart: the
    # README documents no readiness wording, and the app exposes no GET route to
    # probe. The two FOR loops below are therefore no-ops by design, not an
    # oversight — `Wait Until Apps Connected` above is the ONLY readiness gate
    # this suite has.
    FOR    ${marker}    IN    @{READY_MARKERS}
        Wait Until Ready Marker    ${log}    ${marker}
    END
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
    ...    spring-ai/event-planner's TEARDOWN documents `diagrid project delete`
    ...    ("## Clean Up"), so this loop really deletes the ephemeral project.
    ...    `Run Keyword And Ignore Error` guards both calls: `Stop Process Tree`
    ...    is not idempotent against a process that has already exited, and a
    ...    failed stop must not prevent the documented delete from running.
    Run Keyword And Ignore Error    Stop Quickstart    ${PROJECT}
    ${qs}=    Get Quickstart
    Run Keyword And Ignore Error
    ...    Run Documented Commands    ${qs}[teardown]    ${PROJECT}

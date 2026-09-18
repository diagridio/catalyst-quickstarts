*** Comments ***
End-to-end test for the agents/microsoft-dotnet/enterprise-identity quickstart
(csharp only: this quickstart is the C# port of agents/langgraph/enterprise-identity,
and each port has its own suite).

Mirrors agents/microsoft-dotnet/enterprise-identity/README.md: "## Setup" builds,
"## Run with Catalyst" provisions and runs, "### 4. See It Fail Closed" is the pair
of documented requests this suite asserts. This README documents no cleanup
command, so deleting the project is infrastructure here.

WHAT THIS SUITE PROVES, precisely: the documented build and provisioning commands
succeed, both apps connect through the dev tunnel, Kestrel serves on the
documented port, and an unauthenticated request to either documented route is
refused 401 with the exact body `{"error": "oauth.missing_token"}` -- the shipped
middleware's missing-token path (Diagrid.AI.Identity 1.2.0, `WriteErrorAsync` in
OAuthMiddleware.cs).

WHAT IT DOES NOT PROVE: that an authenticated request succeeds, or that a
verified identity reaches the app's handler. No keyword here takes headers and
nothing here can mint a token dataplane Sentry signed, so both documented
`diagrid call invoke` calls are in UNCOVERED. Do not add an assertion that
implies otherwise. The OUTBOUND leg (on-behalf-of to the CRM's MCP tool) happens
only on an authenticated call, so it is out of this suite's reach for the same
reason -- do not add an assertion implying the CRM received a delegated JWT.
Those gaps are covered instead by
agents/microsoft-dotnet/enterprise-identity/unit-tests, which stands the identity
plane up in-process and asserts the 200, the 403, the expired 401 and the subject
substitution.

There is no separate SERVING_MARKER gate here, unlike the agents/microsoft-dotnet
suite next door. That suite needs one because the marker its README documents is
the Dapr connectivity line, which Kestrel logs BEFORE it binds the port. This app
registers no Dapr client at all, so it never prints that line: the marker its
README documents IS Kestrel's `Now listening on`, so READY_MARKERS is already the
serving gate. See READY_MARKERS in the data module.

The request loop below is the shape every agent-family suite uses, with the
GET/POST branch the python sibling's suite introduced: it branches on
${request}[method], because the README's primary fail-closed example is a GET.

Run it:
  export DIAGRID_API_KEY=...
  eval "$(bash tools/qs-tester/ci/project-name.sh agents-ei-csharp | grep '^PROJECT=')"
  bash tools/qs-tester/ci/login.sh
  cd tools/qs-tester
  uv run robot --variable PROJECT:$PROJECT --outputdir results/agents-enterprise-identity-csharp \
    ../../agents/microsoft-dotnet/enterprise-identity/tests/quickstart.robot
  bash ci/teardown-project.sh "$PROJECT"

*** Settings ***
# Four levels up: this quickstart lives at
# agents/microsoft-dotnet/enterprise-identity/tests/, one directory level below
# agents/microsoft-dotnet.
Resource        ../../../../tools/qs-tester/resources/catalyst.resource
Resource        ../../../../tools/qs-tester/resources/quickstart.resource
# Imported twice on purpose, same as every other suite: `Variables` exposes the
# module-level names (@{REQUESTS}, @{READY_MARKERS}), `Library` exposes
# get_quickstart as a keyword. Neither import alone gives both.
Variables       ../../../../tools/qs-tester/variables/agents_enterprise_identity_csharp.py
Library         ../../../../tools/qs-tester/variables/agents_enterprise_identity_csharp.py
Library         Collections
Suite Setup     Should Not Be Empty    ${PROJECT}
...             msg=Pass --variable PROJECT:<catalyst-project-name>
Test Teardown   Clean Up Quickstart

*** Variables ***
${PROJECT}      ${EMPTY}

*** Test Cases ***
Csharp Microsoft Agent Framework Identity Quickstart
    [Tags]    csharp    enterprise-identity    agents
    ${qs}=      Get Quickstart
    ${log}=     Suite Log File    agents-enterprise-identity-csharp    csharp

    # Empty for this quickstart -- it ships a canned offline model and both
    # requests are refused before the agent runs -- but kept so that adding a
    # secret to the data module cannot silently skip the check.
    FOR    ${secret}    IN    @{qs}[secrets]
        Require Env Var    ${secret}    agents/microsoft-dotnet/enterprise-identity
    END

    Build Quickstart            ${qs}
    # README "## Run with Catalyst" step 1, items 2-3, run verbatim.
    Run Documented Commands     ${qs}[setup]    ${PROJECT}    cwd=${qs}[dir]
    Start Quickstart            ${qs}    ${PROJECT}    ${log}

    Wait Until Apps Connected   ${qs}    ${log}
    # @{READY_MARKERS} and @{REQUESTS} come from the `Variables` import, NOT from
    # ${qs}, and that is deliberate: a --variablefile override replaces a variable
    # file's value but cannot touch what a Python keyword returned. Reading these
    # from ${qs} would make the mutation check run with the real markers, pass,
    # and prove nothing.
    FOR    ${marker}    IN    @{READY_MARKERS}
        Wait Until Ready Marker    ${log}    ${marker}
    END
    # HEALTH_PROBES is empty for this suite and this loop is a no-op. Not an
    # oversight: with RequireAuth=true the middleware sits ahead of every route
    # and answers 401 on all of them, and the shipped OAuthConfig has no path
    # exclusion, so no path can produce the 200 this keyword polls for. That is
    # also why the quickstart exposes no health route and why its dev config sets
    # enableAppHealthCheck: false. See HEALTH_PROBES in the data module.
    Wait Until Apps Healthy     ${qs}

    # CATALYST_PROBE_MARKERS is empty, so this loop is a no-op too. Unlike the
    # other agent suites that is a decision, not just "unobserved": the gate
    # guards the window in which a WORKFLOW call hangs unrecoverably, and this
    # quickstart starts no workflow -- both requests are refused by the
    # middleware before any Dapr call happens. The loop stays so that filling the
    # marker in later is a data change in the variables module, not a change here.
    FOR    ${marker}    IN    @{qs}[catalyst_probe_markers]
        Wait Until Catalyst Attached    ${log}    ${marker}
    END

    # The documented calls, in documented order. README "### 4. See It Fail
    # Closed". Two entries, both the negative case: see REQUESTS in the data
    # module for why the authenticated calls are not here.
    FOR    ${request}    IN    @{REQUESTS}
        # `Evaluate`, not `Get From Dictionary ... default=`: the default has to
        # be an empty SEQUENCE. A ${EMPTY} default is an empty string, and Run
        # Documented Commands would fail iterating it with "not list or
        # list-like" for every request that carries no commands.
        ${commands}=    Evaluate    $request.get('commands', ())
        Run Documented Commands    ${commands}    ${PROJECT}    cwd=${qs}[dir]
        # `body` is the EXACT expected response body, which is assertable here
        # because a 401 from the middleware carries no model output; `field` is
        # the weaker presence check the other agent suites need for responses
        # that do. Both are optional, and no request in this module uses `field`.
        ${body}=        Get From Dictionary    ${request}    body           default=${NONE}
        ${field}=       Get From Dictionary    ${request}    field          default=${NONE}
        # This suite's README documents a GET, so it branches instead of
        # asserting POST. An unrecognised method fails loudly rather than being
        # skipped: a request the loop quietly ignores is coverage that reads as
        # green and asserts nothing.
        IF    '${request}[method]' == 'GET'
            GET And Expect    ${request}[port]    ${request}[path]
            ...    ${request}[status]    ${body}
        ELSE IF    '${request}[method]' == 'POST' and $body is not None
            POST And Expect    ${request}[port]    ${request}[path]    ${request}[payload]
            ...    ${request}[status]    ${body}
        ELSE IF    '${request}[method]' == 'POST'
            POST And Expect Field    ${request}[port]    ${request}[path]    ${request}[payload]
            ...    ${request}[status]    ${field}
        ELSE
            Fail    msg=Unhandled documented method '${request}[method]' for ${request}[path]. Add a branch here rather than leaving the request unasserted.
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
    ...    releases the local app connections -- both of them here, since this
    ...    quickstart runs two apps.
    ...
    ...    `Run Keyword And Ignore Error` guards both calls: `Stop Process Tree`
    ...    is not idempotent against a process that has already exited, and a
    ...    failed stop must not prevent the documented cleanup from running.
    ...
    ...    This quickstart's TEARDOWN is empty, because its README documents no
    ...    cleanup command, so the second call is a no-op here and
    ...    ci/teardown-project.sh deletes the project. The call stays because
    ...    this keyword is the template the other agent suites copy.
    Run Keyword And Ignore Error    Stop Quickstart    ${PROJECT}
    ${qs}=    Get Quickstart
    Run Keyword And Ignore Error
    ...    Run Documented Commands    ${qs}[teardown]    ${PROJECT}

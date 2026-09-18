*** Comments ***
End-to-end test for the agents/spring-ai/enterprise-identity quickstart (java
only: this quickstart has one implementation).

Mirrors agents/spring-ai/enterprise-identity/README.md: "## Setup" installs,
"## Run with Catalyst" provisions and runs, "### 4. See It Fail Closed" is the
pair of documented requests this suite asserts. This README documents no cleanup
command -- like the Python quickstart it was ported from, and unlike the other
two agents/spring-ai suites -- so deleting the project is infrastructure here.

WHAT THIS SUITE PROVES, precisely: the documented install and provisioning
commands succeed, both apps connect through the dev tunnel, the canned offline
model is the one in play, Tomcat serves on the documented port, and an
unauthenticated request to either documented route is refused 401 with the exact
body `{"error": "oauth.missing_token"}` -- the shipped filter's missing-token
path (diagrid-ai-identity 0.3.0, OAuthErrorCodes.MISSING_TOKEN).

WHAT IT DOES NOT PROVE: that an authenticated request succeeds, or that a
verified identity reaches the app's handler. No keyword here takes headers and
nothing here can mint a token dataplane Sentry signed, so both documented
`diagrid call invoke` calls are in UNCOVERED. Those two outcomes -- the 200 and
the 403 -- are covered instead by the quickstart's own unit tests, which stand the
identity plane up in-process
(agents/spring-ai/enterprise-identity/identity-agent/src/test/java, run by
.github/workflows/agents_enterprise_identity_java.yaml). Do not add an assertion
here that implies otherwise.

The OUTBOUND leg (on-behalf-of to a downstream MCP tool) is documented by the
README and implemented by CatalystMcpClient, but nothing here observes it: it
starts with a credential-bearing request this harness cannot make. Do not add an
assertion implying a downstream MCP server receives a delegated JWT.

The request loop below is the shape every agent-family suite uses, with one
addition the Python enterprise-identity suite was first to need: it branches on
${request}[method], because the README's primary fail-closed example is a GET.
The other agents/spring-ai suites' POST-only guard says exactly this ("use GET
And Expect for a documented GET").

Run it:
  export DIAGRID_API_KEY=...
  eval "$(bash tools/qs-tester/ci/project-name.sh agents-spring-ai-identity | grep '^PROJECT=')"
  bash tools/qs-tester/ci/login.sh
  cd tools/qs-tester
  uv run robot --variable PROJECT:$PROJECT --outputdir results/agents-spring-ai-identity \
    ../../agents/spring-ai/enterprise-identity/tests/quickstart.robot
  bash ci/teardown-project.sh "$PROJECT"

*** Settings ***
# One level deeper than the canonical agent suites: this quickstart lives at
# agents/<group>/<name>/tests/quickstart.robot, three directory levels below
# agents/, so it takes an extra ../ to reach tools/qs-tester. Same as the
# event-planner and crash-recovery siblings.
Resource        ../../../../tools/qs-tester/resources/catalyst.resource
Resource        ../../../../tools/qs-tester/resources/quickstart.resource
# Imported twice on purpose, same as every other suite: `Variables` exposes the
# module-level names (@{REQUESTS}, @{READY_MARKERS}, ${SERVING_MARKER},
# ${OFFLINE_MODEL_MARKER}), `Library` exposes get_quickstart as a keyword.
# Neither import alone gives both.
Variables       ../../../../tools/qs-tester/variables/agents_spring_ai_enterprise_identity.py
Library         ../../../../tools/qs-tester/variables/agents_spring_ai_enterprise_identity.py
Library         Collections
Suite Setup     Should Not Be Empty    ${PROJECT}
...             msg=Pass --variable PROJECT:<catalyst-project-name>
Test Teardown   Clean Up Quickstart

*** Variables ***
${PROJECT}      ${EMPTY}

*** Test Cases ***
Java Spring-Ai Enterprise Identity Quickstart
    [Tags]    java    spring-ai-enterprise-identity    agents
    ${qs}=      Get Quickstart
    ${log}=     Suite Log File    agents-spring-ai-enterprise-identity    java

    # Empty for this quickstart -- it ships a canned offline model and both
    # requests are refused before the agent runs -- but kept so that adding a
    # secret to the data module cannot silently skip the check.
    FOR    ${secret}    IN    @{qs}[secrets]
        Require Env Var    ${secret}    agents/spring-ai/enterprise-identity
    END

    # ONE install command for TWO Maven modules. That is what the aggregator pom
    # in the quickstart directory is for; see INSTALL in the data module.
    Build Quickstart            ${qs}
    # README "## Run with Catalyst" step 1, run verbatim.
    Run Documented Commands     ${qs}[setup]    ${PROJECT}    cwd=${qs}[dir]
    Start Quickstart            ${qs}    ${PROJECT}    ${log}

    # Both apps, the agent and the stand-in CRM: CONNECTED_APPS lists both, so
    # this waits for both tunnels and `Stop Quickstart` releases both.
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
    # oversight: with requireAuth=true the filter wraps every route and answers
    # 401 on all of them, the shipped OAuthConfig has no path exclusion, and the
    # app carries no spring-boot-starter-actuator, so no path can produce the 200
    # this keyword polls for. That is also why the quickstart exposes no health
    # route and why its dev config sets enableAppHealthCheck: false. See
    # HEALTH_PROBES in the data module.
    Wait Until Apps Healthy     ${qs}

    # CATALYST_PROBE_MARKERS is empty, so this loop is a no-op too. Unlike the
    # other agents/spring-ai suites that is a decision, not just "unobserved": the
    # gate guards the window in which a WORKFLOW call hangs unrecoverably, and this
    # quickstart starts no workflow -- it has no diagrid-spring-ai-starter, and
    # both requests are refused by the filter before any Dapr call happens. The
    # loop stays so that filling the marker in later is a data change in the
    # variables module, not a change here.
    FOR    ${marker}    IN    @{qs}[catalyst_probe_markers]
        Wait Until Catalyst Attached    ${log}    ${marker}
    END

    # Proves the offline model is the one in play, so this suite cannot quietly
    # pass through a real provider on a machine that exports a key.
    Wait Until Log Contains     ${log}    ${OFFLINE_MODEL_MARKER}    timeout=180s

    # AND that the port is actually accepting connections. `Wait Until Apps
    # Connected` above is satisfied while Spring Boot is still starting, and the
    # model marker is logged before Tomcat binds -- see SERVING_MARKER in the data
    # module for the ordering. Without this the requests below raced the listener
    # and died with `Connection refused`. This repeats READY_MARKERS, which is the
    # same line read as documentation; keeping both means a README that stops
    # documenting the line still leaves the race gated.
    Wait Until Log Contains     ${log}    ${SERVING_MARKER}          timeout=180s

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
        # because a 401 from the filter carries no model output; `field` is the
        # weaker presence check the other agent suites need for responses that
        # do. Both are optional, and no request in this module uses `field`.
        ${body}=        Get From Dictionary    ${request}    body           default=${NONE}
        ${field}=       Get From Dictionary    ${request}    field          default=${NONE}
        # Branches rather than asserting POST, because this quickstart's primary
        # documented example is a GET. An unrecognised method fails loudly rather
        # than being skipped: a request the loop quietly ignores is coverage that
        # reads as green and asserts nothing.
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

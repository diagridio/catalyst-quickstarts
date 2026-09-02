*** Comments ***
End-to-end test for the agents/spring-ai/crash-recovery quickstart (java only:
this quickstart has one implementation, unlike the canonical four-language APIs).

Mirrors agents/spring-ai/crash-recovery/README.md: "## Setup" installs,
"### 1. Deploy and Run" provisions and runs, "### 2. Book under an id you own"
triggers and crashes, "## Recovery: restart the app" restarts, "## Collect the
answer" attaches to the recovered run, "## Clean Up" deletes the project.

Unlike the other two agent-family suites this one covers the crash flow, because
this README documents a way to crash without a source edit: `kill_after_seconds`
makes the app halt itself at a known point inside the booking window. The
two-terminal `POST /crash/kill` variant is in UNCOVERED — the README says to skip
it when kill_after_seconds is sent, and racing a kill against a live window buys
no extra assertion.

Run it:
  export DIAGRID_API_KEY=...
  eval "$(bash tools/qs-tester/ci/project-name.sh agents-spring-ai-crash-recovery | grep '^PROJECT=')"
  bash tools/qs-tester/ci/login.sh
  cd tools/qs-tester
  uv run robot --variable PROJECT:$PROJECT --outputdir results/agents-spring-ai-crash-recovery \
    ../../agents/spring-ai/crash-recovery/tests/quickstart.robot
  bash ci/teardown-project.sh "$PROJECT"

*** Settings ***
Resource        ../../../../tools/qs-tester/resources/catalyst.resource
Resource        ../../../../tools/qs-tester/resources/quickstart.resource
# Imported twice on purpose, same as every other suite: `Variables` exposes the
# module-level names (@{REQUESTS}, ${COMMITTED_MARKER}), `Library` exposes
# get_quickstart as a keyword. Neither import alone gives both.
Variables       ../../../../tools/qs-tester/variables/agents_spring_ai_crash_recovery.py
Library         ../../../../tools/qs-tester/variables/agents_spring_ai_crash_recovery.py
Library         Collections
Suite Setup     Should Not Be Empty    ${PROJECT}
...             msg=Pass --variable PROJECT:<catalyst-project-name>
Test Teardown   Clean Up Quickstart

*** Variables ***
${PROJECT}      ${EMPTY}

*** Test Cases ***
Java Spring Ai Crash Recovery Quickstart
    [Tags]    java    spring-ai    agents    crash-recovery
    ${qs}=      Get Quickstart
    ${log}=     Suite Log File    agents-spring-ai-crash-recovery    java

    # Empty for this quickstart (canned offline model), but kept so that adding a
    # secret to the data module cannot silently skip the check.
    FOR    ${secret}    IN    @{qs}[secrets]
        Require Env Var    ${secret}    agents/spring-ai/crash-recovery
    END

    Build Quickstart            ${qs}
    # README "### 1. Deploy and Run" steps, run verbatim.
    Run Documented Commands     ${qs}[setup]    ${PROJECT}    cwd=${qs}[dir]
    Start Quickstart            ${qs}    ${PROJECT}    ${log}

    Wait Until Apps Connected   ${qs}    ${log}
    # READY_MARKERS is empty for this quickstart: the README documents no readiness
    # wording, and its own note that the recovered run "is usually scrolling before
    # Spring Boot has finished starting Tomcat" means a Tomcat marker would be a
    # LATER signal than the thing under test. Readiness rests on the connection gate.
    FOR    ${marker}    IN    @{READY_MARKERS}
        Wait Until Ready Marker    ${log}    ${marker}
    END
    Wait Until Apps Healthy     ${qs}

    FOR    ${marker}    IN    @{qs}[catalyst_probe_markers]
        Wait Until Catalyst Attached    ${log}    ${marker}
    END

    # Proves the offline model is the one in play. Without it this suite could pass
    # against a real provider on a runner that happens to export a key, and the
    # `secrets: ()` declaration would be untested.
    Wait Until Log Contains     ${log}    ${OFFLINE_MODEL_MARKER}    timeout=180s

    # README "### 2. Book under an id you own", the kill_after_seconds variant. The
    # process halts itself mid-booking, so this call never gets a response — the
    # connection dies with the JVM. Its own outcome proves nothing, which is why the
    # assertion is the port check below, not this request.
    ${payload}=    Create Dictionary
    ...    id=${CRASH_ID}    reference=${CRASH_REFERENCE}    kill_after_seconds=${KILL_AFTER_SECONDS}
    Run Keyword And Ignore Error
    ...    POST    http://localhost:8080/crash/run    json=${payload}    timeout=${KILL_AFTER_SECONDS + 20}

    # The booking actually started. Without this the self-kill below could be a
    # crash before commitReservation ever ran, and the recovery would then have
    # nothing to resume — a demo that proves nothing while passing.
    Wait Until Log Contains     ${log}    ${COMMITTING_SELF_KILL}    timeout=180s
    # And the app halted itself for the documented reason, rather than dying of
    # something else at a convenient moment.
    Wait Until Log Contains     ${log}    ${SELF_KILL_MARKER}    timeout=90s

    # THIS is the assertion that the crash happened. Stop Process Tree below would
    # otherwise silently substitute for a kill that never fired, leaving every
    # downstream assertion passing. It is also the gate that 8080 is free before the
    # relaunch: Wait Until Apps Healthy is perfectly satisfied by an app that never died.
    Wait Until Keyword Succeeds    30s    2s    App Port Is Closed    8080

    # The CLI parent is still up; take the tree down so the alias can be rebound.
    Run Keyword And Ignore Error    Stop Process Tree    apps

    # README "## Recovery: restart the app" — the same run command, nothing else.
    ${log_again}=    Suite Log File    agents-spring-ai-crash-recovery    java-recovery
    Start Quickstart            ${qs}    ${PROJECT}    ${log_again}
    Wait Until Apps Connected   ${qs}    ${log_again}
    Wait Until Apps Healthy     ${qs}

    # README "## Recovery": "You do not have to send anything." Catalyst hands the
    # pending work back on reconnect and the interrupted tool call finishes on its
    # own. Asserting the completion marker in the RESTARTED app's log is what makes
    # that claim testable — a generous budget because it waits out the remainder of
    # the booking's own sleep.
    Wait Until Log Contains     ${log_again}    ${COMMITTED_MARKER}    timeout=240s

    # README "## Collect the answer": the SAME call with the SAME id, which attaches
    # to the finished run and returns the recorded answer. This one does answer, so
    # here the response is the assertion.
    FOR    ${request}    IN    @{REQUESTS}
        Should Be Equal    ${request}[method]    POST
        ...    msg=Only POST requests are handled here; use GET And Expect for a documented GET.
        ${body}=    POST And Expect
        ...    ${request}[port]    ${request}[path]    ${request}[payload]    ${request}[status]
        # README "## Collect the answer" prints this shape verbatim and states that
        # with the offline model `result` is exactly the tool's own line. Asserted as
        # a prefix because the README documents that the code after BK- is derived
        # from the reference without documenting the derived value.
        Should Start With    ${body}[${request}[field]]    ${CRASH_RESULT_PREFIX}
        ...    msg=Re-issued /crash/run did not return the recorded booking confirmation
        Should Be Equal    ${body}[message]    ${NONE}
        ...    msg=A 200 must carry no attach instruction
    END

    # The whole point of the demo. The booking committed exactly once: if the
    # restarted app logged the committing line again, the crash landed outside the
    # window and Catalyst replayed work it had already recorded.
    Log Should Not Contain      ${log_again}    ${COMMITTING_SELF_KILL}

*** Keywords ***
Clean Up Quickstart
    [Documentation]    Stop the apps, then run whatever cleanup the README
    ...    documents. `Stop Quickstart` also calls `diagrid dev stop`, which
    ...    releases the local app connections.
    ...
    ...    This quickstart's TEARDOWN documents `diagrid project delete`
    ...    ("## Clean Up"), so this loop really deletes the ephemeral project.
    ...    `Run Keyword And Ignore Error` guards both calls: `Stop Process Tree`
    ...    is not idempotent against a process that has already exited, and this
    ...    suite deliberately kills the app mid-test, so by the time teardown runs
    ...    the tree may already be gone. A failed stop must not prevent the
    ...    documented delete from running.
    Run Keyword And Ignore Error    Stop Quickstart    ${PROJECT}
    ${qs}=    Get Quickstart
    Run Keyword And Ignore Error
    ...    Run Documented Commands    ${qs}[teardown]    ${PROJECT}

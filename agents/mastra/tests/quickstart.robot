*** Comments ***
End-to-end test for the agents/mastra quickstart, crash-recovery flow.

Mirrors agents/mastra/README.md "## Crash Recovery Test With Catalyst": "### 3"
starts the crash app, "### 4" runs under an id you own with kill_after_seconds,
"### 5" restarts, "### 6" collects the answer. The README's main flow
(dev-mastra.yaml, one turn of main.ts) and the "Optional: crash the app
yourself" POST /crash/kill variant are in UNCOVERED in the data module.

mastra calls a real model, so this suite asserts only on log markers the app
prints and on framework-generated fields, never on model prose.

Run live on 2026-10-16: PASS 1/1 in 130s, real model (OpenAI). The first run
failed on restart with a stale ~/.diagrid/tuns/<project>:sre-agent lock file; the
re-run passed after the first dev run was made to exit by itself before being
stopped. That pass does not prove the fix, because the CLI had already exited that
time. The logs showed the app self-killed at kill_after_seconds, the restarted app
did not repeat step 1, the interrupted step 2 resumed, and the re-issued POST
/crash/run returned 200 with a result. No mutation check has been run
(ci/check_mutation.py), so the suite stays nightly False.

Run it:
  export DIAGRID_API_KEY=...
  export OPENAI_API_KEY=...
  eval "$(bash tools/qs-tester/ci/project-name.sh agents-mastra | grep '^PROJECT=')"
  bash tools/qs-tester/ci/login.sh
  cd tools/qs-tester
  uv run robot --variable PROJECT:$PROJECT --outputdir results/agents-mastra \
    ../../agents/mastra/tests/quickstart.robot
  bash ci/teardown-project.sh "$PROJECT"

*** Settings ***
Resource        ../../../tools/qs-tester/resources/catalyst.resource
Resource        ../../../tools/qs-tester/resources/quickstart.resource
# Imported twice on purpose, same as every other suite: `Variables` exposes the
# module-level names (@{REQUESTS}, ${STEP1_MARKER}), `Library` exposes
# get_quickstart as a keyword. Neither import alone gives both.
Variables       ../../../tools/qs-tester/variables/agents_mastra.py
Library         ../../../tools/qs-tester/variables/agents_mastra.py
Library         Collections
Suite Setup     Should Not Be Empty    ${PROJECT}
...             msg=Pass --variable PROJECT:<catalyst-project-name>
Test Teardown   Clean Up Quickstart

*** Variables ***
${PROJECT}      ${EMPTY}

*** Test Cases ***
Javascript Mastra Crash Recovery Quickstart
    [Tags]    javascript    mastra    agents    crash-recovery
    ${qs}=      Get Quickstart
    ${log}=     Suite Log File    agents-mastra    javascript

    # A missing model key must fail here, before a project is created.
    FOR    ${secret}    IN    @{qs}[secrets]
        Require Env Var    ${secret}    agents/mastra
    END

    Build Quickstart            ${qs}
    # README "### 1. Login and Run" steps 2-3, run verbatim.
    Run Documented Commands     ${qs}[setup]    ${PROJECT}    cwd=${qs}[dir]
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
    # because it needs a started app and a second test case would need a second
    # start. It schedules nothing, so it cannot disturb the crash below.
    ${empty}=   Create Dictionary
    ${bad}=     POST And Expect    ${APP_PORT}    /crash/run    ${empty}    400
    FOR    ${key}    IN    id    result    message
        Dictionary Should Contain Key    ${bad}    ${key}
        ...    msg=400 body is missing "${key}": ${bad}
    END
    Should Be Equal    ${bad}[result]    ${NONE}
    Should Not Be Empty    ${bad}[message]

    # README "### 4", with kill_after_seconds. The process halts itself, so this
    # call never gets a response and its outcome proves nothing; the port check
    # below is the crash assertion.
    ${payload}=    Create Dictionary
    ...    id=${CRASH_ID}    prompt=${CRASH_PROMPT}    kill_after_seconds=${KILL_AFTER_SECONDS}
    Run Keyword And Ignore Error
    ...    POST    http://localhost:${APP_PORT}/crash/run    json=${payload}    timeout=120

    # Step 1 (model call 1) completed before the crash, so there is something to
    # resume. The generous timeouts cover a real model round trip.
    Wait Until Log Contains     ${log}    ${STEP1_MARKER}          timeout=180s
    # The armed variant of step 2's line, so step 2 started AND armed the kill.
    Wait Until Log Contains     ${log}    ${STEP2_ARMED_MARKER}    timeout=180s
    # The app halted itself for the documented reason, not something else.
    Wait Until Log Contains     ${log}    ${SELF_KILL_MARKER}      timeout=90s

    # THE assertion that the crash happened. Stop Process Tree below would
    # otherwise substitute for a kill that never fired. It also gates on the port
    # being free before the relaunch.
    Wait Until Keyword Succeeds    30s    2s    App Port Is Closed    ${APP_PORT}

    # Let the first `diagrid dev run` finish shutting itself down after the crash. Signalling it
    # mid-shutdown interrupted its cleanup and left ~/.diagrid/tuns/<project>:<app id> behind, so the
    # restart failed with "file ... already exists for App ID" (seen on the first live mastra run).
    # Stop Process Tree below then only mops up anything still alive.
    Wait For Process    apps    timeout=30s    on_timeout=continue
    Run Keyword And Ignore Error    Stop Process Tree    apps

    # README "### 5. Restart the app": the same run command, nothing else.
    ${log_again}=    Suite Log File    agents-mastra    javascript-recovery
    Start Quickstart            ${qs}    ${PROJECT}    ${log_again}
    Wait Until Apps Connected   ${qs}    ${log_again}
    Wait Until Apps Healthy     ${qs}

    # "You do not have to send anything": Catalyst hands the run back on reconnect
    # and the interrupted tool finishes on its own, about 10s after it restarts.
    Wait Until Log Contains     ${log_again}    ${STEP2_DONE_MARKER}    timeout=240s

    # README "### 6. Collect the answer": the same call with the same id attaches to
    # the finished run. 200, `result` set, `message` null.
    FOR    ${request}    IN    @{REQUESTS}
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

    # "Model call 1 is not made again": its line must not appear in the restarted
    # app's log. The line is numbered from the workflow's own iteration index, not
    # a per-process counter, so a re-made first call would print it here.
    Log Should Not Contain    ${log_again}    ${STEP1_MARKER}

*** Keywords ***
Clean Up Quickstart
    [Documentation]    Stop the apps, then run whatever cleanup the README
    ...    documents. `Stop Quickstart` also calls `diagrid dev stop`, which
    ...    releases the local app connections.
    ...
    ...    TEARDOWN is empty here: the README's `diagrid project delete` stops at
    ...    an interactive prompt, so it is in UNCOVERED and ci/teardown-project.sh
    ...    deletes the ephemeral project (with --yes).
    ...    `Run Keyword And Ignore Error` guards both calls: this suite kills the
    ...    app mid-test, so the process tree may already be gone, and a failed
    ...    stop must not prevent whatever cleanup is documented from running.
    Run Keyword And Ignore Error    Stop Quickstart    ${PROJECT}
    ${qs}=    Get Quickstart
    Run Keyword And Ignore Error
    ...    Run Documented Commands    ${qs}[teardown]    ${PROJECT}

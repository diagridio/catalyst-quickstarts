*** Comments ***
End-to-end test for the workflow quickstart, all four languages.

Mirrors workflow/<language>/README.md: section 6.1 starts an instance, 6.2 gets
its status, and section 7 runs the crash-recovery demo in the three languages
that ship one. POST /workflow/terminate/{id} is deliberately absent — no README
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
# OperatingSystem is here for Set Environment Variable alone: the crash cases drive
# the app's delay down through the environment it inherits from this process.
Library         OperatingSystem
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

# The crash cases run on every nightly for their language and cannot be tagged out
# of it: e2e-quickstarts.yml passes only `--include <lang>` and never `--exclude`,
# and Robot ORs --include values, so `csharp crash` matches `--include csharp`. The
# `crash` tag is there to select them by hand, not to let CI skip them. Skipping
# would need a workflow edit.
Csharp Workflow Crash Recovery
    [Tags]    csharp    crash
    Run Workflow Crash Recovery    csharp

Java Workflow Crash Recovery
    [Tags]    java    crash
    Run Workflow Crash Recovery    java

Python Workflow Crash Recovery
    [Tags]    python    crash
    Run Workflow Crash Recovery    python

*** Keywords ***
Run Workflow Quickstart
    [Arguments]    ${language}
    ${qs}=      Get Quickstart    workflow    ${language}
    ${log}=     Suite Log File    workflow    ${language}
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

Run Workflow Crash Recovery
    [Documentation]    README section 7: start a run under an id you own, kill the app
    ...    mid-activity, restart, re-issue the identical request, and get the same
    ...    answer without the fast activity having run again.
    [Arguments]    ${language}
    Should Contain    ${CRASH_LANGUAGES}    ${language}
    ...    msg=${language} ships no crash-recovery demo
    ${qs}=          Get Quickstart    workflow    ${language}
    # Two log files. Start Background Process truncates whatever it is given, so a
    # single file would let the restart erase the pre-crash evidence.
    ${log_first}=   Suite Log File    workflow    ${language}    -crash-first
    ${log_again}=   Suite Log File    workflow    ${language}    -crash-restart

    # The apps read this from the environment they inherit. 30s four times over is not
    # a cost this suite should pay to prove something 20s proves.
    Set Environment Variable    CRASH_DELAY_SECONDS    ${CRASH_DELAY_SECONDS}

    ${crash_id}=    Replace String    ${CRASH_INSTANCE_ID}    {language}    ${language}
    ${payload}=     Create Dictionary    id=${crash_id}    reference=${CRASH_REFERENCE}
    ${committing}=  Set Variable    ${CRASH_COMMITTING_MARKER}
    ${received}=    Replace String    ${CRASH_RECEIVED_MARKER}    {id}    ${crash_id}
    ${done}=        Replace String    ${CRASH_DONE_MARKER}    {id}    ${crash_id}

    Build Quickstart            ${qs}
    Start Quickstart            ${qs}    ${PROJECT}    ${log_first}
    Wait Until Apps Connected   ${qs}    ${log_first}
    Wait Until Apps Healthy     ${qs}

    # README 7.1 — start the run. The response never arrives: /crash/run blocks for the
    # length of the slow activity and the app is killed while it is still blocked. So the
    # client timeout is short and its failure is expected; the log is the signal.
    Run Keyword And Ignore Error
    ...    POST    http://localhost:5001/crash/run    json=${payload}    timeout=2
    Wait Until Log Contains     ${log_first}    ${received}      timeout=120s
    Wait Until Log Contains     ${log_first}    ${committing}    timeout=60s

    # README 7.2 — kill the app mid-activity. This request cannot answer either: the
    # process is gone before a response is written.
    Run Keyword And Ignore Error
    ...    POST    http://localhost:5001/crash/kill    timeout=2
    Run Keyword And Ignore Error    Stop Process Tree    apps

    # README 7.3 — restart with the same run command and wait for the run to finish.
    Start Quickstart            ${qs}    ${PROJECT}    ${log_again}
    Wait Until Apps Connected   ${qs}    ${log_again}
    Wait Until Apps Healthy     ${qs}
    Wait Until Log Contains     ${log_again}    ${CRASH_COMMITTED_MARKER}    timeout=180s
    Wait Until Log Contains     ${log_again}    ${done}                      timeout=60s

    # README 7.3 — re-issue the IDENTICAL request. It attaches to the finished instance
    # rather than reserving again, and returns the same confirmation code.
    ${body}=    POST And Expect    5001    /crash/run    ${payload}    200
    Should Be Equal    ${body}[result]    ${CRASH_CONFIRMATION}
    ...    msg=Re-issued /crash/run did not return the recorded confirmation

    # The whole proof. The fast activity completed and Catalyst recorded its result
    # before the crash, so the replay must not have run it a second time. If this marker
    # is in the restarted app's log, the crash landed before the first persisted
    # completion and the demo demonstrates nothing.
    Log Should Not Contain    ${log_again}    ${received}

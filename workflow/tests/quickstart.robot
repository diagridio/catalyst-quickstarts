*** Comments ***
End-to-end test for the workflow quickstart, all four languages.

Mirrors workflow/<language>/README.md: section 6.1 starts an instance, 6.2 gets
its status, and section 7 runs the crash-recovery demo in the three languages
that ship one. POST /workflow/terminate/{id} is deliberately absent: no README
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

# A case that skips itself, rather than no case at all. The javascript leg otherwise
# shows one workflow test where every other leg shows two, with nothing in the report
# saying why.
Javascript Workflow Crash Recovery
    [Tags]    javascript    crash
    Skip    javascript ships no crash-recovery demo: workflow/javascript/README.md has no section 7

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
    ${log_first}=   Suite Log File    workflow    ${language}    crash-first
    ${log_again}=   Suite Log File    workflow    ${language}    crash-restart

    # The apps read both of these from the environment they inherit. 30s four times over is
    # not a cost this suite should pay to prove something 20s proves, and a short wait budget
    # turns the blocking first call into the documented 202. Removed again in [Teardown]
    # below, so neither can leak into a case that runs after this one.
    Set Environment Variable    CRASH_DELAY_SECONDS    ${CRASH_DELAY_SECONDS}
    Set Environment Variable    CRASH_WAIT_SECONDS     ${CRASH_WAIT_SECONDS}

    # Unique per run, not a fixed `trip-42-<language>`. A constant id is already
    # COMPLETED on the second run against a project that has seen this test, and
    # /crash/run would then attach to it, execute nothing, and leave the first marker
    # wait below to burn its whole budget and fail pointing at the app. CI mints a
    # fresh project per leg and so never noticed; the documented local invocation does.
    ${unique}=      Generate Random String    6    [NUMBERS]
    ${crash_id}=    Replace String    ${CRASH_INSTANCE_ID}    {language}    ${language}-${unique}
    ${payload}=     Create Dictionary    id=${crash_id}    reference=${CRASH_REFERENCE}
    ${received}=    Replace String    ${CRASH_RECEIVED_MARKER}    {id}    ${crash_id}
    ${done}=        Replace String    ${CRASH_DONE_MARKER}    {id}    ${crash_id}
    ${attaching}=   Replace String    ${CRASH_ATTACH_MARKER}    {id}    ${crash_id}

    # Builds again, even though the plain case in this suite already built the same tree
    # and both cases always run in the same CI leg. Deliberate: `--test "Java Workflow
    # Crash Recovery"` has to work on its own. For java that is a second `mvn clean
    # install`, which is the price of that independence.
    Build Quickstart            ${qs}
    Start Quickstart            ${qs}    ${PROJECT}    ${log_first}
    Wait Until Apps Connected   ${qs}    ${log_first}
    Wait Until Apps Healthy     ${qs}

    # README 7.1: start the run, and assert the documented 202.
    #
    # A reader on the default 120s budget sees this call BLOCK, and the previous version of
    # this test threw the response away behind Run Keyword And Ignore Error because it could
    # not wait that long. That hid every real failure: a 422 from a renamed field or a 500
    # from an unregistered workflow surfaced 120s later as "the log lacks a marker", pointing
    # away from the response body that named the cause. It also left the 202 branch, which
    # every README documents, with no coverage in any language.
    #
    # Driving CRASH_WAIT_SECONDS down to a few seconds fixes both at once: the budget elapses
    # while the slow activity is still committing, which is exactly the state the 202 exists to
    # report, so the assertion is real and costs no extra wall clock. The run keeps going
    # regardless, which is what the rest of this test depends on.
    ${body}=    POST And Expect    5001    /crash/run    ${payload}    202
    Should Be Equal    ${body}[id]    ${crash_id}
    Should Be Equal    ${body}[result]    ${NONE}
    ...    msg=A 202 must carry no result
    Should Contain    ${body}[message]    still running as ${crash_id}
    ...    msg=A 202 must tell the caller to re-issue the same id

    # Asserts the injected delay actually reached the app. The marker carries the number,
    # so a value that never propagated (and left the app on its 30s default) fails here
    # instead of surfacing later as a kill that lands after the window closed.
    Wait Until Log Contains     ${log_first}    ${received}                  timeout=120s
    Wait Until Log Contains     ${log_first}    ${CRASH_COMMITTING_MARKER}    timeout=60s

    # README 7.2: kill the app mid-activity. This request cannot answer either: the
    # process is gone before a response is written, so its own outcome proves nothing.
    Run Keyword And Ignore Error
    ...    POST    http://localhost:5001/crash/kill    timeout=2

    # THIS is the assertion that /crash/kill worked. Without it the Stop Process Tree
    # below silently substitutes for a broken endpoint: a 404, a 405 or an unregistered
    # route leaves every downstream assertion passing, and the one endpoint README 7.2
    # tells the reader to call is never exercised at all. It is also the gate that port
    # 5001 is free before the relaunch, since Wait Until Apps Healthy is perfectly
    # satisfied by an app that never died.
    Wait Until Keyword Succeeds    30s    2s    App Port Is Closed    5001

    # The CLI parent is still up; take the tree down so the alias can be rebound.
    Run Keyword And Ignore Error    Stop Process Tree    apps

    # README 7.3: restart with the same run command and wait for the run to finish.
    Start Quickstart            ${qs}    ${PROJECT}    ${log_again}
    Wait Until Apps Connected   ${qs}    ${log_again}
    Wait Until Apps Healthy     ${qs}
    # Split budget so a failure says WHICH half broke: the interrupted activity never
    # got redispatched, or it got redispatched and did not finish.
    Wait Until Log Contains     ${log_again}    ${CRASH_COMMITTING_MARKER}    timeout=240s
    Wait Until Log Contains     ${log_again}    ${CRASH_COMMITTED_MARKER}     timeout=90s
    Wait Until Log Contains     ${log_again}    ${done}                       timeout=60s

    # README 7.3: re-issue the IDENTICAL request. It attaches to the finished instance
    # rather than reserving again, and returns the same confirmation code.
    ${body}=    POST And Expect    5001    /crash/run    ${payload}    200
    Should Be Equal    ${body}[result]    ${CRASH_CONFIRMATION}
    ...    msg=Re-issued /crash/run did not return the recorded confirmation

    # The confirmation above is a pure function of the reference, so it is identical for
    # an attached run, a re-run and a brand new instance, and on its own it cannot tell
    # them apart. This marker is the discriminator: only the attach branch logs it.
    Wait Until Log Contains     ${log_again}    ${attaching}    timeout=30s

    # The whole proof. The fast activity completed and Catalyst recorded its result
    # before the crash, so the replay must not have run it a second time. If this marker
    # is in the restarted app's log, the crash landed before the first persisted
    # completion and the demo demonstrates nothing.
    Log Should Not Contain    ${log_again}    ${received}

    # A KEYWORD teardown, deliberately, not a test-level one. A test-level [Teardown]
    # would REPLACE the suite's `Test Teardown    Stop Quickstart` and leak the whole
    # dev-run tree; a keyword teardown runs in addition to it, so the env var is cleaned
    # up here and the process tree is still stopped by the suite exactly once.
    [Teardown]    Remove Environment Variable    CRASH_DELAY_SECONDS    CRASH_WAIT_SECONDS

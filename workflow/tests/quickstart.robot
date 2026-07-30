*** Comments ***
End-to-end test for the workflow quickstart, all four languages.

Mirrors workflow/<language>/README.md: section 6.1 starts an instance, 6.2 gets
its status. POST /workflow/terminate/{id} is deliberately absent — no README
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

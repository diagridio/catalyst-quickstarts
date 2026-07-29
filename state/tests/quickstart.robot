*** Comments ***
End-to-end test for the state management quickstart, all four languages.

Mirrors state/<language>/README.md exactly: section 4 installs, section 5 runs,
section 6.1 stores and 6.2 retrieves. DELETE /order/{id} is deliberately absent —
no README documents it, and the suites test the documented flow and nothing more.

Run one language at a time:
  cd tools/qs-tester
  uv run robot --include python --variable PROJECT:my-project \
    --outputdir results/state ../../state/tests/quickstart.robot

*** Settings ***
Resource        ../../tools/qs-tester/resources/catalyst.resource
Resource        ../../tools/qs-tester/resources/quickstart.resource
# quickstarts.py is imported twice on purpose. `Variables` exposes its module-level
# dicts as ${STATE_STORE_BODY} and friends; `Library` exposes get_quickstart as the
# `Get Quickstart` keyword. A Variables import alone would NOT provide the keyword.
Variables       ../../tools/qs-tester/variables/quickstarts.py
Library         ../../tools/qs-tester/variables/quickstarts.py
Library         Collections
Suite Setup     Should Not Be Empty    ${PROJECT}
...             msg=Pass --variable PROJECT:<catalyst-project-name>
Test Teardown   Stop Quickstart    ${PROJECT}

*** Variables ***
${PROJECT}      ${EMPTY}

*** Test Cases ***
Csharp State Quickstart
    [Tags]    csharp
    Run State Quickstart    csharp

Java State Quickstart
    [Tags]    java
    Run State Quickstart    java

Javascript State Quickstart
    [Tags]    javascript
    Run State Quickstart    javascript

Python State Quickstart
    [Tags]    python
    Run State Quickstart    python

*** Keywords ***
Run State Quickstart
    [Arguments]    ${language}
    ${qs}=      Get Quickstart    state    ${language}
    ${log}=     Suite Log File    state
    Build Quickstart            ${qs}
    Start Quickstart            ${qs}    ${PROJECT}    ${log}
    # state's app has appPort 0, so no `Connected App ID` line is ever emitted.
    # The keyword iterates an empty list here; the health check is the real gate.
    Wait Until Apps Connected   ${qs}    ${log}
    Wait Until Apps Healthy     ${qs}

    # README 6.1 — store state
    ${expected_store}=      Get From Dictionary    ${STATE_STORE_BODY}    ${language}
    POST And Expect         5001    /order    ${ORDER_PAYLOAD}    201    ${expected_store}
    Wait Until Log Contains    ${log}    ${STATE_SAVE_MARKER}

    # README 6.2 — retrieve state
    ${expected_get}=        Get From Dictionary    ${STATE_RETRIEVE_BODY}    ${language}
    GET And Expect          5001    /order/1    200    ${expected_get}
    Wait Until Log Contains    ${log}    ${STATE_RETRIEVE_MARKER}

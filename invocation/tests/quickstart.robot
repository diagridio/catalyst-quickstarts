*** Comments ***
End-to-end test for the service invocation quickstart, all four languages.

Mirrors invocation/<language>/README.md: section 6.1 posts an order to the client,
which invokes the server through Catalyst. The client returns 500 if the server is
unreachable, so a 200 with the documented body already proves the round trip; the
log markers additionally prove both processes did the work.

Run one language at a time:
  cd tools/qs-tester
  uv run robot --include python --variable PROJECT:my-project \
    --outputdir results/invocation ../../invocation/tests/quickstart.robot

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
Csharp Invocation Quickstart
    [Tags]    csharp
    Run Invocation Quickstart    csharp

Java Invocation Quickstart
    [Tags]    java
    Run Invocation Quickstart    java

Javascript Invocation Quickstart
    [Tags]    javascript
    Run Invocation Quickstart    javascript

Python Invocation Quickstart
    [Tags]    python
    Run Invocation Quickstart    python

*** Keywords ***
Run Invocation Quickstart
    [Arguments]    ${language}
    ${qs}=      Get Quickstart    invocation    ${language}
    ${log}=     Suite Log File    invocation    ${language}
    Build Quickstart            ${qs}
    Start Quickstart            ${qs}    ${PROJECT}    ${log}
    # Only `server` has an appPort, so only its connection marker is emitted —
    # matching the README, which names server and not client.
    Wait Until Apps Connected   ${qs}    ${log}
    Wait Until Apps Healthy     ${qs}

    # README 6.1 — client invokes server. Body is identical in all four languages.
    POST And Expect     5001    /order    ${ORDER_PAYLOAD}    200    ${INVOCATION_BODY}

    Wait Until Log Contains     ${log}    ${INVOCATION_SERVER_MARKER}
    ${client_marker}=   Get From Dictionary    ${INVOCATION_CLIENT_MARKER}    ${language}
    Wait Until Log Contains     ${log}    ${client_marker}

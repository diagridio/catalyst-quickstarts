*** Comments ***
End-to-end test for the pub/sub quickstart, all four languages.

Mirrors pubsub/<language>/README.md section 6.1, which publishes one order.

The subscriber log marker is not optional decoration: the publisher returns 201 as
soon as the broker accepts the message, and the subscriber exposes no queryable
endpoint, so without that marker a broken subscription or a mis-scoped
subscription.yaml would pass a green test.

Run one language at a time:
  cd tools/qs-tester
  uv run robot --include python --variable PROJECT:my-project \
    --outputdir results/pubsub ../../pubsub/tests/quickstart.robot

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
Csharp Pubsub Quickstart
    [Tags]    csharp
    Run Pubsub Quickstart    csharp

Java Pubsub Quickstart
    [Tags]    java
    Run Pubsub Quickstart    java

Javascript Pubsub Quickstart
    [Tags]    javascript
    Run Pubsub Quickstart    javascript

Python Pubsub Quickstart
    [Tags]    python
    Run Pubsub Quickstart    python

*** Keywords ***
Run Pubsub Quickstart
    [Arguments]    ${language}
    ${qs}=      Get Quickstart    pubsub    ${language}
    ${log}=     Suite Log File    pubsub
    Build Quickstart            ${qs}
    Start Quickstart            ${qs}    ${PROJECT}    ${log}
    # Both apps have an appPort, so both connection markers are emitted — the
    # README tells the user to wait for exactly these two lines.
    Wait Until Apps Connected   ${qs}    ${log}
    Wait Until Apps Healthy     ${qs}

    # README 6.1 — publish
    ${expected}=    Get From Dictionary    ${PUBSUB_PUBLISH_BODY}    ${language}
    POST And Expect     5001    /order    ${ORDER_PAYLOAD}    201    ${expected}
    Wait Until Log Contains     ${log}    ${PUBSUB_PUBLISH_MARKER}

    # Delivery to the subscriber. Longer timeout than the other markers: this is
    # a round trip through the managed broker, not a local function call.
    ${receive_marker}=  Get From Dictionary    ${PUBSUB_RECEIVE_MARKER}    ${language}
    Wait Until Log Contains     ${log}    ${receive_marker}    timeout=120s

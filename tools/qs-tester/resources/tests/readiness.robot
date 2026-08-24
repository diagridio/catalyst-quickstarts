*** Comments ***
Tests the readiness gate in quickstart.resource against flaky_server.py, which
reproduces the shape of Catalyst's startup window without a project or
credentials. Runs in a few seconds; CI's lint job runs it on every PR.

The negative test matters more than the positive one. A gate that never fails is
a gate that would let a permanently broken invocation ship green, which is the
failure mode the invocation suite exists to catch.

*** Settings ***
Resource        ../quickstart.resource
Resource        ../process.resource
Library         OperatingSystem
Library         Process
Library         Collections
Test Teardown   Run Keyword And Ignore Error    Stop Process Tree    flaky

*** Variables ***
${PORT}         5099
${SERVER}       ${CURDIR}/flaky_server.py

*** Test Cases ***
Gate Returns Once The Endpoint Stops Answering 500
    [Documentation]    Two 500s then 200, exactly the real startup window in
    ...    miniature. The gate must absorb the 500s and return.
    Start Flaky Server    2
    ${payload}=    Create Dictionary    orderId=${1}
    Wait Until Not Server Error    ${PORT}    /order    ${payload}
    ...    timeout=30s    interval=1s
    # The gate returning is not enough: prove the endpoint really is serving 200
    # now, so a gate that returned for the wrong reason cannot pass this test.
    ${response}=    POST    http://localhost:${PORT}/order    json=${payload}
    ...    expected_status=200    timeout=10

Gate Fails When The Endpoint Never Recovers
    [Documentation]    A permanently broken endpoint must make the gate fail, not
    ...    pass vacuously once the timeout expires.
    Start Flaky Server    1000
    ${payload}=    Create Dictionary    orderId=${1}
    # Match the gate's own message, not `*`: a bare glob also matches "No keyword
    # with name ... found", so this test would pass on a gate that does not exist.
    Run Keyword And Expect Error    *still answering 500*
    ...    Wait Until Not Server Error    ${PORT}    /order    ${payload}
    ...    timeout=4s    interval=1s

Gate Does Not Absorb A 4xx
    [Documentation]    The gate waits out 5xx only. A 404 is a real answer from a
    ...    reachable app, so it must return at once and leave the verdict to the
    ...    strict assertion that follows it in the suite.
    Start Flaky Server    0
    ${payload}=    Create Dictionary    orderId=${1}
    ${before}=    Get Time    epoch
    Wait Until Not Server Error    ${PORT}    /missing    ${payload}
    ...    timeout=60s    interval=5s
    ${after}=    Get Time    epoch
    ${elapsed}=    Evaluate    ${after} - ${before}
    Should Be True    ${elapsed} < 10
    ...    msg=Gate took ${elapsed}s on a 404; it is polling instead of returning

*** Keywords ***
Start Flaky Server
    [Arguments]    ${failures}
    Start Background Process    python3 ${SERVER} ${PORT} ${failures}
    ...    ${TEMPDIR}/flaky-server.log    flaky
    Wait Until Log Contains    ${TEMPDIR}/flaky-server.log    listening on ${PORT}
    ...    timeout=20s

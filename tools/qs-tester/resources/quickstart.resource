*** Comments ***
Building a quickstart, waiting for its apps to serve, and asserting documented
HTTP responses. Response bodies are compared as parsed JSON, not as strings, so
key order and whitespace cannot cause a false failure.

*** Settings ***
Library     RequestsLibrary
Library     Collections
Library     OperatingSystem
Resource    process.resource

*** Keywords ***
Build Quickstart
    [Documentation]    Run the install command from the quickstart's README section 4.
    [Arguments]    ${qs}
    Log    Building ${qs}[dir]: ${qs}[install]    console=True
    Run And Expect RC Zero    ${qs}[install]    cwd=${qs}[dir]    timeout=900s

Suite Log File
    [Documentation]    One captured `diagrid dev run` stream per (api, language).
    ...    Lives under the Robot output dir so CI uploads it with the report.
    ...    The language MUST be in the filename: all four language tests share a
    ...    suite, and Start Background Process truncates this file, so a per-api
    ...    name left only the last language's log on disk and destroyed the
    ...    evidence for whichever earlier language actually failed.
    [Arguments]    ${api}    ${language}
    RETURN    ${OUTPUT DIR}/${api}-${language}-dev-run.log

Wait Until Apps Healthy
    [Documentation]    Poll `GET /` on every app port until it answers 200. This is
    ...    the only readiness gate for workflow and state, which emit no connection
    ...    marker, so the timeout is generous enough for a JVM or .NET cold start.
    [Arguments]    ${qs}
    FOR    ${port}    IN    @{qs}[health_ports]
        Wait Until Keyword Succeeds    180s    3s    Health Check Returns 200    ${port}
    END

Health Check Returns 200
    [Arguments]    ${port}
    GET    http://localhost:${port}/    expected_status=200    timeout=10

Wait Until Not Server Error
    [Documentation]    Poll POST ${path} until it answers with anything other than
    ...    5xx, then return without asserting the body.
    ...
    ...    Neither readiness signal the harness can observe proves Catalyst can
    ...    route INTO an app. `diagrid dev run` prints
    ...    `Connected App ID "<id>" to http://localhost:<port>` when the tunnel is
    ...    established, and `GET /` answers 200 as soon as the app's own server is
    ...    up, but Catalyst marks the app channel healthy only after it has probed
    ...    the app through that tunnel itself. Measured against a real project:
    ...    invocation answered 500 `ERR_DIRECT_INVOKE ... app is not in a healthy
    ...    state` at the instant both signals were satisfied, and 200 sixteen
    ...    seconds later. A suite that fires its documented request the moment the
    ...    signals pass is racing that window, which is exactly how this failed.
    ...
    ...    Deliberately narrow: 5xx is waited out, everything else returns
    ...    immediately, and the caller still has to assert the documented status and
    ...    body afterwards. A permanently broken app makes this keyword time out and
    ...    fail rather than pass vacuously — see resources/tests/readiness.robot,
    ...    which tests all three of those properties.
    [Arguments]    ${port}    ${path}    ${payload}    ${timeout}=90s    ${interval}=3s
    Wait Until Keyword Succeeds    ${timeout}    ${interval}
    ...    Request Is Not Server Error    ${port}    ${path}    ${payload}

Request Is Not Server Error
    [Arguments]    ${port}    ${path}    ${payload}
    # expected_status=anything: a 500 here is the condition being polled, not a
    # failure to report, so RequestsLibrary must not raise on it.
    ${response}=    POST    http://localhost:${port}${path}    json=${payload}
    ...    expected_status=anything    timeout=30
    Should Be True    ${response.status_code} < 500
    ...    msg=POST ${path} still answering ${response.status_code}: ${response.text}

POST And Expect
    [Documentation]    POST ${payload} as JSON and assert the status code and, if
    ...    given, the exact parsed response body.
    [Arguments]    ${port}    ${path}    ${payload}    ${status}    ${expected_body}=${NONE}
    ${response}=    POST    http://localhost:${port}${path}    json=${payload}
    ...    expected_status=${status}    timeout=30
    ${body}=    Set Variable    ${response.json()}
    IF    $expected_body is not None
        Should Be Equal    ${body}    ${expected_body}
        ...    msg=POST ${path} body mismatch.\nExpected: ${expected_body}\nActual: ${body}
    END
    RETURN    ${body}

GET And Expect
    [Arguments]    ${port}    ${path}    ${status}    ${expected_body}=${NONE}
    ${response}=    GET    http://localhost:${port}${path}
    ...    expected_status=${status}    timeout=30
    ${body}=    Set Variable    ${response.json()}
    IF    $expected_body is not None
        Should Be Equal    ${body}    ${expected_body}
        ...    msg=GET ${path} body mismatch.\nExpected: ${expected_body}\nActual: ${body}
    END
    RETURN    ${body}

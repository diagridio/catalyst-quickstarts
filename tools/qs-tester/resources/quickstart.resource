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
    [Documentation]    One captured `diagrid dev run` stream per suite. Lives under
    ...    the Robot output dir so CI uploads it with the report.
    [Arguments]    ${api}
    RETURN    ${OUTPUT DIR}/${api}-dev-run.log

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

POST And Expect
    [Documentation]    POST ${payload} as JSON and assert the status code and, if
    ...    given, the exact parsed response body.
    [Arguments]    ${port}    ${path}    ${payload}    ${status}    ${expected_body}=${NONE}
    ${response}=    POST    http://localhost:${port}${path}    json=${payload}
    ...    expected_status=${status}    timeout=30
    ${body}=    Set Variable    ${response.json()}
    IF    $expected_body is not None
        Should Be Equal    ${body}    ${expected_body}
        ...    msg=POST ${path} body mismatch.\nExpected: ${expected_body}\nActual:   ${body}
    END
    RETURN    ${body}

GET And Expect
    [Arguments]    ${port}    ${path}    ${status}    ${expected_body}=${NONE}
    ${response}=    GET    http://localhost:${port}${path}
    ...    expected_status=${status}    timeout=30
    ${body}=    Set Variable    ${response.json()}
    IF    $expected_body is not None
        Should Be Equal    ${body}    ${expected_body}
        ...    msg=GET ${path} body mismatch.\nExpected: ${expected_body}\nActual:   ${body}
    END
    RETURN    ${body}

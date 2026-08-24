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
    [Documentation]    Poll every `(port, path)` probe in ${qs}[health_probes] until
    ...    it answers 200. This is the only readiness gate for workflow and state,
    ...    which emit no connection marker, so the timeout is generous enough for a
    ...    JVM or .NET cold start.
    ...
    ...    The path is part of the probe, not hardcoded to `/`, because "GET /
    ...    answers 200" is a property of the specific app and not of apps in
    ...    general. The canonical quickstarts all route `/` themselves
    ...    (state/python/main.py, state/csharp/Program.cs, state/javascript/index.js,
    ...    state/java Controller.java), so `quickstarts.get_quickstart` pairs every
    ...    port with `/`. An agent app built on the Diagrid SDK's
    ...    DaprWorkflowGraphRunner.serve() does not: it registers its own routes on a
    ...    bare FastAPI() and answers 404 on `/`, so probing `/` there would wait out
    ...    the whole timeout on a perfectly healthy app. See HEALTH_PROBES in
    ...    variables/agents_langgraph.py for that case.
    [Arguments]    ${qs}
    FOR    ${probe}    IN    @{qs}[health_probes]
        Wait Until Keyword Succeeds    ${READINESS_TIMEOUT}    3s
        ...    Health Check Returns 200    ${probe}[0]    ${probe}[1]
    END

Health Check Returns 200
    [Documentation]    One probe attempt. ${path} defaults to `/` because that is
    ...    what the canonical apps serve; pass the app's real path for anything
    ...    that does not route `/`.
    [Arguments]    ${port}    ${path}=/
    GET    http://localhost:${port}${path}    expected_status=200    timeout=10

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

Require Env Var
    [Documentation]    Fail unless ${name} is set to a non-empty value, naming the
    ...    quickstart that needs it. Agent quickstarts need a model provider key,
    ...    and a revoked or unset secret should read as a configuration error here
    ...    rather than as an opaque 401 from the provider several keywords later.
    ...    An empty value fails too: that is what a misconfigured GitHub secret
    ...    looks like, and a bare existence check would wave it through.
    [Arguments]    ${name}    ${quickstart}
    ${value}=    Get Environment Variable    ${name}    default=${EMPTY}
    Should Not Be Empty    ${value}
    ...    msg=${name} is not set, and the ${quickstart} quickstart needs it. Export it before running this suite; in CI it comes from the job's env block.

POST And Expect Field
    [Documentation]    POST ${payload} and assert the status code, plus (when
    ...    ${field} is given) that the named JSON field is present and non-empty.
    ...    Agent responses contain model output, so an exact body comparison is
    ...    impossible; presence and non-emptiness are what remains assertable.
    ...    Where a README documents no response body at all, pass no field and the
    ...    status code is the only assertion — weak on purpose, and honest about it.
    ...    The timeout is 120s rather than the 30s used elsewhere because a model
    ...    call sits inside this request.
    [Arguments]    ${port}    ${path}    ${payload}    ${status}    ${field}=${NONE}
    ${response}=    POST    http://localhost:${port}${path}    json=${payload}
    ...    expected_status=${status}    timeout=120
    ${body}=    Set Variable    ${response.json()}
    IF    $field is not None
        Dictionary Should Contain Key    ${body}    ${field}
        ...    msg=POST ${path} returned no "${field}" field.\nBody: ${body}
        Should Not Be Empty    ${body}[${field}]
        ...    msg=POST ${path} returned an empty "${field}".\nBody: ${body}
    END
    RETURN    ${body}

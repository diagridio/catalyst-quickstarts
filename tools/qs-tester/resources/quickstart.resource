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
    # `${status}` is converted to a string before it reaches RequestsLibrary.
    # RequestsLibrary raises InvalidExpectedStatus for any non-string
    # expected_status (SessionKeywords._check_status: `if not
    # is_string_type(expected_status): raise`), and an agent suite reads its status
    # from `${request}[status]` in a Python data module, where 200 is a number.
    # The canonical suites pass a Robot literal, which is already a string, which
    # is why this only ever broke the agent suites — and why every test in
    # resources/tests/keywords.robot passed while they could not.
    ${status}=      Convert To String    ${status}
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
    # See POST And Expect for why this conversion is here.
    ${status}=      Convert To String    ${status}
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

POST And Expect The App To Exit
    [Documentation]    POST ${payload} and assert the request did NOT complete,
    ...    because the app killed its own process while handling it.
    ...
    ...    `agents/microsoft-dotnet` documents exactly this: "Call
    ...    `step_two_compare` — crashes before completing (process exits)", and of
    ...    the documented curl, "The process exits — this is expected". There is no
    ...    status code to assert, so the assertion is the absence of a response —
    ...    but only when the cause is the app dying.
    ...
    ...    Three outcomes, and two of them must fail:
    ...
    ...    - the connection drops -> PASS. The app exited mid-response, which is
    ...      the documented behaviour.
    ...    - a status code comes back -> FAIL. The crash silently stopped
    ...      happening. Not hypothetical: `Program.cs` sat committed with
    ...      `//Environment.Exit(1);` commented out, so on a fresh clone the
    ...      documented crash demo did nothing. An assertion that accepted a
    ...      response would have shipped that green.
    ...    - the request times out -> FAIL, and distinctly. A hang is not a crash;
    ...      it is the shape of Catalyst's attach window (see
    ...      `Wait Until Catalyst Attached`), and this quickstart has no attach
    ...      gate, so a hang is a live possibility. Reporting one as "crashed"
    ...      would hide it behind an assertion that looks satisfied.
    ...
    ...    ${timeout} is what separates the last two: it must be longer than the
    ...    app needs to reach its crash, and shorter than you are willing to wait
    ...    on a hang. resources/tests/crash_assertion.robot tests all three.
    [Arguments]    ${port}    ${path}    ${payload}    ${timeout}=120
    ${outcome}    ${result}=    Run Keyword And Ignore Error
    ...    POST    http://localhost:${port}${path}    json=${payload}
    ...    expected_status=anything    timeout=${timeout}
    IF    '${outcome}' == 'PASS'
        Fail    POST ${path} completed with status ${result.status_code}, but this quickstart documents the app exiting mid-request. The crash is not happening. Body: ${result.text}
    END
    # ReadTimeout is the hang, not the crash. Rejected explicitly rather than
    # lumped in with every other failure, so a hung run cannot read as a pass.
    ${timed_out}=    Evaluate    'ReadTimeout' in $result or 'Read timed out' in $result
    IF    ${timed_out}
        Fail    POST ${path} did not answer within ${timeout}s and did not drop the connection either. That is a hang, not the documented crash — most likely Catalyst's attach window. (${result})
    END
    Should Contain    ${result}    ConnectionError
    ...    msg=POST ${path} failed, but not by the app exiting: the documented crash drops the connection. (${result})

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
    # See POST And Expect for why this conversion is here. This is the keyword the
    # agent suites actually call, so this is where the missing conversion showed up
    # as `InvalidExpectedStatus: 200` on a live run.
    ${status}=      Convert To String    ${status}
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

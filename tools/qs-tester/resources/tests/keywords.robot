*** Comments ***
Tests for the keywords the agent-family suites depend on. Needs no Catalyst
project, no credentials and no network: the HTTP assertions run against
echo_server.py on localhost. Runs in CI's lint job alongside smoke.robot.

*** Settings ***
Resource        ../catalyst.resource
Resource        ../quickstart.resource
Library         OperatingSystem
Library         Process
Suite Setup     Start Echo Server
Suite Teardown  Stop Process Tree    echo

*** Variables ***
${ECHO_PORT}    8099

*** Test Cases ***
Require Env Var Fails When The Variable Is Absent
    Remove Environment Variable    QS_TESTER_FAKE_KEY
    ${status}=    Run Keyword And Return Status
    ...    Require Env Var    QS_TESTER_FAKE_KEY    fake
    Should Be Equal    ${status}    ${False}

Require Env Var Passes When The Variable Is Set
    Set Environment Variable    QS_TESTER_FAKE_KEY    sk-not-a-real-key
    Require Env Var    QS_TESTER_FAKE_KEY    fake
    [Teardown]    Remove Environment Variable    QS_TESTER_FAKE_KEY

Require Env Var Fails When The Variable Is Set But Empty
    # An empty key is what a misconfigured GitHub secret actually looks like:
    # the env var exists, so a plain existence check would pass and the failure
    # would surface later as an opaque 401 from the model provider.
    Set Environment Variable    QS_TESTER_FAKE_KEY    ${EMPTY}
    ${status}=    Run Keyword And Return Status
    ...    Require Env Var    QS_TESTER_FAKE_KEY    fake
    Should Be Equal    ${status}    ${False}
    [Teardown]    Remove Environment Variable    QS_TESTER_FAKE_KEY

POST And Expect Field Passes On A Present Non-Empty Field
    ${body}=    POST And Expect Field    ${ECHO_PORT}    /full    ${{ {'task': 'x'} }}    200    result
    Should Be Equal    ${body}[result]    some text

POST And Expect Field Fails When The Field Is Missing
    ${status}=    Run Keyword And Return Status
    ...    POST And Expect Field    ${ECHO_PORT}    /none    ${{ {'task': 'x'} }}    200    result
    Should Be Equal    ${status}    ${False}

POST And Expect Field Fails When The Field Is Empty
    # The whole point of the keyword: a 200 with an empty field means the agent
    # produced nothing, which must not read as success.
    ${status}=    Run Keyword And Return Status
    ...    POST And Expect Field    ${ECHO_PORT}    /empty    ${{ {'task': 'x'} }}    200    result
    Should Be Equal    ${status}    ${False}

POST And Expect Field Skips The Field Check When No Field Is Named
    # Agent quickstarts whose README documents no response body assert the
    # status code only, until a live run reveals the real shape.
    ${body}=    POST And Expect Field    ${ECHO_PORT}    /none    ${{ {'task': 'x'} }}    200
    Should Not Be Empty    ${body}

Run Documented Commands Substitutes The Project Name
    ${commands}=    Create List    bash -c 'echo project={project} > ${TEMPDIR}/documented.txt'
    Run Documented Commands    ${commands}    qs-ci-demo-1
    ${content}=    Get File    ${TEMPDIR}/documented.txt
    Should Contain    ${content}    project=qs-ci-demo-1

Run Documented Commands Fails On The First Non-Zero Exit
    ${commands}=    Create List    bash -c 'exit 7'    bash -c 'echo unreachable > ${TEMPDIR}/unreachable.txt'
    Remove File    ${TEMPDIR}/unreachable.txt
    ${status}=    Run Keyword And Return Status
    ...    Run Documented Commands    ${commands}    qs-ci-demo-1
    Should Be Equal    ${status}    ${False}
    # Stopping at the first failure matters: a failed `project create` must not
    # be followed by an `agent create` whose error message hides the real cause.
    File Should Not Exist    ${TEMPDIR}/unreachable.txt

Health Check Returns 200 Defaults To The Path The Canonical Apps Serve
    # No path argument: the default has to stay `/`, because that is what all
    # sixteen canonical implementations route and what their `health_probes`
    # pair every port with.
    Health Check Returns 200    ${ECHO_PORT}

Health Check Returns 200 Fails On A Path The App Does Not Serve
    # The regression this guards: agents/langgraph's app registers no `/`, so a
    # suite that probes `/` there polls a 404 until the readiness timeout expires
    # and then fails on a healthy quickstart. The probe must reject a path the app
    # does not serve, or that mistake is undetectable until a live run.
    ${status}=    Run Keyword And Return Status
    ...    Health Check Returns 200    ${ECHO_PORT}    /not-a-route
    Should Be Equal    ${status}    ${False}

Wait Until Apps Healthy Probes The Path The Quickstart Declares
    # An agent-shaped probe: a path other than `/`. `/dapr/subscribe` is what
    # agents/langgraph declares in HEALTH_PROBES, and the fixture serves it.
    ${qs}=    Create Dictionary    health_probes=${{ [[$ECHO_PORT, '/dapr/subscribe']] }}
    Wait Until Apps Healthy    ${qs}

Wait Until Apps Healthy Fails When The Declared Path Is Not Served
    # And it must fail, rather than pass, when the declared path is wrong — the
    # end-to-end version of the check above, through the keyword the suites call.
    Set Test Variable    ${READINESS_TIMEOUT}    3s
    ${qs}=    Create Dictionary    health_probes=${{ [[$ECHO_PORT, '/not-a-route']] }}
    ${status}=    Run Keyword And Return Status    Wait Until Apps Healthy    ${qs}
    Should Be Equal    ${status}    ${False}

Wait Until Ready Marker Finds A Marker That Arrives Late
    Start Background Process    bash -c 'sleep 2; echo "Uvicorn running on http://127.0.0.1:8005"'
    ...    ${TEMPDIR}/ready.log    readytest
    Wait Until Ready Marker    ${TEMPDIR}/ready.log    Uvicorn running on
    # The background command exits on its own right after printing the marker,
    # so by teardown time it is already gone. Stop Process Tree is documented as
    # unsafe to call on a process that has already exited (see Stop Quickstart,
    # which guards the same call with Run Keyword And Ignore Error for the same
    # reason) — mirror that guard here rather than fail this test's cleanup.
    [Teardown]    Run Keyword And Ignore Error    Stop Process Tree    readytest

Wait Until Ready Marker Fails When The Marker Never Arrives
    Set Test Variable    ${READINESS_TIMEOUT}    3s
    Create File    ${TEMPDIR}/never.log    starting up
    ${status}=    Run Keyword And Return Status
    ...    Wait Until Ready Marker    ${TEMPDIR}/never.log    Uvicorn running on
    Should Be Equal    ${status}    ${False}

*** Keywords ***
Start Echo Server
    Start Background Process    python ${CURDIR}/echo_server.py ${ECHO_PORT}
    ...    ${TEMPDIR}/echo.log    echo
    Wait Until Keyword Succeeds    20s    1s    Health Check Returns 200    ${ECHO_PORT}

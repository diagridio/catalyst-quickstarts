*** Comments ***
Tests for the keywords the agent-family suites depend on. Needs no Catalyst
project, no credentials and no network: the HTTP assertions run against
echo_server.py on localhost. Runs in CI's lint job alongside smoke.robot.

Every negative test here asserts the failure MESSAGE, via Run Keyword And Expect
Error, rather than a boolean from Run Keyword And Return Status. That is not a
style preference. Run Keyword And Return Status returns False for a keyword that
does not exist, so a status-only negative test passes against a keyword that has
been renamed or deleted — it proves the keyword is absent, which is the opposite
of what its name claims. Matching the real message ties the verdict to the
keyword having run and failed for the stated reason. readiness.robot makes the
same point in its own words.

Where a message pattern carries more than the bare failure — an rc, a status
code, "failed after retrying" — that extra text is load-bearing and the comment
on the test says what it pins down. Do not loosen those to `*`.

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
    Run Keyword And Expect Error
    ...    *QS_TESTER_FAKE_KEY is not set, and the fake quickstart needs it*
    ...    Require Env Var    QS_TESTER_FAKE_KEY    fake

Require Env Var Passes When The Variable Is Set
    Set Environment Variable    QS_TESTER_FAKE_KEY    sk-not-a-real-key
    Require Env Var    QS_TESTER_FAKE_KEY    fake
    [Teardown]    Remove Environment Variable    QS_TESTER_FAKE_KEY

Require Env Var Fails When The Variable Is Set But Empty
    # An empty key is what a misconfigured GitHub secret actually looks like:
    # the env var exists, so a plain existence check would pass and the failure
    # would surface later as an opaque 401 from the model provider.
    Set Environment Variable    QS_TESTER_FAKE_KEY    ${EMPTY}
    # The message is the same one the absent case produces — the keyword cannot
    # tell them apart and does not need to. What this test adds is that an
    # existence-only check, which would raise nothing here, fails with
    # "did not occur" instead of passing.
    Run Keyword And Expect Error
    ...    *QS_TESTER_FAKE_KEY is not set, and the fake quickstart needs it*
    ...    Require Env Var    QS_TESTER_FAKE_KEY    fake
    [Teardown]    Remove Environment Variable    QS_TESTER_FAKE_KEY

POST And Expect Field Passes On A Present Non-Empty Field
    ${body}=    POST And Expect Field    ${ECHO_PORT}    /full    ${{ {'task': 'x'} }}    200    result
    Should Be Equal    ${body}[result]    some text

POST And Expect Field Fails When The Field Is Missing
    Run Keyword And Expect Error    *POST /none returned no "result" field*
    ...    POST And Expect Field    ${ECHO_PORT}    /none    ${{ {'task': 'x'} }}    200    result

POST And Expect Field Fails When The Field Is Empty
    # The whole point of the keyword: a 200 with an empty field means the agent
    # produced nothing, which must not read as success.
    Run Keyword And Expect Error    *POST /empty returned an empty "result"*
    ...    POST And Expect Field    ${ECHO_PORT}    /empty    ${{ {'task': 'x'} }}    200    result

POST And Expect Field Accepts An Integer Status From A Data Module
    [Documentation]    The status reaches this keyword as a Python int, because an
    ...    agent suite reads it from `${request}[status]` in its variables module,
    ...    where 200 is written as a number. RequestsLibrary rejects a non-string
    ...    `expected_status` outright (`InvalidExpectedStatus`), so the keyword has
    ...    to coerce.
    ...
    ...    Every other test in this file passes the status as a Robot literal,
    ...    which is already a string — which is exactly why they all passed while
    ...    the real agent suites could not. The int path is the one the suites
    ...    actually take, so it is the one that needs a test.
    ${body}=    POST And Expect Field    ${ECHO_PORT}    /full    ${{ {'task': 'x'} }}
    ...    ${200}    result
    Should Be Equal    ${body}[result]    some text

POST And Expect Accepts An Integer Status From A Data Module
    [Documentation]    Same coercion, same reason. Not currently reached by any
    ...    suite — the canonical ones pass Robot literals — but an agent suite with
    ...    a documented GET is told to use `GET And Expect`, and one with a
    ...    deterministic body would use this, both from `${request}[status]`.
    ${body}=    POST And Expect    ${ECHO_PORT}    /full    ${{ {'task': 'x'} }}    ${200}
    Should Be Equal    ${body}[result]    some text

GET And Expect Accepts An Integer Status From A Data Module
    [Documentation]    Also the only test `GET And Expect` has. It parses the
    ...    response as JSON unconditionally, so it needs a GET route that returns
    ...    a body — the two paths the readiness probe uses answer plain "ok".
    ${body}=    GET And Expect    ${ECHO_PORT}    /order/1    ${200}
    ...    ${{ {'orderId': 1} }}
    Should Be Equal    ${body}[orderId]    ${1}

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
    # rc=7 in the pattern, not a bare glob: it pins the failure to the FIRST
    # command. A keyword that ran both and reported the second would say rc=0 or
    # name the other command.
    Run Keyword And Expect Error    *Command failed (rc=7)*
    ...    Run Documented Commands    ${commands}    qs-ci-demo-1
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
    Run Keyword And Expect Error    *Expected status: 404 != 200*
    ...    Health Check Returns 200    ${ECHO_PORT}    /not-a-route

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
    # "failed after retrying" is part of the pattern on purpose: it proves the
    # keyword POLLED the probe rather than checking it once, which is the whole
    # reason it wraps Health Check Returns 200 in Wait Until Keyword Succeeds.
    Run Keyword And Expect Error
    ...    *failed after retrying for 3 seconds*Expected status: 404 != 200*
    ...    Wait Until Apps Healthy    ${qs}

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
    [Documentation]    A quickstart that never announces itself must fail here
    ...    rather than fall through into the assertions.
    ...
    ...    Asserts the failure MESSAGE, not a status flag. `Run Keyword And Return
    ...    Status` returns False for a keyword that does not exist either, so the
    ...    status-only version of this test passed against a `Wait Until Ready
    ...    Marker` that had been renamed or deleted — it proved the keyword was
    ...    absent or broken, which is the opposite of what it claims. Matching
    ...    `does not contain "<marker>"` ties the verdict to this marker and to
    ...    the keyword really running. Same reason readiness.robot's negative test
    ...    matches `*still answering 500*` instead of `*`.
    Set Test Variable    ${READINESS_TIMEOUT}    3s
    Create File    ${TEMPDIR}/never.log    starting up
    ${before}=    Get Time    epoch
    Run Keyword And Expect Error    *does not contain "Uvicorn running on"*
    ...    Wait Until Ready Marker    ${TEMPDIR}/never.log    Uvicorn running on
    # The keyword's whole reason to exist is that app logging is asynchronous, so
    # it must POLL for the marker rather than read the file once and give up. A
    # single-read implementation would fail this test's error match too, and pass
    # it in milliseconds; only the elapsed time tells the two apart.
    ${elapsed}=    Evaluate    ${{ int(__import__('time').time()) }} - ${before}
    Should Be True    ${elapsed} >= 2
    ...    msg=Wait Until Ready Marker gave up after ${elapsed}s of a 3s timeout; it is reading once instead of polling

Wait Until Catalyst Attached Finds A Probe That Arrives Late
    [Documentation]    The gate's whole job is to keep the suite from triggering
    ...    before Catalyst has attached to the app, so it has to wait rather than
    ...    read the log once and give up.
    Start Background Process
    ...    bash -c 'echo "Uvicorn running on"; sleep 2; echo "INFO: 10.0.85.58:0 - \\"GET /dapr/config HTTP/1.1\\" 404 Not Found"'
    ...    ${TEMPDIR}/attached.log    attachtest
    Wait Until Catalyst Attached    ${TEMPDIR}/attached.log    GET /dapr/config
    [Teardown]    Run Keyword And Ignore Error    Stop Process Tree    attachtest

Wait Until Catalyst Attached Fails When Catalyst Never Probes
    [Documentation]    An app that is up locally but that Catalyst never attaches
    ...    to must fail here, not sail through into the window. Passing vacuously
    ...    is unrecoverable: the first workflow call made too early hangs forever,
    ...    and no retry gets it back — measured 2026-08-27, 12 retries over 181s.
    Set Test Variable    ${READINESS_TIMEOUT}    3s
    Create File    ${TEMPDIR}/unattached.log    Uvicorn running on http://0.0.0.0:8005
    # Match the gate's own message, not a status flag: `Run Keyword And Return
    # Status` returns False for a keyword that does not exist either, so a
    # status-only assertion passes against a gate nobody has written yet.
    Run Keyword And Expect Error    *Catalyst never probed the app*
    ...    Wait Until Catalyst Attached    ${TEMPDIR}/unattached.log    GET /dapr/config

Wait Until Apps Connected Is Bounded By CONNECT_TIMEOUT Not READINESS_TIMEOUT
    [Documentation]    The connection gate needs its own budget. It legitimately
    ...    takes 32-36s against real Catalyst, while the two waits that follow it
    ...    take about five seconds each — so a mutation run that shortens
    ...    ${READINESS_TIMEOUT} to make a mutated assertion give up quickly used to
    ...    starve this gate instead, and the run died here having never reached the
    ...    mutation. `check_mutation.py` correctly rejected the result (the target
    ...    keyword was NOT RUN), but only after a Catalyst project had been spent.
    ...
    ...    So: shortening READINESS_TIMEOUT must NOT shorten this keyword.
    Set Test Variable    ${READINESS_TIMEOUT}    2s
    Set Test Variable    ${CONNECT_TIMEOUT}    20s
    # The line is written by Robot into a file and catted by the background
    # process, rather than echoed inline: the connection line contains double
    # quotes, and getting them through Robot escaping AND shell quoting intact
    # is its own bug — one that would make this test fail for a reason having
    # nothing to do with the timeout it is testing.
    Create File    ${TEMPDIR}/connect-line.txt
    ...    Connected App ID "probe-app" to http://localhost:8099
    Create File    ${TEMPDIR}/connect.log    ${EMPTY}
    Start Background Process
    ...    bash -c 'sleep 6; cat ${TEMPDIR}/connect-line.txt'
    ...    ${TEMPDIR}/connect.log    connecttest
    ${qs}=    Create Dictionary    connected_apps=${{ [['probe-app', 8099]] }}
    # Six seconds is well past READINESS_TIMEOUT and well inside CONNECT_TIMEOUT,
    # so this passes only if the keyword reads the latter.
    Wait Until Apps Connected    ${qs}    ${TEMPDIR}/connect.log
    [Teardown]    Run Keyword And Ignore Error    Stop Process Tree    connecttest

Start Quickstart Records The Connected App IDs For Teardown
    # Regression test for a merge hazard: Start Quickstart reads
    # ${qs}[connected_apps] to remember which app connections Stop Quickstart must
    # release. An agent data module that omits the key fails here at launch, and a
    # --dryrun cannot catch it because the failure is a runtime dict access.
    ${qs}=    Create Dictionary
    ...    run=bash -c 'echo started; sleep 5'
    ...    dir=${TEMPDIR}
    ...    connected_apps=${{ [['probe-app', 8099]] }}
    Start Quickstart    ${qs}    qs-ci-demo-1    ${TEMPDIR}/connected.log
    Should Be Equal    ${CONNECTED_APP_IDS}[0]    probe-app
    [Teardown]    Run Keyword And Ignore Error    Stop Process Tree    apps

*** Keywords ***
Start Echo Server
    Start Background Process    python ${CURDIR}/echo_server.py ${ECHO_PORT}
    ...    ${TEMPDIR}/echo.log    echo
    Wait Until Keyword Succeeds    20s    1s    Health Check Returns 200    ${ECHO_PORT}

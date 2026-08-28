*** Comments ***
Tests the crash assertion in quickstart.resource against crashing_server.py,
which reproduces `agents/microsoft-dotnet`'s documented trigger without a
Catalyst project or credentials. Runs in seconds; CI's lint job runs it.

That quickstart's trigger deliberately kills its own process — "Call
`step_two_compare` — crashes before completing (process exits)" — so there is no
status code to assert. What the suite must assert is that the request did not
complete AND that it failed for the documented reason.

The two negative tests are the point of the file, and they guard opposite
mistakes:

  A normal 200 must FAIL the assertion. That is the crash having silently
  stopped happening, which is not hypothetical: Program.cs sat committed with
  `//Environment.Exit(1);` commented out, so on a fresh clone the documented
  crash demo did nothing. An assertion that accepted a 200 would ship that green.

  A hang must FAIL the assertion too. A hang is not a crash — it is the shape of
  Catalyst's attach window, and `agents/microsoft-dotnet` has no attach gate, so
  it is a live possibility there. Accepting it would hide a hung run behind an
  assertion that looks satisfied.

*** Settings ***
Resource        ../quickstart.resource
Resource        ../process.resource
Library         OperatingSystem
Library         Process
Test Teardown   Run Keyword And Ignore Error    Stop Process Tree    crasher

*** Variables ***
${PORT}         5097
${SERVER}       ${CURDIR}/crashing_server.py

*** Test Cases ***
Crash Assertion Passes When The App Exits Mid Request
    [Documentation]    The documented flow: the app prints its tool markers and
    ...    then dies without answering, so the client sees the connection drop.
    Start Crashing Server
    ${payload}=    Create Dictionary    prompt=Find a venue in Austin for a company gala
    POST And Expect The App To Exit    ${PORT}    /crash    ${payload}    timeout=20
    # The keyword returning is not enough: prove the app really did die, so a
    # keyword that returned for the wrong reason cannot pass this test.
    Wait Until Log Contains    ${TEMPDIR}/crashing-server.log
    ...    >>> TOOL 2: Comparing venues...    timeout=10s

Crash Assertion Fails When The App Answers Normally
    [Documentation]    The regression this exists for. A 200 means the crash did
    ...    not happen, which is a broken quickstart, not a passing test.
    Start Crashing Server
    ${payload}=    Create Dictionary    prompt=Find a venue in Austin for a company gala
    # Match the keyword's own message, not `*`: a bare glob also matches "No
    # keyword with name ... found", so this test would pass on a keyword that
    # does not exist.
    Run Keyword And Expect Error    *completed with status 200*
    ...    POST And Expect The App To Exit    ${PORT}    /ok    ${payload}    timeout=20

Crash Assertion Fails When The Request Hangs Instead
    [Documentation]    A hang is not a crash. Catalyst's attach window makes a
    ...    workflow call hang forever, and this suite has no attach gate, so the
    ...    assertion must not accept a timeout as the documented exit.
    Start Crashing Server
    ${payload}=    Create Dictionary    prompt=Find a venue in Austin for a company gala
    Run Keyword And Expect Error    *did not answer within*
    ...    POST And Expect The App To Exit    ${PORT}    /hang    ${payload}    timeout=3

*** Keywords ***
Start Crashing Server
    Start Background Process    python3 ${SERVER} ${PORT}
    ...    ${TEMPDIR}/crashing-server.log    crasher
    Wait Until Log Contains    ${TEMPDIR}/crashing-server.log    listening on ${PORT}
    ...    timeout=20s

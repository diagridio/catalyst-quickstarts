*** Comments ***
Tests the two paths through Stop Quickstart that never release an app connection,
because both of them run on every nightly leg and neither is covered by the
suites themselves.

Stop Quickstart is a Test Teardown, so a keyword error here does not just skip a
release — it turns a passing quickstart into a failing one, for all four
languages at once. Needs no credentials: if either path wrongly reached for the
CLI, `Release App Connection` would assert on output it never got.

*** Settings ***
Resource    ../catalyst.resource
Library     ../../variables/quickstarts.py

*** Variables ***
# A name no run may ever contact. Reaching the CLI with this is the failure.
${UNCONTACTABLE}    no-such-project-should-never-be-contacted

*** Test Cases ***
Teardown Before A Launch Releases Nothing
    [Documentation]    A build failure fails the test before Start Quickstart has
    ...    run, and teardown still executes. The empty default for
    ...    ${CONNECTED_APP_IDS} is what keeps that a no-op instead of an error.
    Should Be Empty    ${CONNECTED_APP_IDS}
    Stop Quickstart    ${UNCONTACTABLE}

An Api With No Connected Apps Releases Nothing
    [Documentation]    state and workflow set appPort 0, so no app ID of theirs has
    ...    a local connection and Start Quickstart records an empty list. Robot
    ...    accepts `Set Test Variable  @{name}` with zero values; if it ever stops
    ...    doing so, every state and workflow teardown breaks and this fails first.
    ${qs}=    Get Quickstart    state    python
    Should Be Empty    ${qs}[connected_apps]
    ${app_ids}=    Evaluate    [app[0] for app in $qs["connected_apps"]]
    Set Test Variable    @{CONNECTED_APP_IDS}    @{app_ids}
    Should Be Empty    ${CONNECTED_APP_IDS}
    Stop Quickstart    ${UNCONTACTABLE}

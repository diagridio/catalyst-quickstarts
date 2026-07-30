*** Settings ***
Resource    ../process.resource
Library     OperatingSystem

*** Test Cases ***
Background Process Writes To Its Log And Can Be Stopped
    Start Background Process    bash -c 'for i in 1 2 3 4 5 6 7 8 9; do echo tick $i; sleep 1; done'
    ...    ${TEMPDIR}/smoke.log    ticker
    Wait Until Log Contains    ${TEMPDIR}/smoke.log    tick 2    timeout=20s
    ${result}=    Stop Process Tree    ticker
    Should Not Be Equal    ${result}    ${None}

Stale Log Content Is Truncated On Start
    Create File    ${TEMPDIR}/stale.log    tick 99
    Start Background Process    bash -c 'sleep 5'    ${TEMPDIR}/stale.log    sleeper
    Log Should Not Contain Stale    ${TEMPDIR}/stale.log    tick 99
    Stop Process Tree    sleeper

Run And Expect RC Zero Fails On Non-Zero Exit
    ${status}=    Run Keyword And Return Status
    ...    Run And Expect RC Zero    bash -c 'exit 3'
    Should Be Equal    ${status}    ${False}

Nested Children Are Killed When SIGINT Is Ignored
    # A parent that traps SIGINT, with a grandchild in its OWN process group
    # (`set -m` turns on job control so the backgrounded job gets a fresh
    # pgid instead of inheriting the parent's). Without that, the grandchild
    # would share the parent's pgid, and the *unrelated* SIGKILL that
    # `Wait For Process ... on_timeout=kill` sends to that pgid as a last
    # resort would reap it too (SIGKILL, unlike SIGINT, cannot be ignored) —
    # letting this test pass without ever touching the PID-tree walk. Putting
    # the grandchild in its own group is what makes the PID-tree fallback the
    # *only* thing that can reach it, exactly the diagrid dev run situation.
    Start Background Process
    ...    bash -c 'set -m; trap "" INT; bash -c "sleep 300" & echo started; wait'
    ...    ${TEMPDIR}/nested.log    nested
    Wait Until Log Contains    ${TEMPDIR}/nested.log    started    timeout=20s
    ${pid}=    Get Process Id    nested
    ${kids}=    Run Process    bash    -c    pgrep -P ${pid} | head -1
    ${grandchild}=    Set Variable    ${kids.stdout.strip()}
    # A test that cannot capture a real grandchild PID cannot prove anything
    # about killing it — fail loudly here instead of letting the aliveness
    # check below pass vacuously on an empty/garbage PID.
    Should Not Be Empty    ${grandchild}
    ...    msg=Could not capture the grandchild PID via 'pgrep -P ${pid}'; test is inconclusive
    Stop Process Tree    nested    timeout=5s
    # The grandchild must be gone, not orphaned. Check the exit status of
    # `kill -0` directly (0 = still alive, non-zero = no such process) rather
    # than matching on printed text, so there is no way to misparse the result.
    ${check}=    Run Process    bash    -c    kill -0 ${grandchild} 2>/dev/null; echo $?
    Should Be Equal As Integers    ${check.stdout.strip()}    1
    ...    msg=Grandchild process ${grandchild} is still alive after Stop Process Tree

*** Keywords ***
Log Should Not Contain Stale
    [Arguments]    ${logfile}    ${text}
    ${content}=    Get File    ${logfile}
    Should Not Contain    ${content}    ${text}

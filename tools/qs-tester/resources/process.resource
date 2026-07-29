*** Comments ***
Process lifecycle keywords. Deliberately knows nothing about Catalyst, HTTP, or
the quickstarts — it is the piece most likely to need debugging in isolation.

The teardown logic is ported from dapr-university-instruqt's
tools/track-tester/resources/dapr.resource. Do not simplify it; the comments
explain why each layer exists.

*** Settings ***
Library    Process
Library    OperatingSystem

*** Keywords ***
Start Background Process
    [Documentation]    Launch ${command} without blocking, merging stdout and stderr
    ...    into ${logfile}. ${alias} lets later keywords refer to the process.
    [Arguments]    ${command}    ${logfile}    ${alias}    ${cwd}=${EMPTY}
    # Robot's Process library already truncates any stdout= path it opens
    # (open(path, "w")), so this is belt-and-braces against that undocumented
    # behaviour changing — not the thing that currently prevents a stale log
    # from satisfying an assertion.
    Create File    ${logfile}    ${EMPTY}
    ${handle}=    Start Process    ${command}    shell=True    alias=${alias}
    ...    cwd=${cwd}    stdout=${logfile}    stderr=STDOUT
    RETURN    ${handle}

Wait Until Log Contains
    [Documentation]    Poll ${logfile} every 2s until it contains ${text}.
    ...    App logging is asynchronous with respect to the HTTP response, so
    ...    every log assertion has to be a wait rather than a single read.
    [Arguments]    ${logfile}    ${text}    ${timeout}=60s
    Wait Until Keyword Succeeds    ${timeout}    2s
    ...    Log Should Contain    ${logfile}    ${text}

Log Should Contain
    [Arguments]    ${logfile}    ${text}
    ${content}=    Get File    ${logfile}
    Should Contain    ${content}    ${text}
    ...    msg=Log ${logfile} does not contain "${text}"

Run And Expect RC Zero
    [Documentation]    Run ${command} to completion and fail unless it exits 0.
    ...    Used for build commands, which are slow: default timeout 600s.
    [Arguments]    ${command}    ${cwd}=${EMPTY}    ${timeout}=600s
    # Omit stdout= so Robot captures to a managed temp file it cleans up.
    # Passing stdout=PIPE would write a stray file literally named "PIPE".
    ${result}=    Run Process    ${command}    shell=True    cwd=${cwd}
    ...    stderr=STDOUT    timeout=${timeout}
    Should Be Equal As Integers    ${result.rc}    0
    ...    msg=Command failed (rc=${result.rc}): ${command}\n${result.stdout}
    RETURN    ${result}

Stop Process Tree
    [Documentation]    Send SIGINT (the README's CTRL+C) to the process group, then
    ...    escalate to a PID-tree SIGKILL if anything survives.
    [Arguments]    ${alias}    ${timeout}=15s
    # group=True so the CLI *and* the app it launched both receive SIGINT, like
    # Ctrl+C in a terminal. Signalling the single PID leaves children unsignalled
    # on Linux and the CLI never exits.
    Send Signal To Process    SIGINT    ${alias}    group=True
    # Do not rely on Robot's on_timeout=kill: it force-kills only the tracked
    # top-level PID. The CLI, its sidecar and the app can survive as orphans,
    # still holding ports 5001/5002 and corrupting the next suite in the leg.
    ${result}=    Wait For Process    ${alias}    timeout=${timeout}    on_timeout=continue
    IF    $result is None
        # A group signal is not enough here. `diagrid dev run` and the app each
        # detach into new process groups, and for the three python quickstarts we
        # launch through a `bash -c '. .venv/bin/activate && ...'` wrapper, so the
        # descendants sit in groups the wrapper's own group can never reach. The
        # only reliable fallback is to walk the real OS parent/child PID tree from
        # the tracked PID, to any depth, and SIGKILL every descendant directly.
        ${pid}=    Get Process Id    ${alias}
        Run Process    bash    -c
        ...    kill_tree() { for c in $(pgrep -P "$1" 2>/dev/null); do kill_tree "$c"; done; kill -9 "$1" 2>/dev/null; }; kill_tree ${pid}
        ${result}=    Wait For Process    ${alias}    timeout=10s    on_timeout=kill
    END
    RETURN    ${result}

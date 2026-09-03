*** Comments ***
Process lifecycle keywords. Deliberately knows nothing about Catalyst, HTTP, or
the quickstarts — it is the piece most likely to need debugging in isolation.

The teardown logic is ported from dapr-university-instruqt's
tools/track-tester/resources/dapr.resource. Do not simplify it; the comments
explain why each layer exists.

*** Settings ***
Library    Process
Library    OperatingSystem

*** Variables ***
# Both are overridable with `robot --variable`, which is how the mutation check
# makes a run it expects to fail give up in seconds instead of minutes. The
# defaults are the values these waits used before they were parameterised: do not
# change them, or every existing suite's timing changes with them.
${MARKER_TIMEOUT}       60s
${READINESS_TIMEOUT}    180s
# The connection gate's own budget, deliberately NOT ${READINESS_TIMEOUT}. It
# waits on Catalyst establishing the dev tunnel, measured at 32-36s against a
# real project, while every other wait governed by ${READINESS_TIMEOUT} finishes
# in about five seconds. A mutation run shortens ${READINESS_TIMEOUT} so the
# mutated assertion gives up quickly; when this gate shared that variable, the
# override starved it instead and the run died before reaching the mutation —
# `check_mutation.py` rejected the result as proving nothing, but only after a
# Catalyst project had been spent. Same default as before the split, so no
# existing suite's timing changes.
${CONNECT_TIMEOUT}      180s

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
    [Arguments]    ${logfile}    ${text}    ${timeout}=${MARKER_TIMEOUT}
    Wait Until Keyword Succeeds    ${timeout}    2s
    ...    Log Should Contain    ${logfile}    ${text}

Log Should Contain
    [Arguments]    ${logfile}    ${text}
    ${content}=    Get File    ${logfile}
    Should Contain    ${content}    ${text}
    ...    msg=Log ${logfile} does not contain "${text}"

Log Should Not Contain
    [Documentation]    Assert ${text} is absent from ${logfile}. Deliberately a single
    ...    read and not a wait: an absence cannot be polled for, and the caller is
    ...    expected to have already waited for a later marker that orders the read.
    [Arguments]    ${logfile}    ${text}
    ${content}=    Get File    ${logfile}
    Should Not Contain    ${content}    ${text}
    ...    msg=Log ${logfile} unexpectedly contains "${text}"

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
        # detach into new process groups, and the python quickstarts add another
        # layer: the documented command is `uv run diagrid dev run`, so uv sits
        # between us and the CLI, and the descendants end up in groups our own
        # group can never reach. The only reliable fallback is to walk the real OS
        # parent/child PID tree from the tracked PID, to any depth, and SIGKILL
        # every descendant directly. Do NOT delete this as dead code.
        ${pid}=    Get Process Id    ${alias}
        Run Process    bash    -c
        ...    kill_tree() { for c in $(pgrep -P "$1" 2>/dev/null); do kill_tree "$c"; done; kill -9 "$1" 2>/dev/null; }; kill_tree ${pid}
        ${result}=    Wait For Process    ${alias}    timeout=10s    on_timeout=kill
    END
    RETURN    ${result}

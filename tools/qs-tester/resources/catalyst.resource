*** Comments ***
Launching and stopping a quickstart through the `diagrid dev run` command its
README documents, plus the readiness marker that command emits.

*** Settings ***
Library     Collections
Library     String
Resource    process.resource

*** Variables ***
# App IDs whose local app connection Stop Quickstart has to release. Start
# Quickstart overwrites this per test; the empty default keeps teardown a no-op
# when a test fails before the launch (a build failure still runs teardown).
@{CONNECTED_APP_IDS}    @{EMPTY}

*** Keywords ***
Start Quickstart
    [Documentation]    Launch the quickstart's documented run command in the
    ...    background under alias `apps`, substituting the ephemeral project name.
    [Arguments]    ${qs}    ${project}    ${logfile}
    ${command}=    Resolve Project In Command    ${qs}[run]    ${project}
    Log    Starting: ${command}    console=True
    # Record the app IDs for teardown. Set Test Variable, not a local: Stop
    # Quickstart runs as Test Teardown, where this keyword's locals are gone.
    ${app_ids}=    Evaluate    [app[0] for app in $qs["connected_apps"]]
    Set Test Variable    @{CONNECTED_APP_IDS}    @{app_ids}
    ${handle}=    Start Background Process    ${command}    ${logfile}    apps
    ...    cwd=${qs}[dir]
    RETURN    ${handle}

Resolve Project In Command
    [Documentation]    Substitute the ephemeral project name for the {project}
    ...    placeholder. Deliberately NOT named `Format String` — the String library
    ...    already has a keyword by that name and the collision would be silent.
    [Arguments]    ${template}    ${project}
    ${result}=    Replace String    ${template}    {project}    ${project}
    RETURN    ${result}

Wait Until Apps Connected
    [Documentation]    Wait for `Connected App ID "<id>" to http://localhost:<port>` for
    ...    each app that has a local app connection. Apps with appPort 0 or no appPort
    ...    (workflow, state, invocation's client) never emit this line, so
    ...    ${qs}[connected_apps] is empty for those and this keyword does nothing.
    ...    The `http://` scheme is part of the line the CLI prints — matching on the
    ...    schemeless `to localhost:<port>` silently waits out the full timeout.
    ...
    ...    Bounded by ${CONNECT_TIMEOUT}, not ${READINESS_TIMEOUT}: this gate takes
    ...    32-36s against real Catalyst while the waits after it take about five
    ...    seconds, so a mutation run that shortens ${READINESS_TIMEOUT} must not
    ...    shorten this one. See the variable's comment in process.resource.
    [Arguments]    ${qs}    ${logfile}
    FOR    ${app}    IN    @{qs}[connected_apps]
        ${app_id}=    Set Variable    ${app}[0]
        ${port}=    Set Variable    ${app}[1]
        Wait Until Log Contains    ${logfile}
        ...    Connected App ID "${app_id}" to http://localhost:${port}    timeout=${CONNECT_TIMEOUT}
    END

Stop Quickstart
    [Documentation]    CTRL+C equivalent, then release the local app connections.
    ...    Safe to call when the process is already gone.
    ...
    ...    SIGINT alone is not enough: the CLI prints `Disconnected App ID "<id>"`
    ...    and then tells you the dev session is still active, and the app ID keeps
    ...    a `trust.diagrid.io` app endpoint pointing at a tunnel that no longer
    ...    exists. Invocations to a project in that state fail with the same
    ...    `app is not in a healthy state` 500 as a genuinely broken app, which
    ...    makes the next run's diagnosis harder than it needs to be.
    [Arguments]    ${project}
    Run Keyword And Ignore Error    Stop Process Tree    apps
    FOR    ${app_id}    IN    @{CONNECTED_APP_IDS}
        Release App Connection    ${app_id}    ${project}
    END

Release App Connection
    [Documentation]    `diagrid dev stop` for one app ID, asserting it actually
    ...    disconnected.
    ...
    ...    Two CLI behaviours (v1.36.0) force both the flag choice and the
    ...    assertion. `--project` on its own — what this used to run — prints
    ...    "Dev config file or App ID is required" and does nothing. `-f
    ...    <dev-config>` cannot parse the quickstarts' own dev config files at all:
    ...    their `command:` is a YAML list, `dev stop` expects a string, and it
    ...    fails with "Json: cannot unmarshal number into Go struct field
    ...    App.Apps.RunConfig.Command of type string". `--app-id` is the one form
    ...    that works. Every one of those failures exits 0, so an rc check proves
    ...    nothing and the success line has to be asserted instead.
    [Arguments]    ${app_id}    ${project}
    ${result}=    Run Process    diagrid dev stop --app-id ${app_id} --project ${project}
    ...    shell=True    stderr=STDOUT    timeout=120s
    Should Contain    ${result.stdout}    disconnected
    ...    msg=Could not release the app connection for '${app_id}' in ${project} (rc=${result.rc}): ${result.stdout}

Run Documented Commands
    [Documentation]    Run an ordered list of documented commands, substituting the
    ...    ephemeral project name, and stop at the first non-zero exit.
    ...
    ...    Agent-family READMEs document their own provisioning (`project create`
    ...    with per-quickstart managed-service flags such as
    ...    `--enable-managed-workflow --deploy-managed-kv --deploy-managed-pubsub`,
    ...    plus `--wait --use`, then `agent create`, and sometimes `app create` and
    ...    `apply -f`), so the suite runs those commands verbatim instead of an
    ...    invented equivalent. The flags are per-quickstart data — see the
    ...    harness README's "Two kinds of quickstart". Stopping at the first failure keeps the real
    ...    cause visible: an `agent create` that runs after a failed `project
    ...    create` fails for a second, more confusing reason.
    ...
    ...    The 600s default matches Run And Expect RC Zero's: `project create
    ...    --wait` blocks until managed services are ready.
    [Arguments]    ${commands}    ${project}    ${cwd}=${EMPTY}    ${timeout}=600s
    FOR    ${template}    IN    @{commands}
        ${resolved}=    Resolve Project In Command    ${template}    ${project}
        ${command}=     Make Command Non Interactive    ${resolved}
        Log    Documented command: ${command}    console=True
        Run And Expect RC Zero    ${command}    cwd=${cwd}    timeout=${timeout}
    END

Make Command Non Interactive
    [Documentation]    Add the approval flag to a documented `diagrid project
    ...    delete`, which otherwise prompts and waits forever for an answer
    ...    nothing sends.
    ...
    ...    This is the second sanctioned deviation from running documented
    ...    commands verbatim, and it exists for the same reason as the first:
    ...    `diagrid login` blocks on a browser prompt, so `ci/login.sh` passes
    ...    `--api-key`. Neither README is wrong — a human running the quickstart
    ...    answers the prompt — but a suite cannot.
    ...
    ...    Observed 2026-08-28 on agents/microsoft-dotnet: the documented
    ...    teardown printed `WARNING: Deleting the following projects will delete
    ...    all associated resources` and then sat until Robot SIGTERMed it at the
    ...    600s timeout (`rc=-15`), in BOTH the green and mutated runs — twenty
    ...    minutes of a verify-live run spent waiting on a prompt. It failed
    ...    silently because `Clean Up Quickstart` wraps teardown in
    ...    `Run Keyword And Ignore Error`, and the project survived only because
    ...    `ci/teardown-project.sh` passes `--yes` itself. Applies to
    ...    `agents/spring-ai/event-planner` too, which documents the same command;
    ...    `agents/langgraph` documents no cleanup and never hit it.
    ...
    ...    Confirmed live the same day: with the flag added, the same teardown
    ...    takes 1.37s and the documented `project delete` really deletes the
    ...    project — checked with `diagrid project list` after a run with no
    ...    safety-net script. The whole MAF suite went from ~11 minutes to 53s.
    ...
    ...    Deliberately narrow. Only `project delete` is rewritten, and only when
    ...    neither approval flag is already present, so a README that documents
    ...    the non-interactive form is left exactly as written. Every other
    ...    documented command runs verbatim, which is the harness's premise.
    ...    doc-sync still compares the data module's untouched string against the
    ...    README, so this deviation cannot hide drift.
    [Arguments]    ${command}
    ${is_delete}=    Evaluate    $command.startswith('diagrid project delete')
    ${approved}=     Evaluate    '--yes' in $command.split() or '--approve' in $command.split()
    IF    ${is_delete} and not ${approved}
        RETURN    ${command} --yes
    END
    RETURN    ${command}

Wait Until Ready Marker
    [Documentation]    Wait for a per-quickstart readiness string in the captured
    ...    `diagrid dev run` output. Agent quickstarts do not emit the canonical
    ...    `Connected App ID "<id>" to http://localhost:<port>` line that
    ...    Wait Until Apps Connected waits for; langgraph prints `Uvicorn running
    ...    on`, and the marker is a property of the framework, not the language.
    [Arguments]    ${logfile}    ${marker}
    Wait Until Log Contains    ${logfile}    ${marker}    timeout=${READINESS_TIMEOUT}

Wait Until Catalyst Attached
    [Documentation]    Wait for the first sign that Catalyst has attached to the
    ...    app and is probing it back through the dev tunnel — an INBOUND request
    ...    in the app's own captured output. This is the last readiness gate an
    ...    agent suite passes, and the only one that says anything about Catalyst.
    ...
    ...    Why it exists. `Connected App ID "<id>" to http://localhost:<port>`,
    ...    `Uvicorn running on ...` and a 200 from the health probe are all
    ...    satisfied by the LOCAL process. For a second or three afterwards,
    ...    Catalyst has not attached, and a workflow call made in that window does
    ...    not fail — it hangs, and it never recovers. Measured 2026-08-27 on
    ...    agents/langgraph: a POST at readiness+0s hung for the full client
    ...    timeout with no workflow instance ever created, and TWELVE retries over
    ...    181s never got it back. The first call into the window poisons the app's
    ...    workflow client permanently, which is why this gate has to run BEFORE
    ...    the first request rather than wrap it in a retry. Gated on this marker,
    ...    the same request answered 200 in ~1s on three consecutive runs.
    ...
    ...    Why an inbound request is the signal: Catalyst fetches `/dapr/config`
    ...    (and probes `/`) through the tunnel once it attaches, and the app logs
    ...    those the same way it logs any request. Verified against the alternative
    ...    that looked more obvious and is VACUOUS: probing the app's own
    ...    `GET /agent/run/{workflow_id}` answers 404 in 71ms at readiness+0 while
    ...    the POST beside it hangs, because the two issue different RPCs
    ...    (`GetInstance` vs `StartInstance`) and only the write path is late.
    ...    Catalyst's own workflow HTTP API answers 202 in that window too, and its
    ...    worker executes work items one second in — so neither of those is a
    ...    usable signal either. Do not "improve" this into an active probe.
    ...
    ...    The marker is per quickstart, like READY_MARKERS: it is whatever that
    ...    app's logging makes visible for an inbound request, a property of the
    ...    framework rather than of Catalyst. An app that logs no inbound request
    ...    has no marker here, and its suite runs unguarded — see
    ...    CATALYST_PROBE_MARKERS in the agent data modules.
    [Arguments]    ${logfile}    ${marker}
    ${status}    ${error}=    Run Keyword And Ignore Error
    ...    Wait Until Log Contains    ${logfile}    ${marker}    timeout=${READINESS_TIMEOUT}
    IF    '${status}' == 'FAIL'
        Fail    Catalyst never probed the app: "${marker}" did not appear in ${logfile} within ${READINESS_TIMEOUT}. The app is up locally but Catalyst has not attached, and triggering now would hang forever. (${error})
    END

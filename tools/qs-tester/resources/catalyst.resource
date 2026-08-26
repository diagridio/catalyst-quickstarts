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
    [Arguments]    ${qs}    ${logfile}
    FOR    ${app}    IN    @{qs}[connected_apps]
        ${app_id}=    Set Variable    ${app}[0]
        ${port}=    Set Variable    ${app}[1]
        Wait Until Log Contains    ${logfile}
        ...    Connected App ID "${app_id}" to http://localhost:${port}    timeout=${READINESS_TIMEOUT}
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
        ${command}=    Resolve Project In Command    ${template}    ${project}
        Log    Documented command: ${command}    console=True
        Run And Expect RC Zero    ${command}    cwd=${cwd}    timeout=${timeout}
    END

Wait Until Ready Marker
    [Documentation]    Wait for a per-quickstart readiness string in the captured
    ...    `diagrid dev run` output. Agent quickstarts do not emit the canonical
    ...    `Connected App ID "<id>" to http://localhost:<port>` line that
    ...    Wait Until Apps Connected waits for; langgraph prints `Uvicorn running
    ...    on`, and the marker is a property of the framework, not the language.
    [Arguments]    ${logfile}    ${marker}
    Wait Until Log Contains    ${logfile}    ${marker}    timeout=${READINESS_TIMEOUT}

*** Comments ***
Launching and stopping a quickstart through the `diagrid dev run` command its
README documents, plus the readiness marker that command emits.

*** Settings ***
Library     Collections
Library     String
Resource    process.resource

*** Keywords ***
Start Quickstart
    [Documentation]    Launch the quickstart's documented run command in the
    ...    background under alias `apps`, substituting the ephemeral project name.
    [Arguments]    ${qs}    ${project}    ${logfile}
    ${command}=    Resolve Project In Command    ${qs}[run]    ${project}
    Log    Starting: ${command}    console=True
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
        ...    Connected App ID "${app_id}" to http://localhost:${port}    timeout=180s
    END

Stop Quickstart
    [Documentation]    CTRL+C equivalent, then release the local app connections.
    ...    Safe to call when the process is already gone.
    [Arguments]    ${project}
    Run Keyword And Ignore Error    Stop Process Tree    apps
    Run Process    diagrid dev stop --project ${project}    shell=True
    ...    stderr=STDOUT    timeout=120s

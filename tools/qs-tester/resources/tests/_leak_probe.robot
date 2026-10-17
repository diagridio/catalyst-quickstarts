*** Comments ***
Fixture, not a suite: the leading underscore keeps `robot resources/tests` from
discovering it. keywords.robot runs it in a child robot process and then reads
that process's output.xml, to prove Require Env Var never writes the secret it
checks into the Robot output.

*** Settings ***
Resource        ../quickstart.resource

*** Test Cases ***
Probe
    Require Env Var    QS_TESTER_FAKE_KEY    leak-probe

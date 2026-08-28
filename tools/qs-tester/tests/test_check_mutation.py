"""Tests for the mutation-check verdict.

This is the thing that decides whether a suite gets reported VERIFIED, so its
false positives are expensive: certifying an assertion as "can fail" when the
mutated run actually died somewhere else is exactly the outcome SKILL.md calls
the one that damages the harness.

The XML below is the shape Robot 7 writes, checked against two real runs while
this was written: `results/agents-langgraph-nokey/output.xml` (a suite that
stopped at `Require Env Var`, leaving `Wait Until Ready Marker` NOT RUN) and a
throwaway suite that failed inside `Wait Until Ready Marker` with the mutation
sentinel in its message.
"""

from pathlib import Path

from check_mutation import check

KEYWORD = "Wait Until Ready Marker"
SENTINEL = "__mutation_check__"


def write_output(tmp_path: Path, keywords: list[tuple[str, str, str]]) -> Path:
    """Write an output.xml holding one <kw> per (name, status, message)."""
    body = "".join(
        f'<kw name="{name}" owner="catalyst">'
        f'<status status="{status}">{message}</status></kw>'
        for name, status, message in keywords
    )
    path = tmp_path / "output.xml"
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<robot generator="Robot 7.0">'
        f'<suite name="Quickstart"><test name="T">{body}'
        '<status status="FAIL">failed</status></test>'
        '<status status="FAIL"/></suite></robot>'
    )
    return path


def test_passes_when_the_mutated_keyword_failed_naming_the_sentinel(tmp_path):
    output = write_output(
        tmp_path,
        [(KEYWORD, "FAIL", f'Log does not contain "{SENTINEL}"')],
    )
    assert check(output, KEYWORD, SENTINEL) == []


def test_fails_when_the_suite_died_before_reaching_the_keyword(tmp_path):
    # The defect this exists for: an agent-family suite provisions itself in
    # SETUP, so a mutated run against an already-provisioned project dies in
    # `project create` and never reaches the mutated assertion. Robot records the
    # keyword as NOT RUN, robot exits non-zero, and a bare "non-zero means the
    # mutation was caught" check would call that proof.
    output = write_output(
        tmp_path,
        [
            ("Run Documented Commands", "FAIL", "Command failed (rc=1): diagrid project create"),
            (KEYWORD, "NOT RUN", ""),
        ],
    )
    problems = check(output, KEYWORD, SENTINEL)
    assert problems and "never failed" in problems[0]
    assert "NOT RUN" in problems[0]


def write_swallowed_output(tmp_path: Path, keyword: str, message: str) -> Path:
    """Write an output.xml shaped exactly like a real Robot 7 run in which
    `keyword` FAILs but the failure is caught by `Run Keyword And Return
    Status` and turned into a boolean, so the enclosing test still PASSes.

    This is the shape `/tmp/fool/output.xml` has for `Wait Until Ready Marker`
    after `uv run robot --outputdir /tmp/fool resources/tests/smoke.robot
    resources/tests/keywords.robot`: the suite is 20/20 PASS, and the keyword
    is nested two levels deep (`Run Keyword And Return Status` wrapping the
    named keyword) with its own `<status status="FAIL">`, while the `<test>`
    and `<suite>` around it both report PASS.
    """
    path = tmp_path / "output.xml"
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<robot generator="Robot 7.0">'
        '<suite name="Quickstart"><test name="T">'
        '<kw name="Run Keyword And Return Status" owner="BuiltIn">'
        f'<kw name="{keyword}" owner="catalyst">'
        f'<status status="FAIL">{message}</status></kw>'
        '<status status="PASS"/></kw>'
        '<status status="PASS"/></test>'
        '<status status="PASS"/></suite></robot>'
    )
    return path


def test_fails_when_the_keyword_failed_but_the_enclosing_test_swallowed_it(tmp_path):
    # The exact fooling case a reviewer demonstrated: `Wait Until Ready Marker`
    # FAILs inside `Run Keyword And Return Status`, which turns that into
    # `${status}=False` and the test asserts on the boolean, so the test (and
    # the whole suite) PASSES. A checker that looks only at the keyword's own
    # status prints "Mutation caught" here and exits 0 -- against a run that is
    # 20/20 PASS. Even a message that names the sentinel must not save this,
    # because the failure never reached anything that could fail a real run.
    output = write_swallowed_output(tmp_path, KEYWORD, f'Log does not contain "{SENTINEL}"')
    problems = check(output, KEYWORD, SENTINEL)
    assert problems and "swallowed" in problems[0]
    assert "PASSED" in problems[0]


def test_fails_when_the_keyword_passed_and_something_else_broke(tmp_path):
    output = write_output(
        tmp_path,
        [
            (KEYWORD, "PASS", ""),
            ("POST And Expect Field", "FAIL", "connection refused"),
        ],
    )
    problems = check(output, KEYWORD, SENTINEL)
    assert problems and "never failed" in problems[0]


def test_fails_when_no_keyword_by_that_name_ran(tmp_path):
    output = write_output(tmp_path, [("Build Quickstart", "FAIL", "uv sync failed")])
    problems = check(output, KEYWORD, SENTINEL)
    assert problems and "no keyword named" in problems[0]


def test_fails_when_the_failure_message_does_not_name_the_sentinel(tmp_path):
    # The keyword failed, but for its own reasons -- a real readiness timeout on
    # the real marker, say. Same keyword, different cause, no proof.
    output = write_output(
        tmp_path,
        [(KEYWORD, "FAIL", 'Log does not contain "Uvicorn running on"')],
    )
    problems = check(output, KEYWORD, SENTINEL)
    assert problems and "no failure message mentions" in problems[0]


def test_skips_the_message_check_when_no_substring_is_given(tmp_path):
    # A custom mutation that does not carry the sentinel still gets the
    # keyword-name check, which is weaker but not nothing.
    output = write_output(tmp_path, [(KEYWORD, "FAIL", "some other wording")])
    assert check(output, KEYWORD, "") == []


def test_fails_when_the_mutated_run_produced_no_output_xml(tmp_path):
    problems = check(tmp_path / "absent" / "output.xml", KEYWORD, SENTINEL)
    assert problems and "does not exist" in problems[0]


def test_fails_on_an_unparseable_output_xml(tmp_path):
    path = tmp_path / "output.xml"
    path.write_text("<robot><suite>truncated mid-file")
    problems = check(path, KEYWORD, SENTINEL)
    assert problems and "not parseable" in problems[0]

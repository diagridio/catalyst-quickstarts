import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

import suites

REPO_ROOT = Path(__file__).resolve().parents[3]
HARNESS = Path(__file__).resolve().parents[1]


def list_suites(*args):
    """Run ci/list-suites.py the way the shell scripts do, from tools/qs-tester."""
    return subprocess.run(
        [sys.executable, "ci/list-suites.py", *args],
        cwd=HARNESS,
        capture_output=True,
        text=True,
    )


def _list_suites_module():
    """Load ci/list-suites.py in-process, so a test can monkeypatch `suites.SUITES`
    and see it reflected in `--matrix` output.

    `list_suites()` above shells out to a fresh interpreter, which cannot see a
    monkeypatch made in this process -- there is no other way to exercise
    `--matrix` against a fabricated row. The hyphen in the filename is why this
    is a manual `importlib` load rather than a plain `import`; the loaded
    module's own `import suites` resolves to the same cached module object
    already imported above, so a `monkeypatch.setattr(suites, "SUITES", ...)`
    here is visible to it.
    """
    path = HARNESS / "ci" / "list-suites.py"
    spec = importlib.util.spec_from_file_location("list_suites_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_row_declares_a_known_family():
    for row in suites.SUITES:
        assert row["family"] in ("canonical", "agent"), row


def test_suite_paths_are_relative_to_the_harness_directory():
    # robot runs from tools/qs-tester, so a bare "workflow/tests/..." would
    # resolve to tools/qs-tester/workflow/tests/... and fail to load.
    for path in suites.suite_paths():
        assert path.startswith("../../"), path


def test_the_four_canonical_suites_are_registered():
    canonical = {r["api"] for r in suites.SUITES if r["family"] == "canonical"}
    assert canonical == {"workflow", "state", "pubsub", "invocation"}


def test_agent_suites_filters_on_nightly():
    all_agents = suites.agent_suites()
    nightly = suites.agent_suites(nightly_only=True)
    assert len(nightly) <= len(all_agents)
    assert all(r["nightly"] for r in nightly)


def test_validate_passes_on_the_real_manifest():
    assert suites.validate(REPO_ROOT) == []


def test_validate_reports_a_missing_suite_file(monkeypatch):
    broken = ({"suite": "nope/tests/quickstart.robot", "family": "canonical",
               "api": "nope", "languages": ("python",), "nightly": True,
               "secrets": ()},)
    monkeypatch.setattr(suites, "SUITES", broken)
    problems = suites.validate(REPO_ROOT)
    assert any("does not exist" in p for p in problems)


def test_validate_reports_a_missing_data_module(monkeypatch):
    broken = ({"suite": "agents/langgraph/tests/quickstart.robot", "family": "agent",
               "name": "langgraph", "data": "agents_nonexistent", "language": "python",
               "runtime": "python", "nightly": True, "secrets": ("OPENAI_API_KEY",)},)
    monkeypatch.setattr(suites, "SUITES", broken)
    problems = suites.validate(REPO_ROOT)
    assert any("data module" in p for p in problems)


def test_validate_reports_a_duplicate_suite_path(monkeypatch):
    row = {"suite": "state/tests/quickstart.robot", "family": "canonical",
           "api": "state", "languages": ("python",), "nightly": True, "secrets": ()}
    monkeypatch.setattr(suites, "SUITES", (row, dict(row)))
    problems = suites.validate(REPO_ROOT)
    assert any("duplicate" in p for p in problems)


def test_validate_reports_a_duplicate_agent_name(monkeypatch):
    row = {"suite": "agents/langgraph/tests/quickstart.robot", "family": "agent",
           "name": "langgraph", "data": "agents_langgraph", "language": "python",
           "runtime": "python", "nightly": True, "secrets": ("OPENAI_API_KEY",)}
    other = dict(row, suite="agents/other/tests/quickstart.robot")
    monkeypatch.setattr(suites, "SUITES", (row, other))
    problems = suites.validate(REPO_ROOT)
    assert any("duplicate" in p and "name" in p for p in problems)


def test_validate_rejects_a_lowercase_secret_name(monkeypatch):
    broken = ({"suite": "agents/langgraph/tests/quickstart.robot", "family": "agent",
               "name": "langgraph", "data": "agents_langgraph", "language": "python",
               "runtime": "python", "nightly": True, "secrets": ("openai_api_key",)},)
    monkeypatch.setattr(suites, "SUITES", broken)
    problems = suites.validate(REPO_ROOT)
    assert any("secret" in p for p in problems)


def test_row_for_suite_finds_a_registered_suite():
    row = suites.row_for_suite("state/tests/quickstart.robot")
    assert row is not None and row["api"] == "state"


# --- ci/list-suites.py --row -------------------------------------------------
# The skill's verify-live.sh branches on this output: it runs agent-family
# suites and refuses canonical ones, which need an externally created project
# and one language at a time. A wrong family here would send a canonical suite
# down the agent path and run it against a project nobody created.


def test_row_reports_an_agent_suite_with_its_name():
    result = list_suites("--row", "agents/langgraph/tests/quickstart.robot")
    assert result.returncode == 0, result.stderr
    assert "FAMILY=agent" in result.stdout
    assert "NAME=langgraph" in result.stdout


def test_row_reports_a_canonical_suite_with_every_language():
    result = list_suites("--row", "state/tests/quickstart.robot")
    assert result.returncode == 0, result.stderr
    assert "FAMILY=canonical" in result.stdout
    assert "LANGUAGES=csharp java javascript python" in result.stdout


def test_row_accepts_the_robot_relative_form_of_a_path():
    # Callers hold the path in the shape robot wants it (`../../<suite>`), so
    # both spellings have to resolve to the same row.
    result = list_suites("--row", "../../agents/langgraph/tests/quickstart.robot")
    assert result.returncode == 0, result.stderr
    assert "FAMILY=agent" in result.stdout


def test_row_fails_on_a_suite_that_is_not_registered():
    result = list_suites("--row", "agents/nope/tests/quickstart.robot")
    assert result.returncode == 1
    assert "not registered" in result.stderr


# --- project-name budget -----------------------------------------------------
# ci/project-name.sh builds qs-ci-<leg>-<run-id>, and agent legs use
# agents-<name>. The binding case is a local run: GITHUB_RUN_ID is unset, so the
# fallback is `local` plus a 10-digit epoch, which is longer than a real
# workflow run id. Sizing to the shorter CI form would let a name pass
# validation here and then fail on someone's laptop.


def test_project_name_budget_is_derived_not_hardcoded():
    # The budget must fall out of the real name format, so it stays true if the
    # prefix or the leg format changes. 55 - len("qs-ci-") - len("agents-")
    # - len("-") - len("local" + 10-digit epoch) == 26.
    assert suites.project_name_budget() == 26


def test_leg_id_is_the_path_below_agents_with_dashes():
    row = suites.row_for_suite("agents/langgraph/tests/quickstart.robot")
    assert suites.leg_id(row) == "langgraph"


def test_validate_rejects_a_name_over_the_budget(monkeypatch):
    too_long = "a" * (suites.project_name_budget() + 1)
    broken = ({"suite": "agents/langgraph/tests/quickstart.robot", "family": "agent",
               "name": too_long, "data": "agents_langgraph", "language": "python",
               "runtime": "python", "nightly": False, "secrets": ("OPENAI_API_KEY",)},)
    monkeypatch.setattr(suites, "SUITES", broken)
    problems = suites.validate(REPO_ROOT)
    assert any("55" in p and "characters" in p for p in problems)


def test_validate_accepts_a_name_exactly_at_the_budget(monkeypatch):
    exact = "a" * suites.project_name_budget()
    row = ({"suite": "agents/langgraph/tests/quickstart.robot", "family": "agent",
            "name": exact, "data": "agents_langgraph", "language": "python",
            "runtime": "python", "nightly": False, "secrets": ("OPENAI_API_KEY",)},)
    monkeypatch.setattr(suites, "SUITES", row)
    assert not any("characters" in p for p in suites.validate(REPO_ROOT))


def test_an_explicit_leg_overrides_a_too_long_derived_name(monkeypatch):
    row = ({"suite": "agents/spring-ai/event-planner/tests/quickstart.robot",
            "family": "agent", "name": "a" * 40, "leg": "short-leg",
            "data": "agents_langgraph", "language": "java", "runtime": "java",
            "nightly": False, "secrets": ("OPENAI_API_KEY",)},)
    monkeypatch.setattr(suites, "SUITES", row)
    assert not any("characters" in p for p in suites.validate(REPO_ROOT))
    assert suites.leg_id(row[0]) == "short-leg"


def test_matrix_output_carries_the_leg_override_not_the_name(monkeypatch, capsys):
    # `--matrix agent` is what the nightly workflow actually reads to build the
    # project name (via `agents-<leg>`). If it emitted `name` where a row set a
    # shorter `leg`, the override would satisfy `--validate` and then still
    # overflow the 55-character ceiling at `diagrid project create` -- the
    # exact failure this task exists to prevent, this time downstream of the
    # lint check instead of caught by it.
    row = ({"suite": "agents/spring-ai/event-planner/tests/quickstart.robot",
            "family": "agent", "name": "a" * 40, "leg": "short-leg",
            "data": "agents_langgraph", "language": "java", "runtime": "java",
            "nightly": False, "secrets": ("OPENAI_API_KEY",)},)
    monkeypatch.setattr(suites, "SUITES", row)
    module = _list_suites_module()
    monkeypatch.setattr(sys, "argv", ["list-suites.py", "--matrix", "agent"])
    assert module.main() == 0
    matrix = json.loads(capsys.readouterr().out)
    assert len(matrix) == 1
    assert matrix[0]["leg"] == "short-leg"
    assert matrix[0]["name"] == "a" * 40


def test_validate_reports_a_non_string_leg_instead_of_raising(monkeypatch):
    # `_REQUIRED` only checks key presence, not type. A `name` that is present
    # but not a string used to reach `len(leg)` unguarded and raise
    # `TypeError: object of type 'int' has no len()`, which is a worse failure
    # mode than a reported problem for validate() to have in CI's lint job.
    broken = ({"suite": "agents/langgraph/tests/quickstart.robot", "family": "agent",
               "name": 12345, "data": "agents_langgraph", "language": "python",
               "runtime": "python", "nightly": False, "secrets": ("OPENAI_API_KEY",)},)
    monkeypatch.setattr(suites, "SUITES", broken)
    problems = suites.validate(REPO_ROOT)
    assert any("must be a string" in p for p in problems)

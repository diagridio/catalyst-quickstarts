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

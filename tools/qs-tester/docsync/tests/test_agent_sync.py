import types

import pytest
from check_readme_sync import all_bash_lines, check_agent, normalise_project

# A synthetic README in the agent-family shape, not a copy of the real
# agents/langgraph one: it deliberately adds a documented "## Clean Up" (the real
# file has none) so the teardown path is covered too. Named sections rather than
# numbers, a documented project name, an out-of-scope crash-test flow, and a `cd`
# the harness expresses as a working directory instead of a command.
README = """\
# LangGraph Quickstart - Schedule Planner

## Setup

```bash
cd agents/langgraph
uv sync
```

### Set your API key

```bash
export OPENAI_API_KEY="your-key-here"
```

## Run with Catalyst

```bash
diagrid login
```

```bash
diagrid project create langgraph-quickstart --enable-agent-infrastructure --wait --use
```

```bash
diagrid agent create langgraph-agent --wait
```

```bash
uv run diagrid dev run -f dev-python-langgraph.yaml --approve
```

Wait until the output shows `Uvicorn running on <localhost:port>`.

### 2. Trigger a Workflow

```bash
curl -i -X POST http://localhost:8005/agent/run \\
  -H "Content-Type: application/json" \\
  -d '{"task": "Check if the Grand Ballroom is available on March 15th"}'
```

## Crash Recovery Test With Catalyst

```bash
uv run diagrid dev run -f dev-crash-test.yaml --approve
```

## Clean Up

```bash
diagrid project delete langgraph-quickstart
```
"""


def data_module(**overrides):
    """A stand-in for variables/agents_<name>.py."""
    module = types.SimpleNamespace(
        DOCUMENTED_PROJECT="langgraph-quickstart",
        SETUP=(
            "diagrid project create {project} --enable-agent-infrastructure --wait --use",
            "diagrid agent create langgraph-agent --wait",
        ),
        INSTALL="uv sync",
        RUN="uv run diagrid dev run -f dev-python-langgraph.yaml --approve",
        TEARDOWN=("diagrid project delete {project}",),
        READY_MARKERS=("Uvicorn running on",),
        REQUESTS=(
            {
                "method": "POST",
                "port": 8005,
                "path": "/agent/run",
                "payload": {"task": "Check if the Grand Ballroom is available on March 15th"},
                "status": 200,
                "field": None,
            },
        ),
        UNCOVERED=(
            ("uv run diagrid dev run -f dev-crash-test.yaml --approve",
             "crash-recovery flow needs a source edit; out of scope"),
        ),
    )
    for key, value in overrides.items():
        setattr(module, key, value)
    return module


def test_all_bash_lines_ignores_powershell_and_prose():
    lines = all_bash_lines(README)
    assert "uv sync" in lines
    assert "diagrid agent create langgraph-agent --wait" in lines
    assert not any("Invoke-RestMethod" in line for line in lines)


def test_all_bash_lines_joins_a_wrapped_curl_into_one_line():
    # The documented curl spans three lines with backslash continuations. A
    # per-line reader would see three fragments and match none of them.
    curls = [line for line in all_bash_lines(README) if line.startswith("curl")]
    assert len(curls) == 1
    assert "Content-Type: application/json" in curls[0]
    assert "Grand Ballroom" in curls[0]


def test_normalise_project_maps_the_documented_name_onto_the_placeholder():
    documented = "diagrid project create langgraph-quickstart --wait --use"
    harness = "diagrid project create {project} --wait --use"
    assert normalise_project(documented, "langgraph-quickstart") == harness


def test_check_agent_passes_when_the_module_matches_the_readme(tmp_path):
    row, root = _fixture(tmp_path)
    assert check_agent(row, root, module=data_module()) == []


def test_check_agent_reports_a_run_command_that_drifted(tmp_path):
    row, root = _fixture(tmp_path)
    module = data_module(RUN="uv run diagrid dev run -f wrong-file.yaml --approve")
    problems = check_agent(row, root, module=module)
    assert any("not documented" in p for p in problems)


def test_check_agent_reports_a_documented_command_nobody_runs(tmp_path):
    # The crash-test command is dropped from UNCOVERED, so nothing accounts for
    # it. This is the direction the canonical checker cannot check.
    row, root = _fixture(tmp_path)
    problems = check_agent(row, root, module=data_module(UNCOVERED=()))
    assert any("dev-crash-test" in p for p in problems)


def test_check_agent_reports_a_readiness_marker_absent_from_the_readme(tmp_path):
    row, root = _fixture(tmp_path)
    module = data_module(READY_MARKERS=("Application started on port",))
    problems = check_agent(row, root, module=module)
    assert any("readiness marker" in p for p in problems)


def test_check_agent_checks_every_readiness_marker(tmp_path):
    # Multi-app quickstarts have one marker per app (dapr-agents/multi-agent-workflow
    # runs three), so a checker that only looked at the first would miss drift in
    # the others.
    row, root = _fixture(tmp_path)
    module = data_module(READY_MARKERS=("Uvicorn running on", "Nothing prints this"))
    problems = check_agent(row, root, module=module)
    assert any("Nothing prints this" in p for p in problems)


def test_check_agent_reports_a_request_payload_that_drifted(tmp_path):
    row, root = _fixture(tmp_path)
    module = data_module(
        REQUESTS=({"method": "POST", "port": 8005, "path": "/agent/run",
                   "payload": {"task": "something else entirely"},
                   "status": 200, "field": None},)
    )
    problems = check_agent(row, root, module=module)
    assert any("payload" in p for p in problems)


def test_check_agent_reports_a_request_url_that_drifted(tmp_path):
    row, root = _fixture(tmp_path)
    module = data_module(
        REQUESTS=({"method": "POST", "port": 9999, "path": "/agent/run",
                   "payload": {"task": "Check if the Grand Ballroom is available on March 15th"},
                   "status": 200, "field": None},)
    )
    problems = check_agent(row, root, module=module)
    assert any("request URL" in p for p in problems)


def test_check_agent_checks_commands_attached_to_a_request(tmp_path):
    # A request's `commands` are documented commands too (mcp-auth's grant step
    # sits between two calls), so they must be documented like any other.
    row, root = _fixture(tmp_path)
    module = data_module(
        REQUESTS=({"method": "POST", "port": 8005, "path": "/agent/run",
                   "payload": {"task": "Check if the Grand Ballroom is available on March 15th"},
                   "status": 200, "field": None,
                   "commands": ("diagrid mcp grant --caller x --tool add",)},)
    )
    problems = check_agent(row, root, module=module)
    assert any("mcp grant" in p for p in problems)


def test_check_agent_checks_a_requests_log_marker(tmp_path):
    row, root = _fixture(tmp_path)
    module = data_module(
        REQUESTS=({"method": "POST", "port": 8005, "path": "/agent/run",
                   "payload": {"task": "Check if the Grand Ballroom is available on March 15th"},
                   "status": 200, "field": None,
                   "log_marker": "no_such_tool"},)
    )
    problems = check_agent(row, root, module=module)
    assert any("log marker" in p for p in problems)


def _fixture(tmp_path):
    """Write README into a fake repo root and return (manifest row, root)."""
    readme_dir = tmp_path / "agents" / "langgraph"
    readme_dir.mkdir(parents=True)
    (readme_dir / "README.md").write_text(README)
    (readme_dir / "tests").mkdir()
    (readme_dir / "tests" / "quickstart.robot").write_text("")
    row = {
        "suite": "agents/langgraph/tests/quickstart.robot",
        "family": "agent",
        "name": "langgraph",
        "data": "agents_langgraph",
        "language": "python",
        "runtime": "python",
        "nightly": True,
        "secrets": ("OPENAI_API_KEY",),
    }
    return row, tmp_path

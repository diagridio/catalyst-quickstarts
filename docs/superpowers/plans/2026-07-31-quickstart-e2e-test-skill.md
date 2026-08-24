# Quickstart E2E Test Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the harness and CI extensions that let agent-family quickstarts be tested at all, prove them with a first live suite (`agents/langgraph`), then package the whole procedure as a skill that adds such a test for any quickstart on request.

**Architecture:** A Python suite manifest (`variables/suites.py`) becomes the single registry that CI discovery, the lint dryrun, and doc-sync all read. Four new Robot keywords plus two overridable timeout variables extend the existing resource files without new ones. Each agent-family quickstart gets a data module holding its documented command sequence verbatim, and a one-test suite beside the quickstart. A new `e2e-agents` CI job, gated behind the existing `e2e` job so the two-concurrent-project cap survives, runs those suites from the manifest.

**Tech Stack:** Robot Framework 7 (`robotframework-requests`), Python 3.12+, `uv`, pytest 8, GitHub Actions, `diagrid` CLI 1.36.0.

Design spec: `docs/superpowers/specs/2026-07-31-quickstart-e2e-test-skill-design.md`. Read it before Task 1; every task below implements a named part of it.

## Global Constraints

- Documented commands run verbatim. Only the project name is substituted. The two sanctioned exceptions are `diagrid login` becoming `diagrid login --api-key "$DIAGRID_API_KEY"`, and the documented project name becoming an ephemeral one.
- Every ephemeral project name starts with `qs-ci-`. `ci/reap-orphans.sh` collects leaked projects by that prefix; a name without it leaks forever.
- Never more than two concurrent Catalyst projects across the whole workflow.
- `max-parallel` is per-job, so two e2e jobs must never run concurrently.
- No new `.resource` keyword files. New keywords go in the existing `catalyst.resource` and `quickstart.resource`, beside the keywords they relate to. Adding test files under `resources/tests/` is expected and not covered by this constraint.
- Existing suite behaviour must not change. The four canonical suites and their timeouts keep working exactly as they do now.
- Never invent an expected value. If a README does not document it and it cannot be read out of the repo, assert only what is documented and leave a comment naming the gap.
- Python 3.12+, no new third-party dependencies (in particular no PyYAML).
- Commit messages: plain imperative, no `feat:`/`fix:` prefixes, matching this repo's history.

## Deliberate refinements to the spec

All were found while planning, by checking the spec's sketches against the quickstarts they have to cover. Apply them as written here, and update the spec in Task 7.

1. **Two timeout variables, not one.** The spec proposed a single `${MARKER_TIMEOUT}`. The harness has two distinct hardcoded timeouts with different values: log markers wait 60s (`Wait Until Log Contains`) and readiness waits 180s (`Wait Until Apps Connected`, `Wait Until Apps Healthy`). Collapsing them into one variable would silently change existing behaviour, which Global Constraints forbid. Use `${MARKER_TIMEOUT}` (default `60s`) and `${READINESS_TIMEOUT}` (default `180s`).
2. **doc-sync loose mode is total, not one-way.** The canonical checker only verifies documented-to-harness coverage, because the harness legitimately does undocumented things. For agent-family quickstarts the reverse also becomes checkable: every documented bash line is either run by the suite or listed in the data module's `UNCOVERED` tuple with a reason. This turns "out of scope" from a claim in prose into a machine-checked list.
3. **`REQUESTS` is an ordered tuple, and a request may carry documented commands to run first.** A single trigger dict cannot express `mcp-auth/python`, whose documented flow interleaves HTTP calls and CLI commands: call the tool and watch it fail closed, run `diagrid mcp grant`, call again and watch it succeed. Each entry therefore gets an optional `commands` tuple, run through the existing `Run Documented Commands` before that request, and an optional `log_marker` asserted after it. Single-request quickstarts like langgraph simply omit both keys. Two documented statuses in one flow (403 then 200) is the case that makes this necessary, and it is the shape most agent quickstarts will eventually grow.
4. **`READY_MARKERS` is a tuple.** `dapr-agents/multi-agent-workflow` runs three apps (`customer-support-system` on 8001, `triage-agent` on 8002, `expert-agent` on 8003), so "the apps are up" is several markers, not one. `HEALTH_PORTS` already handles several ports.
5. **The mutation check overrides through a generated variable file, not `--variable`.** Robot's `--variable` can only set scalars, so it cannot break a tuple like `READY_MARKERS`. A generated one-line variable file passed with `--variablefile` takes precedence over a suite's `Variables` import, works for scalars and tuples alike, and needs no type guessing in the script.

---

## File structure

| File | Responsibility |
|---|---|
| `tools/qs-tester/variables/suites.py` | The suite registry plus its validation. Read by CI discovery, the lint dryrun, and doc-sync. |
| `tools/qs-tester/ci/list-suites.py` | CLI over the registry: `--paths`, `--matrix agent`, `--validate`. |
| `tools/qs-tester/tests/test_suites.py` | Unit tests for the registry and its validation. |
| `tools/qs-tester/resources/process.resource` | Gains the two timeout variables; `Wait Until Log Contains` takes its default from one. |
| `tools/qs-tester/resources/catalyst.resource` | Gains `Run Documented Commands` and `Wait Until Ready Marker`. |
| `tools/qs-tester/resources/quickstart.resource` | Gains `Require Env Var` and `POST And Expect Field`. |
| `tools/qs-tester/resources/tests/keywords.robot` | Credential-free tests for the four new keywords. |
| `tools/qs-tester/resources/tests/echo_server.py` | Stdlib HTTP fixture that answers POST, for testing `POST And Expect Field`. |
| `tools/qs-tester/docsync/check_readme_sync.py` | Gains agent-family loose mode. |
| `tools/qs-tester/docsync/tests/test_agent_sync.py` | Unit tests for loose mode. |
| `tools/qs-tester/variables/agents_langgraph.py` | The first agent-family data module: langgraph's documented commands and assertions. |
| `agents/langgraph/tests/quickstart.robot` | The first agent-family suite. |
| `tools/qs-tester/ci/project-name.sh` | Computes and exports the ephemeral name. No CLI calls. |
| `tools/qs-tester/ci/login.sh` | API-key login. |
| `tools/qs-tester/ci/teardown-project.sh` | Modified: quiet when the project is already gone. |
| `.github/workflows/e2e-quickstarts.yml` | Manifest-driven lint, `discover` job, `e2e-agents` job, updated `report` and `paths`. |
| `.claude/skills/add-quickstart-e2e-test/**` | The skill: SKILL.md, three references, three scripts, evals. |

**Natural stopping point:** Tasks 1-7 deliver working, tested software (langgraph under nightly CI). Tasks 8-10 build the skill that repeats the procedure. Stopping after Task 7 leaves the repo in a coherent state.

---

## Task 1: Suite manifest and its CLI

**Files:**
- Create: `tools/qs-tester/variables/suites.py`
- Create: `tools/qs-tester/ci/list-suites.py`
- Create: `tools/qs-tester/tests/test_suites.py`
- Modify: `tools/qs-tester/pyproject.toml:14-17`
- Modify: `.github/workflows/e2e-quickstarts.yml` (the `Unit-test the doc-sync checker` step only)

**Interfaces:**
- Consumes: nothing.
- Produces: `suites.SUITES` (tuple of dicts); `suites.suite_paths() -> list[str]` returning harness-relative paths like `../../workflow/tests/quickstart.robot`; `suites.agent_suites(nightly_only: bool = False) -> list[dict]`; `suites.validate(repo_root: Path) -> list[str]` returning problem descriptions, empty when valid; `suites.row_for_suite(suite: str) -> dict | None`. Task 4 imports `validate` and `agent_suites`; Task 6 shells out to `ci/list-suites.py`.

- [ ] **Step 1: Write the failing tests**

Create `tools/qs-tester/tests/test_suites.py`:

```python
from pathlib import Path

import pytest

import suites

REPO_ROOT = Path(__file__).resolve().parents[3]


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
```

- [ ] **Step 2: Add the tests directory to pytest and run to verify they fail**

Change `tools/qs-tester/pyproject.toml` lines 14-17 to:

```toml
[tool.pytest.ini_options]
pythonpath = ["docsync", "variables"]
testpaths = ["docsync/tests", "tests"]
```

Run: `cd tools/qs-tester && uv run pytest -q`
Expected: collection errors, `ModuleNotFoundError: No module named 'suites'`.

- [ ] **Step 3: Write the manifest**

Create `tools/qs-tester/variables/suites.py`:

```python
"""The registry of every Robot suite in this repository.

One row per suite. Three consumers read it, which is the whole point of having
it: the lint dryrun (so adding a suite does not mean editing a hardcoded path
list), the CI matrix for agent-family suites, and doc-sync (so a new suite is
checked against its README automatically).

A Python module rather than YAML: PyYAML is not a dependency of this harness,
the repo already expresses its tables as commented Python modules
(`quickstarts.py`), and both `ci/list-suites.py` and the doc-sync checker can
import this directly.

Fields, by family:

  canonical   suite, family, api, languages, nightly, secrets
  agent       suite, family, name, data, language, runtime, nightly, secrets

`nightly` is read only for agent-family rows. Canonical scheduling is the
business of the workflow's own `e2e` job, which keeps its hand-written language
matrix; these rows exist here for the dryrun and doc-sync only.

`runtime` selects which CI runtime-setup step the suite needs, and is the reason
language is a per-suite property for agent-family quickstarts rather than a
matrix dimension: agents/microsoft-dotnet is .NET, agents/spring-ai is Java, and
the rest are Python.
"""

from pathlib import Path

# This file is tools/qs-tester/variables/suites.py, so the repository root is
# three levels up. Same convention as quickstarts.py.
REPO_ROOT = Path(__file__).resolve().parents[3]

FAMILIES = ("canonical", "agent")
RUNTIMES = ("python", "dotnet", "java", "javascript")

SUITES = (
    {
        "suite": "workflow/tests/quickstart.robot",
        "family": "canonical",
        "api": "workflow",
        "languages": ("csharp", "java", "javascript", "python"),
        "nightly": True,
        "secrets": (),
    },
    {
        "suite": "state/tests/quickstart.robot",
        "family": "canonical",
        "api": "state",
        "languages": ("csharp", "java", "javascript", "python"),
        "nightly": True,
        "secrets": (),
    },
    {
        "suite": "pubsub/tests/quickstart.robot",
        "family": "canonical",
        "api": "pubsub",
        "languages": ("csharp", "java", "javascript", "python"),
        "nightly": True,
        "secrets": (),
    },
    {
        "suite": "invocation/tests/quickstart.robot",
        "family": "canonical",
        "api": "invocation",
        "languages": ("csharp", "java", "javascript", "python"),
        "nightly": True,
        "secrets": (),
    },
)

_REQUIRED = {
    "canonical": ("suite", "family", "api", "languages", "nightly", "secrets"),
    "agent": ("suite", "family", "name", "data", "language", "runtime", "nightly", "secrets"),
}


def suite_paths():
    """Suite paths as robot must receive them.

    robot, rebot and the doc-sync checker all run from tools/qs-tester, so every
    path is prefixed to climb back to the repository root. Returning bare
    repo-relative paths here would make the dryrun fail with "does not exist",
    which is a confusing way to learn about a path convention.
    """
    return [f"../../{row['suite']}" for row in SUITES]


def agent_suites(nightly_only=False):
    """Agent-family rows, optionally only those opted into the nightly run."""
    rows = [row for row in SUITES if row["family"] == "agent"]
    if nightly_only:
        rows = [row for row in rows if row["nightly"]]
    return rows


def row_for_suite(suite):
    """The row whose `suite` matches, or None."""
    for row in SUITES:
        if row["suite"] == suite:
            return row
    return None


def quickstart_dir(row):
    """Absolute path to the quickstart a row tests.

    The suite lives at <quickstart-dir>/tests/quickstart.robot, so the
    quickstart directory is the suite's grandparent. Canonical suites are the
    exception: `state/tests/quickstart.robot` covers four language directories,
    so there is no single directory and this returns the API directory.
    """
    return str(REPO_ROOT / Path(row["suite"]).parent.parent)


def validate(repo_root):
    """Return a list of problem descriptions. Empty means the manifest is sound.

    Called by `ci/list-suites.py --validate` in the lint job, so a manifest
    mistake fails a PR in seconds rather than at 5am inside a nightly leg.
    """
    problems = []
    seen = set()

    for row in SUITES:
        where = row.get("suite", "<row with no suite key>")

        family = row.get("family")
        if family not in FAMILIES:
            problems.append(f"{where}: family must be one of {FAMILIES}, got {family!r}")
            continue

        missing = [key for key in _REQUIRED[family] if key not in row]
        if missing:
            problems.append(f"{where}: {family} row is missing key(s): {', '.join(missing)}")
            continue

        if row["suite"] in seen:
            problems.append(f"{where}: duplicate suite path")
        seen.add(row["suite"])

        if not (repo_root / row["suite"]).is_file():
            problems.append(f"{where}: suite file does not exist")

        for secret in row["secrets"]:
            if secret != secret.upper() or not secret.replace("_", "").isalnum():
                problems.append(
                    f"{where}: secret {secret!r} is not an upper-case environment "
                    "variable name; the CI env block references it literally"
                )

        if family == "agent":
            if row["runtime"] not in RUNTIMES:
                problems.append(
                    f"{where}: runtime must be one of {RUNTIMES}, got {row['runtime']!r}"
                )
            data = repo_root / "tools" / "qs-tester" / "variables" / f"{row['data']}.py"
            if not data.is_file():
                problems.append(f"{where}: data module {data.name} does not exist")

    return problems
```

- [ ] **Step 4: Run the manifest tests**

Run: `cd tools/qs-tester && uv run pytest tests -q`
Expected: PASS, 10 tests. `test_validate_reports_a_missing_data_module` passes because no agent row exists yet and the monkeypatched row points at a module that is genuinely absent.

- [ ] **Step 5: Write the CLI**

Create `tools/qs-tester/ci/list-suites.py`:

```python
"""Read the suite manifest for CI and for the lint dryrun.

Three modes:

    --paths              space-separated suite paths, ready to paste after
                         `robot --dryrun`, run from tools/qs-tester
    --matrix agent       JSON array for a GitHub Actions matrix
    --validate           print problems and exit 1, or confirm and exit 0

Usage from the workflow:

    uv run robot --dryrun ... $(uv run python ci/list-suites.py --paths)
    echo "agents=$(uv run python ci/list-suites.py --matrix agent --nightly)" >> "$GITHUB_OUTPUT"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Same reason as check_readme_sync.py: pytest's pythonpath setting does not
# apply when this file runs as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "variables"))

import suites  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--paths", action="store_true")
    mode.add_argument("--matrix", choices=("agent",))
    mode.add_argument("--validate", action="store_true")
    parser.add_argument(
        "--nightly",
        action="store_true",
        help="with --matrix: only suites opted into the nightly run",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
    )
    args = parser.parse_args()

    if args.paths:
        print(" ".join(suites.suite_paths()))
        return 0

    if args.matrix:
        rows = suites.agent_suites(nightly_only=args.nightly)
        # One flat object per matrix leg. `secrets` is a list of names, not
        # values: the workflow declares the values in its env block, and the
        # suite fails loudly through `Require Env Var` if one is missing.
        matrix = [
            {
                "suite": row["suite"],
                "name": row["name"],
                "language": row["language"],
                "runtime": row["runtime"],
                "secrets": list(row["secrets"]),
            }
            for row in rows
        ]
        # Compact separators: this lands in $GITHUB_OUTPUT, which is line-based.
        print(json.dumps(matrix, separators=(",", ":")))
        return 0

    problems = suites.validate(args.repo_root)
    for problem in problems:
        print(f"::error::{problem}")
    if problems:
        print(f"\n{len(problems)} problem(s) in the suite manifest")
        return 1
    print(f"Suite manifest is valid ({len(suites.SUITES)} suite(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Verify all three modes by hand**

```bash
cd tools/qs-tester
uv run python ci/list-suites.py --validate
uv run python ci/list-suites.py --paths
uv run python ci/list-suites.py --matrix agent
uv run robot --dryrun --variable PROJECT:dryrun --outputdir results/dryrun \
  $(uv run python ci/list-suites.py --paths)
```

Expected: `Suite manifest is valid (4 suite(s))`; four `../../`-prefixed paths; `[]` for the matrix (no agent rows yet); the dryrun passes 16 tests, exactly as the current hardcoded list does.

- [ ] **Step 7: Point the CI unit-test step at the whole test tree**

In `.github/workflows/e2e-quickstarts.yml`, replace the step named `Unit-test the doc-sync checker`:

```yaml
      - name: Unit-test the harness
        run: (cd tools/qs-tester && uv run pytest -q)
```

`testpaths` now covers both `docsync/tests` and `tests`, so a bare `pytest` runs everything and a future test directory needs no workflow edit.

- [ ] **Step 8: Commit**

```bash
git add tools/qs-tester/variables/suites.py tools/qs-tester/ci/list-suites.py \
        tools/qs-tester/tests/test_suites.py tools/qs-tester/pyproject.toml \
        .github/workflows/e2e-quickstarts.yml
git commit -m "Add a suite manifest and the CLI that reads it"
```

---

## Task 2: Overridable timeout variables

**Files:**
- Modify: `tools/qs-tester/resources/process.resource` (add a variables table after line 11; `Wait Until Log Contains` signature at line 31)
- Modify: `tools/qs-tester/resources/catalyst.resource:41` (the `timeout=180s` in `Wait Until Apps Connected`)
- Modify: `tools/qs-tester/resources/quickstart.resource:35` (the `180s` in `Wait Until Apps Healthy`)
- Test: `tools/qs-tester/resources/tests/smoke.robot`

**Interfaces:**
- Consumes: nothing.
- Produces: `${MARKER_TIMEOUT}` (default `60s`) and `${READINESS_TIMEOUT}` (default `180s`), both defined in `process.resource` and overridable with `robot --variable`. Task 5's suite and the skill's mutation check in Task 9 both rely on these names.

- [ ] **Step 1: Write the failing test**

Append to `tools/qs-tester/resources/tests/smoke.robot`, in `*** Test Cases ***`:

```robot
Marker Timeout Variable Bounds The Wait
    # Robot resolves a keyword's default argument values at call time against the
    # current variable scope, so setting the variable here changes what
    # `Wait Until Log Contains` waits for without passing timeout= explicitly.
    # That is exactly how the mutation check shortens a run it expects to fail:
    # `robot --variable MARKER_TIMEOUT:20s`.
    Set Test Variable    ${MARKER_TIMEOUT}    3s
    Create File    ${TEMPDIR}/timeout.log    nothing useful here
    ${start}=    Get Time    epoch
    ${status}=    Run Keyword And Return Status
    ...    Wait Until Log Contains    ${TEMPDIR}/timeout.log    absent-marker
    ${end}=    Get Time    epoch
    Should Be Equal    ${status}    ${False}
    ...    msg=Waiting for a marker that is not in the log must fail
    ${elapsed}=    Evaluate    ${end} - ${start}
    Should Be True    ${elapsed} < 30
    ...    msg=Gave up after ${elapsed}s; MARKER_TIMEOUT was not honoured
```

Add `Library    DateTime` to that file's `*** Settings ***` is not needed: `Get Time` comes from BuiltIn.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd tools/qs-tester && uv run robot --outputdir results/smoke --test "Marker Timeout Variable Bounds The Wait" resources/tests/smoke.robot`

Expected: FAIL with `Gave up after 60s; MARKER_TIMEOUT was not honoured`, after roughly 60 seconds. Not a "variable not found" error: pre-change, `Wait Until Log Contains`'s default is the literal `60s`, so nothing forces a variable lookup. The keyword ignores `${MARKER_TIMEOUT}` entirely and blocks for the full hardcoded minute, which is precisely what the elapsed-time assertion catches. Verified both ways against `c9a8008`.

- [ ] **Step 3: Define the variables and use them**

In `tools/qs-tester/resources/process.resource`, add a variables table between `*** Settings ***` and `*** Keywords ***`:

```robot
*** Variables ***
# Both are overridable with `robot --variable`, which is how the mutation check
# makes a run it expects to fail give up in seconds instead of minutes. The
# defaults are the values these waits used before they were parameterised: do not
# change them, or every existing suite's timing changes with them.
${MARKER_TIMEOUT}       60s
${READINESS_TIMEOUT}    180s
```

In the same file, change `Wait Until Log Contains`'s signature (line 31) from `${timeout}=60s` to:

```robot
    [Arguments]    ${logfile}    ${text}    ${timeout}=${MARKER_TIMEOUT}
```

In `tools/qs-tester/resources/catalyst.resource`, inside `Wait Until Apps Connected`, change the `timeout=180s` argument to `timeout=${READINESS_TIMEOUT}`.

In `tools/qs-tester/resources/quickstart.resource`, inside `Wait Until Apps Healthy`, change `Wait Until Keyword Succeeds    180s    3s` to:

```robot
        Wait Until Keyword Succeeds    ${READINESS_TIMEOUT}    3s    Health Check Returns 200    ${port}
```

- [ ] **Step 4: Run the smoke suite and the dryrun**

```bash
cd tools/qs-tester
uv run robot --outputdir results/smoke resources/tests/smoke.robot
uv run robot --dryrun --variable PROJECT:dryrun --outputdir results/dryrun \
  $(uv run python ci/list-suites.py --paths)
```

Expected: smoke passes 5 tests; the dryrun still passes 16. The dryrun is the check that no canonical suite referenced the old literals.

- [ ] **Step 5: Commit**

```bash
git add tools/qs-tester/resources/process.resource tools/qs-tester/resources/catalyst.resource \
        tools/qs-tester/resources/quickstart.resource tools/qs-tester/resources/tests/smoke.robot
git commit -m "Make the marker and readiness timeouts overridable"
```

---

## Task 3: Four new keywords

**Files:**
- Modify: `tools/qs-tester/resources/catalyst.resource` (add two keywords)
- Modify: `tools/qs-tester/resources/quickstart.resource` (add two keywords)
- Create: `tools/qs-tester/resources/tests/echo_server.py`
- Create: `tools/qs-tester/resources/tests/keywords.robot`

**Interfaces:**
- Consumes: `Run And Expect RC Zero`, `Wait Until Log Contains` (`process.resource`); `Resolve Project In Command` (`catalyst.resource`); `${READINESS_TIMEOUT}` from Task 2.
- Produces four keywords used by Task 5's suite:
  - `Run Documented Commands    ${commands}    ${project}    ${cwd}=${EMPTY}    ${timeout}=600s`
  - `Wait Until Ready Marker    ${logfile}    ${marker}`
  - `Require Env Var    ${name}    ${quickstart}`
  - `POST And Expect Field    ${port}    ${path}    ${payload}    ${status}    ${field}=${NONE}` returning the parsed body.

- [ ] **Step 1: Write the HTTP fixture**

Create `tools/qs-tester/resources/tests/echo_server.py`:

```python
"""A POST-answering HTTP server, so `POST And Expect Field` can be tested with
no Catalyst project and no network.

`python -m http.server` only answers GET, and the keyword under test asserts on
a POST response body, so a fixture is unavoidable. Kept to the standard library
on purpose: this file must not add a dependency to the harness.

Routes:
    POST /full   -> 200 {"result": "some text", "blank": ""}
    POST /empty  -> 200 {"result": ""}
    POST /none   -> 200 {"other": "value"}

Usage:
    python echo_server.py 8099
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

BODIES = {
    "/full": {"result": "some text", "blank": ""},
    "/empty": {"result": ""},
    "/none": {"other": "value"},
}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        body = BODIES.get(self.path)
        payload = json.dumps(body if body is not None else {"error": "no such route"})
        self.send_response(200 if body is not None else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload.encode())

    def do_GET(self):
        # The readiness probe the test suite polls before sending any POST.
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        # Silence per-request logging; the Robot log is the record that matters.
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
```

- [ ] **Step 2: Write the failing keyword tests**

Create `tools/qs-tester/resources/tests/keywords.robot`:

```robot
*** Comments ***
Tests for the keywords the agent-family suites depend on. Needs no Catalyst
project, no credentials and no network: the HTTP assertions run against
echo_server.py on localhost. Runs in CI's lint job alongside smoke.robot.

*** Settings ***
Resource        ../catalyst.resource
Resource        ../quickstart.resource
Library         OperatingSystem
Library         Process
Suite Setup     Start Echo Server
Suite Teardown  Stop Process Tree    echo

*** Variables ***
${ECHO_PORT}    8099

*** Test Cases ***
Require Env Var Fails When The Variable Is Absent
    Remove Environment Variable    QS_TESTER_FAKE_KEY
    ${status}=    Run Keyword And Return Status
    ...    Require Env Var    QS_TESTER_FAKE_KEY    fake
    Should Be Equal    ${status}    ${False}

Require Env Var Passes When The Variable Is Set
    Set Environment Variable    QS_TESTER_FAKE_KEY    sk-not-a-real-key
    Require Env Var    QS_TESTER_FAKE_KEY    fake
    [Teardown]    Remove Environment Variable    QS_TESTER_FAKE_KEY

Require Env Var Fails When The Variable Is Set But Empty
    # An empty key is what a misconfigured GitHub secret actually looks like:
    # the env var exists, so a plain existence check would pass and the failure
    # would surface later as an opaque 401 from the model provider.
    Set Environment Variable    QS_TESTER_FAKE_KEY    ${EMPTY}
    ${status}=    Run Keyword And Return Status
    ...    Require Env Var    QS_TESTER_FAKE_KEY    fake
    Should Be Equal    ${status}    ${False}
    [Teardown]    Remove Environment Variable    QS_TESTER_FAKE_KEY

POST And Expect Field Passes On A Present Non-Empty Field
    ${body}=    POST And Expect Field    ${ECHO_PORT}    /full    ${{ {'task': 'x'} }}    200    result
    Should Be Equal    ${body}[result]    some text

POST And Expect Field Fails When The Field Is Missing
    ${status}=    Run Keyword And Return Status
    ...    POST And Expect Field    ${ECHO_PORT}    /none    ${{ {'task': 'x'} }}    200    result
    Should Be Equal    ${status}    ${False}

POST And Expect Field Fails When The Field Is Empty
    # The whole point of the keyword: a 200 with an empty field means the agent
    # produced nothing, which must not read as success.
    ${status}=    Run Keyword And Return Status
    ...    POST And Expect Field    ${ECHO_PORT}    /empty    ${{ {'task': 'x'} }}    200    result
    Should Be Equal    ${status}    ${False}

POST And Expect Field Skips The Field Check When No Field Is Named
    # Agent quickstarts whose README documents no response body assert the
    # status code only, until a live run reveals the real shape.
    ${body}=    POST And Expect Field    ${ECHO_PORT}    /none    ${{ {'task': 'x'} }}    200
    Should Not Be Empty    ${body}

Run Documented Commands Substitutes The Project Name
    ${commands}=    Create List    bash -c 'echo project={project} > ${TEMPDIR}/documented.txt'
    Run Documented Commands    ${commands}    qs-ci-demo-1
    ${content}=    Get File    ${TEMPDIR}/documented.txt
    Should Contain    ${content}    project=qs-ci-demo-1

Run Documented Commands Fails On The First Non-Zero Exit
    ${commands}=    Create List    bash -c 'exit 7'    bash -c 'echo unreachable > ${TEMPDIR}/unreachable.txt'
    Remove File    ${TEMPDIR}/unreachable.txt
    ${status}=    Run Keyword And Return Status
    ...    Run Documented Commands    ${commands}    qs-ci-demo-1
    Should Be Equal    ${status}    ${False}
    # Stopping at the first failure matters: a failed `project create` must not
    # be followed by an `agent create` whose error message hides the real cause.
    File Should Not Exist    ${TEMPDIR}/unreachable.txt

Wait Until Ready Marker Finds A Marker That Arrives Late
    Start Background Process    bash -c 'sleep 2; echo "Uvicorn running on http://127.0.0.1:8005"'
    ...    ${TEMPDIR}/ready.log    readytest
    Wait Until Ready Marker    ${TEMPDIR}/ready.log    Uvicorn running on
    [Teardown]    Stop Process Tree    readytest

Wait Until Ready Marker Fails When The Marker Never Arrives
    Set Test Variable    ${READINESS_TIMEOUT}    3s
    Create File    ${TEMPDIR}/never.log    starting up
    ${status}=    Run Keyword And Return Status
    ...    Wait Until Ready Marker    ${TEMPDIR}/never.log    Uvicorn running on
    Should Be Equal    ${status}    ${False}

*** Keywords ***
Start Echo Server
    Start Background Process    python ${CURDIR}/echo_server.py ${ECHO_PORT}
    ...    ${TEMPDIR}/echo.log    echo
    Wait Until Keyword Succeeds    20s    1s    Health Check Returns 200    ${ECHO_PORT}
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd tools/qs-tester && uv run robot --outputdir results/keywords resources/tests/keywords.robot`
Expected: every test fails with `No keyword with name 'Require Env Var' found` and similar.

- [ ] **Step 4: Add the two keywords to `quickstart.resource`**

Append to `tools/qs-tester/resources/quickstart.resource`:

```robot
Require Env Var
    [Documentation]    Fail unless ${name} is set to a non-empty value, naming the
    ...    quickstart that needs it. Agent quickstarts need a model provider key,
    ...    and a revoked or unset secret should read as a configuration error here
    ...    rather than as an opaque 401 from the provider several keywords later.
    ...    An empty value fails too: that is what a misconfigured GitHub secret
    ...    looks like, and a bare existence check would wave it through.
    [Arguments]    ${name}    ${quickstart}
    ${value}=    Get Environment Variable    ${name}    default=${EMPTY}
    Should Not Be Empty    ${value}
    ...    msg=${name} is not set, and the ${quickstart} quickstart needs it. Export it before running this suite; in CI it comes from the job's env block.

POST And Expect Field
    [Documentation]    POST ${payload} and assert the status code, plus (when
    ...    ${field} is given) that the named JSON field is present and non-empty.
    ...    Agent responses contain model output, so an exact body comparison is
    ...    impossible; presence and non-emptiness are what remains assertable.
    ...    Where a README documents no response body at all, pass no field and the
    ...    status code is the only assertion — weak on purpose, and honest about it.
    ...    The timeout is 120s rather than the 30s used elsewhere because a model
    ...    call sits inside this request.
    [Arguments]    ${port}    ${path}    ${payload}    ${status}    ${field}=${NONE}
    ${response}=    POST    http://localhost:${port}${path}    json=${payload}
    ...    expected_status=${status}    timeout=120
    ${body}=    Set Variable    ${response.json()}
    IF    $field is not None
        Dictionary Should Contain Key    ${body}    ${field}
        ...    msg=POST ${path} returned no "${field}" field.\nBody: ${body}
        Should Not Be Empty    ${body}[${field}]
        ...    msg=POST ${path} returned an empty "${field}".\nBody: ${body}
    END
    RETURN    ${body}
```

- [ ] **Step 5: Add the two keywords to `catalyst.resource`**

Append to `tools/qs-tester/resources/catalyst.resource`:

```robot
Run Documented Commands
    [Documentation]    Run an ordered list of documented commands, substituting the
    ...    ephemeral project name, and stop at the first non-zero exit.
    ...
    ...    Agent-family READMEs document their own provisioning (`project create
    ...    --enable-agent-infrastructure --wait --use`, `agent create`, `app
    ...    create`, `apply -f`), so the suite runs those commands verbatim instead
    ...    of an invented equivalent. Stopping at the first failure keeps the real
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
```

- [ ] **Step 6: Run the keyword tests**

Run: `cd tools/qs-tester && uv run robot --outputdir results/keywords resources/tests/keywords.robot`
Expected: PASS, 11 tests.

- [ ] **Step 7: Confirm nothing existing broke**

```bash
cd tools/qs-tester
uv run robot --outputdir results/smoke resources/tests/smoke.robot
uv run robot --dryrun --variable PROJECT:dryrun --outputdir results/dryrun \
  $(uv run python ci/list-suites.py --paths)
```

Expected: 5 smoke tests pass; the dryrun passes 16 tests.

- [ ] **Step 8: Commit**

```bash
git add tools/qs-tester/resources/catalyst.resource tools/qs-tester/resources/quickstart.resource \
        tools/qs-tester/resources/tests/echo_server.py tools/qs-tester/resources/tests/keywords.robot
git commit -m "Add keywords for documented commands, readiness markers, secrets and field assertions"
```

---

## Task 4: doc-sync loose mode for agent-family quickstarts

**Files:**
- Modify: `tools/qs-tester/docsync/check_readme_sync.py`
- Create: `tools/qs-tester/docsync/tests/test_agent_sync.py`

**Interfaces:**
- Consumes: `suites.agent_suites` (Task 1); `normalise_run_command` and `_FENCE` (existing).
- Produces: `all_bash_lines(markdown: str) -> list[str]`; `normalise_project(command: str, documented_project: str) -> str`; `check_agent(row: dict, repo_root: Path) -> list[str]`. Task 5's data module must satisfy the contract `check_agent` enforces; Task 6 relies on `--all` covering agent rows.

The data module contract `check_agent` enforces, which Task 5 implements:

| Name | Type | Meaning |
|---|---|---|
| `DOCUMENTED_PROJECT` | str | The project name the README uses, mapped onto `{project}` when comparing. |
| `SETUP` | tuple[str] | Documented provisioning commands, in documented order. Empty when the README documents none. |
| `INSTALL` | str or tuple[str] | Documented install command(s). |
| `RUN` | str | The documented `dev run` command, verbatim. |
| `TEARDOWN` | tuple[str] | Documented cleanup. Empty when the README documents none. |
| `READY_MARKERS` | tuple[str] | Readiness strings, one per app that announces itself. |
| `HEALTH_PORTS` | tuple[int] | Every port that must answer 200 on `GET /`. |
| `SECRETS` | tuple[str] | Environment variable names the quickstart needs. |
| `REQUESTS` | tuple[dict] | The documented calls, in order. Keys: `method`, `port`, `path`, `payload`, `status`; optional `field` (assert present and non-empty), `commands` (documented commands to run before this request), `log_marker` (assert after this request). |
| `UNCOVERED` | tuple[tuple[str, str]] | (command, reason) for documented commands the suite deliberately does not run. |

`commands` is what makes a documented multi-phase flow expressible. `mcp-auth/python` needs it: its documented sequence is call-fails-closed, `diagrid mcp grant`, call-succeeds, which is two requests where the second carries the grant command and expects a different status.

- [ ] **Step 1: Write the failing tests**

Create `tools/qs-tester/docsync/tests/test_agent_sync.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd tools/qs-tester && uv run pytest docsync/tests/test_agent_sync.py -q`
Expected: `ImportError: cannot import name 'all_bash_lines' from 'check_readme_sync'`.

- [ ] **Step 3: Implement loose mode**

Add to `tools/qs-tester/docsync/check_readme_sync.py`, after `normalise_run_command`:

```python
# Documented lines the harness deliberately expresses another way. Each entry is
# a prefix, with the reason it is not a command the suite runs.
_NOT_COMMANDS = (
    # The harness passes cwd= to the process instead of running `cd`.
    "cd ",
    # `diagrid login` is one of the two sanctioned exceptions: CI runs
    # `diagrid login --api-key "$DIAGRID_API_KEY"` because the documented bare
    # form blocks on an interactive browser prompt.
    "diagrid login",
    # Secrets arrive as environment variables from the CI job's env block, so
    # the documented `export FOO=...` has no harness equivalent to match.
    "export ",
    # The trigger is checked as a URL plus payload, not as a shell string,
    # because the README documents it three ways (curl, PowerShell, REST client).
    "curl",
)


def all_bash_lines(markdown):
    """Every command line in every ```bash block, anywhere in the file.

    Agent-family READMEs have named sections ("## Setup", "## Run with
    Catalyst"), not the numbered ones `_section_span` needs, so loose mode reads
    the whole file. Backslash continuations are joined first: the documented curl
    spans three lines, and comparing fragments would match nothing.
    """
    lines = []
    for lang, body in ((m.group(1), m.group(2)) for m in _FENCE.finditer(markdown)):
        if lang != "bash":
            continue
        joined = body.replace("\\\n", " ")
        for line in joined.splitlines():
            line = " ".join(line.split())
            if line and not line.startswith("#"):
                lines.append(line)
    return lines


def normalise_project(command, documented_project):
    """Map a documented command onto the harness's `{project}` placeholder."""
    return command.replace(documented_project, "{project}").strip()


def check_agent(row, repo_root, module=None):
    """Check one agent-family suite's data module against its README.

    Two directions, unlike the canonical check:

      documented -> harness   every documented bash line is either run by the
                              suite or listed in UNCOVERED with a reason
      harness -> documented   every command the suite runs appears in the README

    The second direction is what enforces the guiding principle. The first turns
    "out of scope" from a claim in prose into a list a machine checks, so a
    README that grows a new documented step fails CI until someone decides
    whether the suite should run it.
    """
    if module is None:
        module = importlib.import_module(row["data"])

    quickstart_dir = Path(row["suite"]).parent.parent
    readme = repo_root / quickstart_dir / "README.md"
    if not readme.is_file():
        return [f"{row['name']}: {readme} not found"]

    markdown = readme.read_text()
    where = row["name"]
    problems = []
    project = module.DOCUMENTED_PROJECT

    documented = [normalise_project(line, project) for line in all_bash_lines(markdown)]
    harness = [
        *module.SETUP,
        *_install_lines(module.INSTALL),
        module.RUN,
        *module.TEARDOWN,
        # A request's `commands` are documented commands like any other: mcp-auth's
        # `diagrid mcp grant` sits between two calls, so it belongs in this list
        # rather than escaping the check by being nested in a request.
        *[c for request in module.REQUESTS for c in request.get("commands", ())],
    ]
    harness = [normalise_project(command, project) for command in harness]
    excused = [normalise_project(command, project) for command, _ in module.UNCOVERED]

    for command in harness:
        if command not in documented:
            problems.append(
                f"{where}: harness runs a command that is not documented in the README:\n"
                f"  {command}\n  README has: {documented}"
            )

    for line in documented:
        if line.startswith(_NOT_COMMANDS):
            continue
        if line in harness or line in excused:
            continue
        problems.append(
            f"{where}: README documents a command nothing accounts for:\n"
            f"  {line}\n"
            "  Either run it from the suite, or add it to UNCOVERED with the reason."
        )

    for marker in module.READY_MARKERS:
        if marker not in markdown:
            problems.append(
                f"{where}: readiness marker {marker!r} does not appear in the README"
            )

    payloads = [call["payload"] for call in extract_curl_calls_anywhere(markdown)]
    for request in module.REQUESTS:
        url = f"http://localhost:{request['port']}{request['path']}"
        if url not in markdown:
            problems.append(f"{where}: request URL {url} does not appear in the README")
        if request["payload"] is not None and request["payload"] not in payloads:
            problems.append(
                f"{where}: request payload {request['payload']!r} is not documented.\n"
                f"  README documents: {payloads!r}"
            )

    for marker in [r["log_marker"] for r in module.REQUESTS if r.get("log_marker")]:
        if marker not in markdown:
            problems.append(f"{where}: log marker {marker!r} does not appear in the README")

    return problems


def _install_lines(install):
    """INSTALL is a single command or a tuple of them."""
    return [install] if isinstance(install, str) else list(install)


def extract_curl_calls_anywhere(markdown):
    """extract_curl_calls, but over the whole file rather than section 6."""
    calls = []
    for line in all_bash_lines(markdown):
        if not line.startswith("curl"):
            continue
        tokens = shlex.split(line)
        method, url, payload = "GET", None, None
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token in ("-X", "--request"):
                method, i = tokens[i + 1], i + 2
            elif token in ("-d", "--data"):
                try:
                    payload = json.loads(tokens[i + 1])
                except json.JSONDecodeError:
                    payload = None
                i += 2
            elif token in ("-H", "--header"):
                i += 2
            elif token.startswith("http"):
                url, i = token, i + 1
            else:
                i += 1
        calls.append({"method": method, "url": url, "payload": payload})
    return calls
```

Add `import importlib` to the imports at the top of the file, and extend `main()` so `--all` covers agent rows:

```python
    if args.all:
        pairs = [(a, l) for a in qs.APIS for l in qs.LANGUAGES]
    ...
    problems = []
    for api, language in pairs:
        problems.extend(check(api, language, args.repo_root))

    # Agent-family suites are registered in the manifest rather than being a
    # fixed api x language product, so they are checked from there.
    if args.all:
        import suites

        for row in suites.agent_suites():
            problems.extend(check_agent(row, args.repo_root))
```

- [ ] **Step 4: Run the tests**

Run: `cd tools/qs-tester && uv run pytest -q`
Expected: PASS, 49 tests (27 already on main, 10 manifest from Task 1, 12 agent-sync).

- [ ] **Step 5: Confirm the existing checker still passes**

Run: `cd tools/qs-tester && uv run python docsync/check_readme_sync.py --all`
Expected: `All 16 README(s) in sync with the harness`. No agent rows exist yet, so the new loop is a no-op.

- [ ] **Step 6: Commit**

```bash
git add tools/qs-tester/docsync/check_readme_sync.py tools/qs-tester/docsync/tests/test_agent_sync.py
git commit -m "Check agent-family READMEs against their data modules both ways"
```

---

## Task 5: The first agent-family suite (langgraph)

**Files:**
- Create: `tools/qs-tester/variables/agents_langgraph.py`
- Create: `agents/langgraph/tests/quickstart.robot`
- Modify: `tools/qs-tester/variables/suites.py` (add the row)
- Modify: `tools/qs-tester/ci/teardown-project.sh`
- Create: `tools/qs-tester/ci/project-name.sh`
- Create: `tools/qs-tester/ci/login.sh`

**Interfaces:**
- Consumes: all four keywords from Task 3; `${READINESS_TIMEOUT}` from Task 2; the data module contract from Task 4.
- Produces: the module-level names from Task 4's contract table (`SETUP`, `INSTALL`, `RUN`, `TEARDOWN`, `READY_MARKERS`, `HEALTH_PORTS`, `SECRETS`, `REQUESTS`, `UNCOVERED`, `DOCUMENTED_PROJECT`), plus `agents_langgraph.get_quickstart() -> dict` with keys `family, name, language, dir, setup, install, run, teardown, health_ports, secrets`. `READY_MARKERS` and `REQUESTS` are deliberately absent from that dict, and so is `activate_venv`; see Step 1. Also `ci/project-name.sh` exporting `PROJECT`, and `ci/login.sh`. Task 6 calls both scripts; Task 8's reference file describes this module as the template.

- [ ] **Step 1: Write the data module**

Create `tools/qs-tester/variables/agents_langgraph.py`:

```python
"""Data for the agents/langgraph end-to-end suite.

Every command here is transcribed verbatim from agents/langgraph/README.md, with
one substitution: the documented project name becomes `{project}`. The README is
the source of truth. Change the README, change this file, and
`docsync/check_readme_sync.py --all` will tell you if you changed only one.

Unlike the canonical quickstarts, this README documents its own provisioning, so
SETUP runs the documented `project create` and `agent create` rather than the
invented flags in ci/setup-project.sh. The `dev run` command stays bare because
the documented `project create` carries `--use`: reproducing that dependency is
deliberate, so that a regression in `--use` breaks this suite instead of
silently breaking readers.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

FAMILY = "agents"
NAME = "langgraph"
LANGUAGE = "python"

# README "## Run with Catalyst", step 2. Replaced by an ephemeral qs-ci-* name at
# run time; also what doc-sync maps onto `{project}` when comparing.
DOCUMENTED_PROJECT = "langgraph-quickstart"

QUICKSTART_DIR = str(REPO_ROOT / "agents" / "langgraph")

# README "## Run with Catalyst", steps 2 and 3.
SETUP = (
    "diagrid project create {project} --enable-agent-infrastructure --wait --use",
    "diagrid agent create langgraph-agent --wait",
)

# README "## Setup". The documented `cd agents/langgraph` is expressed as the
# working directory instead of a command.
INSTALL = "uv sync"

# README "## Run with Catalyst", step 4. Bare on purpose: see the module docstring.
RUN = "uv run diagrid dev run -f dev-python-langgraph.yaml --approve"

# Empty on purpose: this README documents no cleanup command. It has no
# "## Clean Up" section, unlike agents/microsoft-dotnet (which documents
# `diagrid project delete dotnet-quickstart`) and the canonical READMEs (section
# 7). Deleting the project is therefore infrastructure, not a documented step, and
# ci/teardown-project.sh owns it. Adding a plausible-looking `project delete` here
# would be inventing a documented command, and doc-sync would correctly reject it.
TEARDOWN = ()

# README: "Wait until the output shows `Uvicorn running on <localhost:port>`."
# Truncated before the address, which varies. A tuple because multi-app
# quickstarts announce themselves once per app: dapr-agents/multi-agent-workflow
# runs three. langgraph has one.
READY_MARKERS = ("Uvicorn running on",)

# appPort in dev-python-langgraph.yaml, and the port the documented curl targets.
HEALTH_PORTS = (8005,)

SECRETS = ("OPENAI_API_KEY",)

# The documented calls, in documented order. README "### 2. Trigger a Workflow".
#
# Optional keys a request may carry, unused here:
#   commands    documented commands to run before this request, for flows that
#               interleave CLI and HTTP (mcp-auth grants a tool between two calls)
#   log_marker  a string to wait for in the dev-run output after this request
#
# `field` is None because no README documents a response body for /agent/run, and
# the endpoint is served by DaprWorkflowGraphRunner.serve() from an external
# package, so the field name cannot be read out of this repo. The suite asserts
# the documented status code only. Fill this in from an observed live response,
# with a comment naming that response as the source; guessing a field name
# produces an assertion that looks like coverage and fails for the wrong reason.
# This is the same weak-assertion tradeoff the harness already accepts for the
# undocumented `GET /workflow/status/{id}` bodies.
REQUESTS = (
    {
        "method": "POST",
        "port": 8005,
        "path": "/agent/run",
        "payload": {"task": "Check if the Grand Ballroom is available on March 15th"},
        "status": 200,
        "field": None,
        # The README describes the agent using the `check_availability` tool, and
        # main.py defines it. Model output varies; the tool call is what the
        # quickstart actually promises, so that is what this asserts.
        "log_marker": "check_availability",
    },
)

# Documented commands this suite deliberately does not run, each with its reason.
# doc-sync fails if a documented command is in neither this tuple nor the suite,
# so a new documented step forces a decision instead of being quietly ignored.
UNCOVERED = (
    (
        "uv run diagrid dev run -f dev-crash-test.yaml --approve",
        "crash-recovery flow requires editing crash_test.py to comment out "
        "os._exit(1); source edits are out of scope",
    ),
    (
        "uv run diagrid dev run -f dev-crash-test.yaml",
        "the second half of the same crash-recovery flow",
    ),
)


def get_quickstart():
    """Everything the suite needs, in one flat dict.

    Robot calls this as a keyword: `${qs}=  Get Quickstart`. Mirrors the shape
    quickstarts.get_quickstart returns so the shared keywords need no changes.
    """
    return {
        "family": FAMILY,
        "name": NAME,
        "language": LANGUAGE,
        "dir": QUICKSTART_DIR,
        "setup": list(SETUP),
        "install": INSTALL,
        "run": RUN,
        "teardown": list(TEARDOWN),
        "health_ports": list(HEALTH_PORTS),
        "secrets": list(SECRETS),
    }
```

No `activate_venv` key: `Start Quickstart` stopped reading one when the python
quickstarts became uv workspaces, and `catalyst.resource` no longer has the
`bash -c '. .venv/bin/activate && ...'` branch. Every documented python run command
is now `uv run diagrid dev run`, which resolves the environment itself.

**Note what this dict deliberately omits: `READY_MARKERS` and `REQUESTS`.** A value
returned by a Python keyword cannot be overridden from the command line, so a
mutation check against `get_quickstart()["ready_markers"]` would run with the real
markers, pass, and "prove" an assertion sound while proving nothing. The suite
reads `@{READY_MARKERS}` and `@{REQUESTS}` from the `Variables` import instead,
which a `--variablefile` override does replace. The dict keeps only what whole-dict
keywords need (`Build Quickstart`, `Start Quickstart`, `Wait Until Apps Healthy`)
plus the secrets loop.

- [ ] **Step 2: Write the suite**

Create `agents/langgraph/tests/quickstart.robot`:

```robot
*** Comments ***
End-to-end test for the agents/langgraph quickstart (python only: this
quickstart has one implementation, unlike the canonical four-language APIs).

Mirrors agents/langgraph/README.md: "## Setup" installs, "## Run with Catalyst"
provisions and runs, "### 2. Trigger a Workflow" triggers. This README documents
no cleanup command, so deleting the project is infrastructure here. The
crash-recovery flow is deliberately absent; see UNCOVERED in
variables/agents_langgraph.py for why.

The request loop below is the shape every agent-family suite uses, including ones
whose documented flow interleaves CLI commands with HTTP calls: a request may
carry `commands` to run first and a `log_marker` to wait for afterwards.

Run it:
  export DIAGRID_API_KEY=... OPENAI_API_KEY=...
  eval "$(bash tools/qs-tester/ci/project-name.sh agents-langgraph | grep '^PROJECT=')"
  bash tools/qs-tester/ci/login.sh
  cd tools/qs-tester
  uv run robot --variable PROJECT:$PROJECT --outputdir results/agents-langgraph \
    ../../agents/langgraph/tests/quickstart.robot
  bash ci/teardown-project.sh "$PROJECT"

*** Settings ***
Resource        ../../../tools/qs-tester/resources/catalyst.resource
Resource        ../../../tools/qs-tester/resources/quickstart.resource
# Imported twice on purpose, same as the canonical suites: `Variables` exposes
# the module-level names (@{REQUESTS}, @{READY_MARKERS}), `Library` exposes
# get_quickstart as a keyword. Neither import alone gives both.
Variables       ../../../tools/qs-tester/variables/agents_langgraph.py
Library         ../../../tools/qs-tester/variables/agents_langgraph.py
Library         Collections
Suite Setup     Should Not Be Empty    ${PROJECT}
...             msg=Pass --variable PROJECT:<catalyst-project-name>
Test Teardown   Clean Up Quickstart

*** Variables ***
${PROJECT}      ${EMPTY}

*** Test Cases ***
Python Langgraph Quickstart
    [Tags]    python    langgraph    agents
    ${qs}=      Get Quickstart
    ${log}=     Suite Log File    agents-langgraph    python

    # A missing model key must fail here, before a project is created, rather
    # than as a 401 from OpenAI several minutes later.
    FOR    ${secret}    IN    @{qs}[secrets]
        Require Env Var    ${secret}    agents/langgraph
    END

    Build Quickstart            ${qs}
    # README "## Run with Catalyst" steps 2-3, run verbatim.
    Run Documented Commands     ${qs}[setup]    ${PROJECT}    cwd=${qs}[dir]
    Start Quickstart            ${qs}    ${PROJECT}    ${log}

    # @{READY_MARKERS} and @{REQUESTS} come from the `Variables` import, NOT from
    # ${qs}, and that is deliberate: a --variablefile override replaces a variable
    # file's value but cannot touch what a Python keyword returned. Reading these
    # from ${qs} would make the mutation check run with the real markers, pass, and
    # prove nothing. One marker per app that announces itself.
    FOR    ${marker}    IN    @{READY_MARKERS}
        Wait Until Ready Marker    ${log}    ${marker}
    END
    Wait Until Apps Healthy     ${qs}

    # The documented calls, in documented order. README "### 2. Trigger a Workflow".
    # `commands` and `log_marker` are optional per request: a flow that interleaves
    # CLI and HTTP (mcp-auth grants a tool between two calls) expresses that here
    # rather than needing its own bespoke suite.
    # Every optional key is read with a default, so a request that needs none of
    # them stays a five-key dict instead of carrying explicit nulls.
    FOR    ${request}    IN    @{REQUESTS}
        # `Evaluate`, not `Get From Dictionary ... default=`: the default has to be an
        # empty SEQUENCE. A ${EMPTY} default is an empty string, and Run Documented
        # Commands would fail iterating it with "not list or list-like" for every
        # request that carries no commands, which is most of them.
        ${commands}=    Evaluate    $request.get('commands', ())
        Run Documented Commands    ${commands}    ${PROJECT}    cwd=${qs}[dir]
        ${field}=       Get From Dictionary    ${request}    field          default=${NONE}
        # POST-only on purpose: every documented agent trigger is a POST. A
        # documented GET belongs in `GET And Expect` from quickstart.resource, and
        # a suite that needs one should branch on ${request}[method] here.
        Should Be Equal    ${request}[method]    POST
        ...    msg=Only POST requests are handled here; use GET And Expect for a documented GET.
        POST And Expect Field    ${request}[port]    ${request}[path]    ${request}[payload]
        ...    ${request}[status]    ${field}
        ${marker}=      Get From Dictionary    ${request}    log_marker     default=${NONE}
        IF    $marker is not None
            Wait Until Log Contains    ${log}    ${marker}
        END
    END

*** Keywords ***
Clean Up Quickstart
    [Documentation]    Stop the apps, then run whatever cleanup the README
    ...    documents. `Stop Quickstart` also calls `diagrid dev stop`, which
    ...    releases the local app connections.
    ...
    ...    langgraph's TEARDOWN is empty, because its README documents no cleanup
    ...    command, so the loop is a no-op here and ci/teardown-project.sh deletes
    ...    the project. The call stays because other agent quickstarts do document
    ...    deletion (agents/microsoft-dotnet documents `diagrid project delete`),
    ...    and this keyword is the template they copy.
    Run Keyword And Ignore Error    Stop Quickstart    ${PROJECT}
    ${qs}=    Get Quickstart
    Run Keyword And Ignore Error
    ...    Run Documented Commands    ${qs}[teardown]    ${PROJECT}
```

- [ ] **Step 3: Register the suite in the manifest**

Add to `SUITES` in `tools/qs-tester/variables/suites.py`, after the four canonical rows:

```python
    {
        "suite": "agents/langgraph/tests/quickstart.robot",
        "family": "agent",
        "name": "langgraph",
        "data": "agents_langgraph",
        "language": "python",
        "runtime": "python",
        # False until this suite has had a green live run and a mutation check
        # proving its assertions can fail. A suite that has never run against real
        # Catalyst would fail the nightly build every night for everyone, and a
        # nightly failure also leaks its project until reap-orphans.sh collects it.
        # Flip to True in the same commit that records the live-run evidence; the
        # dispatch-triggered path runs it before then.
        "nightly": False,
        "secrets": ("OPENAI_API_KEY",),
    },
```

- [ ] **Step 4: Write the two CI helper scripts**

Create `tools/qs-tester/ci/project-name.sh`:

```bash
#!/usr/bin/env bash
# Compute the ephemeral Catalyst project name for one leg. No CLI calls, so it
# cannot fail partway and leave the name unknown.
#
# Agent-family suites provision themselves from their README's documented
# commands, but the name still has to be known BEFORE the suite runs: teardown
# runs under `if: always()`, and a suite that dies inside its documented
# `project create` would otherwise leak a project until reap-orphans.sh.
#
# Reads:  $1 (leg id, e.g. agents-langgraph), GITHUB_RUN_ID (optional)
# Writes: PROJECT to $GITHUB_ENV under Actions; always echoes it.
set -euo pipefail

LEG="${1:-}"
if [ -z "$LEG" ]; then
  echo "::error::Usage: project-name.sh <leg-id>   (e.g. agents-langgraph)" >&2
  exit 1
fi

RUN_ID="${GITHUB_RUN_ID:-local$(date +%s)}"
# The qs-ci- prefix is load-bearing: reap-orphans.sh collects leaked projects by
# that pattern. A name without it leaks forever.
PROJECT="qs-ci-${LEG}-${RUN_ID}"

echo "PROJECT=$PROJECT"
if [ -n "${GITHUB_ENV:-}" ]; then
  echo "PROJECT=$PROJECT" >> "$GITHUB_ENV"
fi
```

Create `tools/qs-tester/ci/login.sh`:

```bash
#!/usr/bin/env bash
# Authenticate the diagrid CLI with an API key.
#
# This is one of the two sanctioned deviations from running documented commands
# verbatim: every quickstart README documents a bare `diagrid login`, which
# blocks on an interactive browser prompt and would hang CI forever. The CLI
# does not read DIAGRID_API_KEY on its own, so --api-key is mandatory.
set -euo pipefail

if [ -z "${DIAGRID_API_KEY:-}" ]; then
  echo "::error::DIAGRID_API_KEY is not set; the login would block on an" >&2
  echo "interactive browser prompt and the job would hang." >&2
  exit 1
fi

diagrid login --api-key "$DIAGRID_API_KEY"
```

- [ ] **Step 5: Make teardown quiet when the project is already gone**

Agent quickstarts whose README documents `diagrid project delete` (for example `agents/microsoft-dotnet`) delete the project as part of the test, so `teardown-project.sh` then finds nothing and, as written today, ends a green leg with a misleading `::warning::Failed to delete`. langgraph documents no cleanup, so its project is still there and this script does the deleting; both paths have to be quiet about the normal case.

In `tools/qs-tester/ci/teardown-project.sh`, replace the final `if diagrid project delete ...` block with:

```bash
# Agent-family suites run their README's documented `diagrid project delete` as
# part of the test, so by the time this runs the project is usually already gone.
# Check first, so a green run does not end with a misleading warning. This script
# still matters: it is the safety net for a suite that died before its teardown.
if ! diagrid project get "$PROJECT" >/dev/null 2>&1; then
  echo "Project $PROJECT no longer exists; nothing to delete."
  exit 0
fi

echo "Deleting project $PROJECT"
# Deliberately not `set -e`: a delete failure should be visible but must not mask
# the real test failure that is already being reported.
# --yes confirmed via `diagrid project delete --help` (CLI 1.36.0): skips the
# interactive confirmation prompt. `--approve` is a documented synonym.
if diagrid project delete "$PROJECT" --yes; then
  echo "Deleted $PROJECT"
else
  echo "::warning::Failed to delete $PROJECT — reap-orphans.sh will collect it."
fi
```

- [ ] **Step 6: Run every credential-free check**

```bash
cd tools/qs-tester
uv run python ci/list-suites.py --validate
uv run python docsync/check_readme_sync.py --all
uv run pytest -q
uv run robot --dryrun --variable PROJECT:dryrun --outputdir results/dryrun \
  $(uv run python ci/list-suites.py --paths)
uv run python ci/list-suites.py --matrix agent
bash ci/project-name.sh agents-langgraph
```

Expected: manifest valid (5 suites); doc-sync reports 16 canonical READMEs in sync and no agent problems; 49 tests pass (27 already on main, 10 manifest, 12 agent-sync); the dryrun now resolves 17 tests; the matrix prints one JSON object; the name script prints `PROJECT=qs-ci-agents-langgraph-local<epoch>`.

If doc-sync reports a problem, fix `agents_langgraph.py` to match the README, not the other way around. Consult `agents/langgraph/README.md` and re-read the guiding principle first.

- [ ] **Step 7: Commit the static-green state**

```bash
git add tools/qs-tester/variables/agents_langgraph.py agents/langgraph/tests/quickstart.robot \
        tools/qs-tester/variables/suites.py tools/qs-tester/ci/project-name.sh \
        tools/qs-tester/ci/login.sh tools/qs-tester/ci/teardown-project.sh
chmod +x tools/qs-tester/ci/project-name.sh tools/qs-tester/ci/login.sh
git commit -m "Add the agents/langgraph end-to-end suite"
```

- [ ] **Step 8: Live verification (needs credentials)**

This step needs `DIAGRID_API_KEY` and `OPENAI_API_KEY`, and it creates a real Catalyst project with agent infrastructure. It is the only proof the suite works.

```bash
export DIAGRID_API_KEY=...
export OPENAI_API_KEY=...
eval "$(bash tools/qs-tester/ci/project-name.sh agents-langgraph | grep '^PROJECT=')"
bash tools/qs-tester/ci/login.sh
cd tools/qs-tester
uv run robot --variable PROJECT:$PROJECT --outputdir results/agents-langgraph \
  ../../agents/langgraph/tests/quickstart.robot
```

Expected: PASS, 1 test. If it fails, read `results/agents-langgraph/agents-langgraph-python-dev-run.log` first: readiness and marker failures are always clearest there.

**If you do not have both keys, stop here and report BLOCKED**, naming which key is missing and quoting these commands. Do not mark this task complete and do not proceed to Task 6: an unrun suite in the CI matrix fails every night for everyone.

- [ ] **Step 9: Record the observed response shape**

The live run prints the `/agent/run` response body in `results/agents-langgraph/log.html` (expand `POST And Expect Field`). If it contains a stable non-empty field, set that request's `field` to its name and replace the placeholder comment with one naming the live response as the source, for example:

```python
    # Observed in a live run on 2026-07-31: {"output": "...", "instance_id": "..."}.
    # No README documents this shape, so this field name comes from that response.
    "field": "output",
```

Then re-run Step 8 to confirm the stronger assertion still passes, and `uv run pytest -q` plus `check_readme_sync.py --all` to confirm nothing else moved.

- [ ] **Step 10: Mutation check**

Prove the readiness assertion is not vacuous, reusing the same project so no second provisioning is needed.

`READY_MARKERS` is a tuple, and `robot --variable` can only set scalars, so the override goes through a generated variable file. A CLI `--variablefile` takes precedence over the suite's own `Variables` import, and this works the same way for scalars and tuples with no type guessing:

```bash
cd tools/qs-tester
mkdir -p results/mutation
cat > results/mutation/mutate.py <<'EOF'
READY_MARKERS = ("__mutation_check__",)
EOF
uv run robot --variable PROJECT:$PROJECT \
  --variablefile results/mutation/mutate.py \
  --variable READINESS_TIMEOUT:20s \
  --outputdir results/agents-langgraph-mutated \
  ../../agents/langgraph/tests/quickstart.robot
```

Expected: FAIL within roughly 20 seconds, with `Log ... does not contain "__mutation_check__"`.

A PASS here means the readiness assertion never fails and is therefore worthless. Do not proceed. The likeliest cause is the suite reading the marker out of `get_quickstart()` instead of the `Variables` import, which no override can reach; the second likeliest is `--variablefile` pointing at a path that does not exist, which Robot reports as an error rather than silently ignoring, so check the console output before assuming the assertion is at fault.

- [ ] **Step 11: Tear down and commit**

```bash
bash tools/qs-tester/ci/teardown-project.sh "$PROJECT"
git add tools/qs-tester/variables/agents_langgraph.py
git commit -m "Record the observed langgraph trigger response field"
```

Confirm the deletion: `diagrid project list | grep "$PROJECT"` must print nothing. These projects are not free.

---

## Task 6: CI wiring

**Files:**
- Modify: `.github/workflows/e2e-quickstarts.yml`

**Interfaces:**
- Consumes: `ci/list-suites.py --paths|--matrix|--validate` (Task 1); `ci/project-name.sh`, `ci/login.sh`, `ci/teardown-project.sh` (Task 5); `resources/tests/keywords.robot` (Task 3).
- Produces: a `discover` job with output `agents`; an `e2e-agents` job whose artifacts are named `robot-agents-<name>` and whose failure files are `failed-agents-<name>.txt`.

- [ ] **Step 1: Replace the lint job's hardcoded paths and add manifest validation**

In the `lint` job, replace the `Resolve suites without executing` step and add a validation step before it:

```yaml
      - name: Validate the suite manifest
        run: (cd tools/qs-tester && uv run python ci/list-suites.py --validate)
      - name: Resolve suites without executing
        run: |
          cd tools/qs-tester
          uv run robot --dryrun --variable PROJECT:dryrun --outputdir results/dryrun \
            $(uv run python ci/list-suites.py --paths)
```

Also extend the smoke step to cover the new keyword suite:

```yaml
      - name: Smoke-test the harness keywords
        run: |
          cd tools/qs-tester
          uv run robot --outputdir results/smoke \
            resources/tests/smoke.robot resources/tests/keywords.robot
```

- [ ] **Step 2: Add the discover job**

Insert after the `reap` job:

```yaml
  # The agents matrix comes from the suite manifest rather than being written out
  # here, so registering a suite is one row in variables/suites.py and no YAML
  # edit at all.
  discover:
    if: github.event_name != 'pull_request' && github.repository_owner == 'diagridio'
    runs-on: ubuntu-latest
    outputs:
      agents: ${{ steps.list.outputs.agents }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - name: Sync harness
        run: (cd tools/qs-tester && uv sync)
      - id: list
        name: List agent suites
        run: |
          cd tools/qs-tester
          # A scheduled run takes only the suites opted into `nightly`, because
          # each one costs a project with agent infrastructure plus real model
          # tokens. A manual dispatch runs every registered agent suite.
          nightly=""
          if [ "${{ github.event_name }}" = "schedule" ]; then
            nightly="--nightly"
          fi
          agents="$(uv run python ci/list-suites.py --matrix agent $nightly)"
          echo "agents=$agents" >> "$GITHUB_OUTPUT"
          echo "Agent suites for this run: $agents"
```

- [ ] **Step 3: Add the e2e-agents job**

Insert after the `e2e` job:

```yaml
  # Runs AFTER e2e, not alongside it. `max-parallel` is per-job, so two jobs at
  # 2 would allow four concurrent Catalyst projects and break the two-project
  # cap this workflow's concurrency comment relies on. `always()` is what still
  # runs these suites when a language leg failed: a nightly run should report
  # every broken quickstart, not stop at the first.
  e2e-agents:
    needs: [e2e, discover]
    if: >-
      always()
      && github.event_name != 'pull_request'
      && github.repository_owner == 'diagridio'
      && needs.discover.result == 'success'
      && needs.discover.outputs.agents != '[]'
    runs-on: ubuntu-latest
    environment: shared-production
    timeout-minutes: 60
    strategy:
      fail-fast: false
      max-parallel: 2
      matrix:
        include: ${{ fromJSON(needs.discover.outputs.agents) }}
    env:
      DIAGRID_API_KEY: ${{ secrets.DIAGRID_API_KEY }}
      # Declared literally rather than indexed from the matrix so the set of
      # providers this workflow can reach is greppable. A suite only needs the
      # one in its manifest row, and `Require Env Var` fails loudly if it is
      # missing or empty.
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5

      - name: Set up .NET
        if: matrix.runtime == 'dotnet'
        uses: actions/setup-dotnet@v4
        with:
          dotnet-version: '10.0.x'

      - name: Set up Java
        if: matrix.runtime == 'java'
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '17'

      - name: Set up Node
        if: matrix.runtime == 'javascript'
        uses: actions/setup-node@v4
        with:
          node-version: 'lts/*'

      - name: Install diagrid CLI
        run: |
          curl -sL https://downloads.diagrid.io/cli/install.sh | RELEASE_VERSION="$DIAGRID_CLI_VERSION" bash
          sudo mv ./diagrid /usr/local/bin
          diagrid version

      - name: Sync harness
        run: (cd tools/qs-tester && uv sync)

      # The suite provisions itself from its README's documented commands, but the
      # project name must be known before that can fail, so teardown always has
      # something to delete.
      - name: Compute the ephemeral project name
        run: bash tools/qs-tester/ci/project-name.sh agents-${{ matrix.name }}

      - name: Log in to Catalyst
        run: bash tools/qs-tester/ci/login.sh

      - name: Run the suite
        run: |
          cd tools/qs-tester
          if ! uv run robot --outputdir "results/agents-${{ matrix.name }}" \
               --variable "PROJECT:$PROJECT" \
               "../../${{ matrix.suite }}"; then
            echo "agents/${{ matrix.name }}" > "results/failed-agents-${{ matrix.name }}.txt"
            echo "::error::Agent suite failed: agents/${{ matrix.name }}"
            exit 1
          fi

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: robot-agents-${{ matrix.name }}
          path: tools/qs-tester/results/

      - name: Delete the ephemeral Catalyst project
        if: always()
        run: bash tools/qs-tester/ci/teardown-project.sh
```

- [ ] **Step 4: Extend the report job and the PR paths**

Change the `report` job's `needs` to include the new job:

```yaml
    needs: [lint, e2e, e2e-agents]
```

Its `github-script` step already walks every artifact for `failed-*.txt`, so `failed-agents-<name>.txt` is picked up with no script change. Its download step uses `continue-on-error: true`, so a skipped `e2e-agents` job cannot break it.

In the `pull_request.paths` list, add the agent-family suite location:

```yaml
      - 'tools/qs-tester/**'
      - '*/tests/quickstart.robot'
      - '*/*/tests/quickstart.robot'
      - '*/*/README.md'
      - '.github/workflows/e2e-quickstarts.yml'
```

`'tools/qs-tester/**'` already covers the manifest and the data modules.

- [ ] **Step 5: Validate the workflow file**

```bash
python3 -c "import sys,yaml,json;d=yaml.safe_load(open('.github/workflows/e2e-quickstarts.yml'));print(json.dumps(sorted(d['jobs']),indent=0));print(d['jobs']['e2e-agents']['needs']);print(d['jobs']['report']['needs'])"
```

Expected: jobs `discover, e2e, e2e-agents, lint, reap, report`; `e2e-agents` needs `['e2e', 'discover']`; `report` needs `['lint', 'e2e', 'e2e-agents']`.

If `actionlint` is available, run `actionlint .github/workflows/e2e-quickstarts.yml` too. If PyYAML is not installed system-wide, use `uvx --with pyyaml python -c ...` rather than adding it to the harness: Global Constraints forbid a new harness dependency.

- [ ] **Step 6: Re-run every credential-free check**

```bash
cd tools/qs-tester
uv run python ci/list-suites.py --validate
uv run pytest -q
uv run python docsync/check_readme_sync.py --all
uv run robot --dryrun --variable PROJECT:dryrun --outputdir results/dryrun \
  $(uv run python ci/list-suites.py --paths)
uv run robot --outputdir results/smoke resources/tests/smoke.robot resources/tests/keywords.robot
```

Expected: all green, exactly as the lint job will run them.

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/e2e-quickstarts.yml
git commit -m "Run agent-family suites from the manifest in a serialised CI job"
```

- [ ] **Step 8: Verify in CI with a single dispatch before trusting the nightly**

Push the branch, open a PR (which runs `lint` only), and confirm it is green. Then, from the Actions tab, dispatch the workflow once on this branch and confirm `discover` emits the langgraph row and `e2e-agents` runs it green.

Do not skip to the nightly schedule: the first real run is the one most likely to reveal a missing secret, and a failed nightly leaks a project until the reaper collects it.

---

## Task 7: Documentation

**Files:**
- Modify: `tools/qs-tester/README.md`
- Modify: `docs/superpowers/specs/2026-07-31-quickstart-e2e-test-skill-design.md`

**Interfaces:**
- Consumes: everything from Tasks 1-6.
- Produces: the runbook Task 8's SKILL.md points readers at.

- [ ] **Step 1: Document the manifest and agent-family suites**

While in this file, resolve its dangling design pointer. Line 9 reads
`Design: docs/superpowers/specs/2026-07-28-quickstart-e2e-tests-design.md`, and that
file is not in the repository: commit `622e732` removed the committed design and plan
documents, and this pointer was missed. Either point it at a spec that is actually
committed or drop the line. Do not leave a reference to a file a reader cannot open.

In `tools/qs-tester/README.md`, add to the `## Layout` list:

```markdown
- `variables/suites.py` — the registry of every suite. The lint dryrun, the CI
  agents matrix and doc-sync all read it, so registering a suite is one row here
  rather than three edits in the workflow.
- `variables/agents_<name>.py` — one per agent-family quickstart, holding that
  quickstart's documented command sequence verbatim.
- `ci/list-suites.py` — reads the manifest for CI (`--paths`, `--matrix agent`,
  `--validate`).
- `ci/project-name.sh`, `ci/login.sh` — the ephemeral name, and the API-key login.
```

- [ ] **Step 2: Add a section on the two conventions**

Add after `### Selecting languages and APIs`:

```markdown
### Two kinds of quickstart

The canonical APIs (`workflow`, `state`, `pubsub`, `invocation`) are an
(api × language) matrix: one suite per API, four language-tagged tests, all data
in `variables/quickstarts.py`.

Agent-family quickstarts (`agents/*`, `dapr-agents/*`, `mcp-auth/*`) are a flat
list. Each has exactly one language, its own suite at
`<family>/<name>/tests/quickstart.robot`, and its own data module. Three things
differ and are worth knowing before you touch one:

1. **They provision themselves.** Their READMEs document `diagrid project create`
   (with `--enable-agent-infrastructure` for `agents/*`), `agent create` and
   sometimes `app create` and `apply -f`, so the suite runs those documented
   commands through `Run Documented Commands`. `ci/setup-project.sh` is for the
   canonical suites, whose READMEs document no provisioning at all.
2. **The `dev run` command can be bare.** `agents/*` documents
   `project create ... --use` followed by a `dev run` with no `--project`. The
   suite reproduces that exactly, so a regression in `--use` fails here.
3. **Assertions are structural.** Responses contain model output, so the suites
   assert the documented status code, a named field being present and non-empty
   where a response shape is known, and a log marker showing the expected tool
   ran.

Nightly membership is per suite (`nightly` in the manifest). Each agent leg costs
a project with agent infrastructure plus real model tokens, so suites left at
`nightly: False` run only on `workflow_dispatch`.
```

- [ ] **Step 3: Add the runbook for a live agent-family run**

```markdown
### Running an agent-family suite locally

```bash
export DIAGRID_API_KEY=...
export OPENAI_API_KEY=...           # whichever secrets the manifest row lists
eval "$(bash tools/qs-tester/ci/project-name.sh agents-langgraph | grep '^PROJECT=')"
bash tools/qs-tester/ci/login.sh
cd tools/qs-tester
uv run robot --variable PROJECT:$PROJECT --outputdir results/agents-langgraph \
  ../../agents/langgraph/tests/quickstart.robot
bash ci/teardown-project.sh "$PROJECT"
```

The suite runs the README's documented `diagrid project delete` itself, so
`teardown-project.sh` usually finds nothing and says so. It stays in the sequence
because it is the safety net for a suite that died before its own teardown.

To prove an assertion is not vacuous, re-run against the same project with the
assertion broken and require a failure. The override goes through a generated
variable file because `--variable` can only set scalars, and the interesting
targets (`READY_MARKERS`, `REQUESTS`) are tuples:

```bash
mkdir -p results/mutation
cat > results/mutation/mutate.py <<'EOF'
READY_MARKERS = ("__mutation_check__",)
EOF
uv run robot --variable PROJECT:$PROJECT \
  --variablefile results/mutation/mutate.py --variable READINESS_TIMEOUT:20s \
  --outputdir results/mutated ../../agents/langgraph/tests/quickstart.robot
```

A PASS means the assertion never fails and is worthless.
```

- [ ] **Step 4: Update the Limitations section**

Replace the first Limitations bullet, which says nothing in the harness has been run against real Catalyst, with the current truth. Record which suites have had a live run, which have had a mutation check, and what remains unproven. Keep the three numbered unproven items that still apply, and add:

```markdown
- **Model nondeterminism.** Agent-family suites assert structure, not content: a
  documented status code, a non-empty named field where a shape is known, and a
  tool-call log marker. A model refusal, a rate limit or an unusually slow
  completion can fail a leg without anything being wrong in the quickstart.
  There is no retry; if this proves noisy, one retry on the trigger request is
  the first thing to try.
- **One mutation check per suite** proves one assertion. The others are unproven
  in the same sense as the log markers above.
```

- [ ] **Step 5: Reconcile the spec with what was built**

Update `docs/superpowers/specs/2026-07-31-quickstart-e2e-test-skill-design.md` for the refinements this plan made. Keep the spec's reasoning intact; only the mechanisms changed.

1. `${MARKER_TIMEOUT}` plus `${READINESS_TIMEOUT}`, rather than one variable.
2. doc-sync loose mode is total via `UNCOVERED`, rather than one-way.
3. The `TEARDOWN` of a quickstart whose README documents no cleanup is empty, and deletion falls to `ci/teardown-project.sh` as infrastructure. langgraph is that case, so the spec's example should not imply every agent quickstart documents a delete.
4. `REQUESTS` is an ordered tuple whose entries may carry `commands` and `log_marker`, and `READY_MARKERS` is a tuple. Record why: `mcp-auth` interleaves CLI commands with HTTP calls, and `dapr-agents/multi-agent-workflow` runs three apps.
5. The mutation check overrides through a generated `--variablefile`, not `--variable`, because `--variable` cannot set a tuple.
6. Phase 2 gains the undocumented-provisioning decision path: leave `SETUP` empty and ask which `ci/setup-project.sh` flags the project needs, rather than guessing.

Also confirm the spec's manifest field list matches `variables/suites.py` as built. The spec listed an `agent_infra` flag and an agent name per row; both became dead fields once the suite ran the documented `project create` and `agent create` itself, so they are not in the manifest.

- [ ] **Step 6: Commit**

```bash
git add tools/qs-tester/README.md docs/superpowers/specs/2026-07-31-quickstart-e2e-test-skill-design.md
git commit -m "Document the suite manifest and agent-family suites"
```

---

## Task 8: The skill's instructions

**Files:**
- Create: `.claude/skills/add-quickstart-e2e-test/SKILL.md`
- Create: `.claude/skills/add-quickstart-e2e-test/references/canonical-api.md`
- Create: `.claude/skills/add-quickstart-e2e-test/references/agent-quickstart.md`
- Create: `.claude/skills/add-quickstart-e2e-test/references/harness-keywords.md`

**Interfaces:**
- Consumes: every artifact from Tasks 1-7. The reference files describe the real APIs, so this task must come after them.
- Produces: the skill Task 9's scripts are invoked from and Task 10 evaluates.

- [ ] **Step 1: Write SKILL.md**

```markdown
---
name: add-quickstart-e2e-test
description: Add a Robot Framework end-to-end test for a quickstart in this repository and wire it into the nightly GitHub Actions workflow. Use this whenever someone wants a quickstart covered by tests or CI, in any phrasing, including "add an e2e test for the langgraph quickstart", "the microsoft-dotnet quickstart has no CI coverage", "write a Robot test for mcp-auth", "we just added a Go state quickstart, test it", or just "is this quickstart tested?" followed by "fix that". Handles both conventions in this repo: the canonical (api x language) quickstarts and the flat agent-family ones under agents/, dapr-agents/ and mcp-auth/.
---

# Add a quickstart end-to-end test

## What you are building

A suite that runs the commands a quickstart's README documents and asserts what
that README promises, so drift between the docs, the code and Catalyst is caught
automatically. The harness lives in `tools/qs-tester`; read its README first if
you have not.

## The rule that decides every judgement call

If a README documents a command, run that command verbatim, substituting only the
project name. Where a README documents nothing, the harness supplies its own
command and labels it infrastructure.

Two exceptions, both already implemented, neither to be re-litigated:

1. `diagrid login` becomes `diagrid login --api-key "$DIAGRID_API_KEY"` via
   `ci/login.sh`. The documented bare form blocks on a browser prompt.
2. The documented project name becomes `qs-ci-<leg>-<run-id>` via
   `ci/project-name.sh`. The `qs-ci-` prefix is what `ci/reap-orphans.sh`
   collects by; a name without it leaks forever.

Never invent an expected value. If the README does not document it and it cannot
be read out of the repo, assert only what is documented and leave a comment
naming the gap. An assertion nobody can trace to a source is worse than no
assertion, because it reads as coverage.

## Phase 0: preflight, before writing anything

Run `scripts/preflight.sh <family>`. It checks the credentials, CLI version and
harness sync you need to finish. A missing key found now costs seconds; found
after you have written four files, it costs the whole run.

If something is missing, say so immediately and ask whether to continue writing
without being able to verify. Do not quietly proceed to a state you cannot prove.

## Phase 1: classify

Which convention is this quickstart?

- Path is `workflow/`, `state/`, `pubsub/` or `invocation/`, README has numbered
  sections (`## 4. Install`, `## 5. Run`, `## 6.`): **canonical**. Read
  `references/canonical-api.md`.
- Path is `agents/`, `dapr-agents/`, `mcp-auth/` or similar, README has named
  sections: **agent-family**. Read `references/agent-quickstart.md`.

Read one reference, not both. They share little and the differences are what
matter.

## Phase 2: extract the facts

From the README first, in this order: install, provisioning, run, readiness
marker, trigger request, expected response, log markers, cleanup, required
secrets.

Where the README is silent about something the test needs, read the dev config
YAML (`appPort`, `appID`) or the app source, and record in a comment where the
value came from. Where the README is silent about something the test would only
guess at, such as a response body shape, leave it unasserted and say why in a
comment.

List every documented command you are NOT going to run, with its reason. That
list becomes `UNCOVERED`, and doc-sync fails if a documented command is in
neither `UNCOVERED` nor the suite. Crash-recovery flows that need source edits,
and endpoints no README documents, belong in `UNCOVERED`.

### When the README documents no project creation

Some quickstarts need a project but never say how to make one.
`dapr-agents/durable-agent` is the clearest case: its prerequisites list only the
CLI, Python and an OpenAI key, yet its `dev run` passes
`--project durable-agent-quickstart`. Under the guiding principle, provisioning is
then infrastructure, and `ci/setup-project.sh` owns it, exactly as for the
canonical APIs.

That script's flags were chosen for the canonical APIs, though
(`--deploy-managed-kv --deploy-managed-pubsub --enable-managed-workflow`), and an
agent quickstart may also need `--enable-agent-infrastructure`. Deciding that from
nothing is guessing, which is the one thing this skill must not do.

So: leave `SETUP` empty, note in the data module that provisioning is
undocumented, and **ask** which flags the project needs before running anything.
Say what you know (the quickstart passes `--project X`, nothing documents creating
X, the canonical flags are these) and what you need decided. A wrong flag here
either fails the whole leg or, worse, provisions something that works by accident
and hides a documentation gap readers will hit.

## Phase 3: write

Follow the files that already exist rather than inventing a layout:
`tools/qs-tester/variables/agents_langgraph.py` and
`agents/langgraph/tests/quickstart.robot` are the agent-family template;
`variables/quickstarts.py` and `state/tests/quickstart.robot` are the canonical
one. `references/harness-keywords.md` lists the keywords available with their
signatures, so you do not write a keyword that already exists.

Conventions that matter here: a `*** Comments ***` header naming which README
sections the suite mirrors, and a comment on every truncation, divergence or
value that came from somewhere other than the README. The next person to read
this file will be debugging a nightly failure at speed.

Register the suite in `tools/qs-tester/variables/suites.py`. For a genuinely new
runtime, also add the setup step to the `e2e-agents` job; otherwise touch no YAML.

## Phase 4: static verification

Run `scripts/verify-static.sh`. It runs the manifest validation, the dryrun,
doc-sync and the unit tests, which is exactly what CI's lint job runs. Loop until
green.

When doc-sync disagrees with you, the README is right and your data module is
wrong, unless you have positive evidence the README itself drifted. Say so
explicitly if you conclude that.

## Phase 5: live verification

Run `scripts/verify-live.sh <suite-path> <leg-id>`. It computes the name, logs
in, runs the suite, runs the mutation check, and tears down on every exit path.

A green run alone is not enough. The mutation check re-runs the suite with one
assertion deliberately broken and requires a failure. If the mutated run passes,
that assertion is vacuous, and a vacuous assertion is worse than none: it makes a
broken quickstart ship green. Investigate rather than reporting success.

## Phase 6: report

Exactly two shapes. There is no "probably fine".

**VERIFIED.** The live run passed and the mutation check failed as expected.
State which suite, which assertions it makes, which variable you mutated, and
what remains unproven (undocumented response shapes, other assertions no
mutation check covered).

**BLOCKED.** You could not complete the live run. State what is missing, what
you wrote anyway, what static checks passed, and the exact commands that finish
the job.

Reporting BLOCKED honestly is a success. Reporting VERIFIED without a green live
run and a failed mutation run is the one outcome that damages the harness,
because everything downstream trusts that claim.
```

- [ ] **Step 2: Write `references/agent-quickstart.md`**

Transcribe, from the spec's "Per-quickstart data module", "Project lifecycle for agent-family suites" and "doc-sync" sections plus the real `agents_langgraph.py`:

- The full data module contract, copied from Task 4's table: `DOCUMENTED_PROJECT`, `SETUP`, `INSTALL`, `RUN`, `TEARDOWN`, `READY_MARKERS`, `HEALTH_PORTS`, `SECRETS`, `REQUESTS` (with its optional `field`, `commands` and `log_marker` keys), `UNCOVERED`, and `get_quickstart()`. State plainly that `READY_MARKERS` and `REQUESTS` are read from the `Variables` import and not from `get_quickstart()`, and why: a value a Python keyword returned cannot be overridden, so a mutation check against it proves nothing.
- Worked examples of the three shapes `REQUESTS` has to cover: one request (langgraph), several requests against several apps (`dapr-agents/multi-agent-workflow`, three apps on 8001-8003 and therefore three readiness markers), and a flow interleaving CLI and HTTP where the second request carries `commands` and expects a different status (`mcp-auth/python`: fail closed, grant, succeed).
- The undocumented-provisioning decision path from SKILL.md phase 2, with `dapr-agents/durable-agent` as the example.
- That the three families differ in their documented provisioning, with the three real examples: `agents/*` (`--enable-agent-infrastructure` plus `agent create`, bare `dev run`), `dapr-agents/durable-agent` (no project create, explicit `--project`), `mcp-auth/python` (`project create --use`, `app create`, `apply -f`, then a `dev run` with both `--project` and three `--skip-*` flags: `--skip-managed-kv --skip-managed-pubsub --skip-default-resiliency`).
- That readiness markers are framework properties, not language properties, and where to find them in a README ("Wait until the output shows ...").
- That assertions are structural, with the reasoning about model output, and that an undocumented response shape means asserting the status code only.
- The mcp-auth warning from the spec's Limitations: if the grant/revoke phases exceed the generic keywords, produce a partial suite plus an explicit gap note in `tools/qs-tester/README.md` rather than assertions implying coverage that does not exist.

- [ ] **Step 3: Write `references/canonical-api.md`**

Transcribe from the existing harness README's "Adding a language or API" plus `variables/quickstarts.py`:

- README sections 4, 5 and 6 map to `INSTALL`, `RUN` and the request assertions.
- Every dict in `quickstarts.py` needs the new key, and `CONNECTED_APPS` is keyed by `(api, language)` because the divergence is real: pubsub's publisher has an `appPort` in csharp and python but not java or javascript.
- A new language means a tagged test case in the existing suite plus a CI matrix entry plus a runtime setup step.
- The existing per-language body divergences as worked examples of transcription, not guessing: java's `orderId` field, python's `"orderId=1"` string form, javascript's `instance_id`.

- [ ] **Step 4: Write `references/harness-keywords.md`**

A table of every keyword available with its signature and one line on when to use it, drawn from `process.resource`, `catalyst.resource` and `quickstart.resource` as they stand after Task 3. Include `${MARKER_TIMEOUT}` and `${READINESS_TIMEOUT}` with their defaults and the note that command-line variables override them, which is what the mutation check uses.

- [ ] **Step 5: Verify the skill loads and reads correctly**

```bash
ls .claude/skills/add-quickstart-e2e-test/
python3 -c "
import re,sys
text=open('.claude/skills/add-quickstart-e2e-test/SKILL.md').read()
assert text.startswith('---'), 'no frontmatter'
front=text.split('---')[1]
assert 'name: add-quickstart-e2e-test' in front
assert 'description:' in front
body=text.split('---',2)[2]
print('body lines:', len(body.splitlines()))
for ref in ('canonical-api.md','agent-quickstart.md','harness-keywords.md'):
    assert ref in body, f'{ref} is never referenced from SKILL.md'
print('ok')
"
```

Expected: `ok`, and a body under 500 lines. Every reference file must be pointed at from SKILL.md, or it will never be read.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/add-quickstart-e2e-test/
git commit -m "Add the add-quickstart-e2e-test skill instructions"
```

---

## Task 9: The skill's scripts

**Files:**
- Create: `.claude/skills/add-quickstart-e2e-test/scripts/preflight.sh`
- Create: `.claude/skills/add-quickstart-e2e-test/scripts/verify-static.sh`
- Create: `.claude/skills/add-quickstart-e2e-test/scripts/verify-live.sh`

**Interfaces:**
- Consumes: `ci/list-suites.py`, `ci/project-name.sh`, `ci/login.sh`, `ci/teardown-project.sh`, `docsync/check_readme_sync.py`.
- Produces: three executables SKILL.md's phases 0, 4 and 5 call.

- [ ] **Step 1: Write preflight.sh**

```bash
#!/usr/bin/env bash
# Check everything needed to finish a run, before any files are written.
#
# Usage: preflight.sh [family]     family: canonical | agent
#
# Exits non-zero listing what is missing. Finding a missing key now costs
# seconds; finding it after four files are written costs the whole run.
set -uo pipefail

FAMILY="${1:-agent}"
HARNESS="$(git rev-parse --show-toplevel)/tools/qs-tester"
problems=()

[ -d "$HARNESS" ] || problems+=("tools/qs-tester not found; run from inside the repository")

if ! command -v uv >/dev/null 2>&1; then
  problems+=("uv is not installed: https://docs.astral.sh/uv/")
fi

if ! command -v diagrid >/dev/null 2>&1; then
  problems+=("diagrid CLI is not on PATH; install the pinned version (see below)")
else
  pinned="$(grep -o "DIAGRID_CLI_VERSION: 'v[0-9.]*'" \
    "$(git rev-parse --show-toplevel)/.github/workflows/e2e-quickstarts.yml" \
    | grep -o 'v[0-9.]*')"
  actual="v$(diagrid version 2>/dev/null | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+' | head -1)"
  if [ -n "$pinned" ] && [ "$pinned" != "$actual" ]; then
    echo "note: local diagrid $actual, CI pins $pinned. Usually fine; if the CLI"
    echo "      surface changed, reproduce CI with:"
    echo "      curl -sL https://downloads.diagrid.io/cli/install.sh | RELEASE_VERSION=\"$pinned\" bash"
  fi
fi

[ -n "${DIAGRID_API_KEY:-}" ] || problems+=("DIAGRID_API_KEY is not set; the live run cannot happen without it")

if [ "$FAMILY" = "agent" ]; then
  # Any one provider key is enough to start; the suite's own Require Env Var
  # names the specific one it needs.
  if [ -z "${OPENAI_API_KEY:-}" ] && [ -z "${GEMINI_API_KEY:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    problems+=("no model provider key set (OPENAI_API_KEY, GEMINI_API_KEY or ANTHROPIC_API_KEY); agent quickstarts call a real model")
  fi
fi

(cd "$HARNESS" && uv sync -q) || problems+=("uv sync failed in tools/qs-tester")

if [ ${#problems[@]} -gt 0 ]; then
  echo "preflight failed:"
  for p in "${problems[@]}"; do echo "  - $p"; done
  exit 1
fi

echo "preflight ok (family: $FAMILY)"
```

- [ ] **Step 2: Write verify-static.sh**

```bash
#!/usr/bin/env bash
# Every check CI's lint job runs, in the same order, with no credentials.
# Run this until it is green before attempting a live run.
set -uo pipefail

cd "$(git rev-parse --show-toplevel)/tools/qs-tester" || exit 1
failed=()

run() {
  # Capture the label BEFORE the shift. Reading $1 after shifting yields the
  # command's first word instead, so every check invoked as `uv run ...` would
  # report the failure as "uv" and the summary line would be useless for triage.
  label="$1"
  shift
  if ! "$@"; then failed+=("$label"); fi
}

run "manifest"  uv run python ci/list-suites.py --validate
run "unit tests" uv run pytest -q
run "doc-sync"  uv run python docsync/check_readme_sync.py --all
echo "== dryrun"
# shellcheck disable=SC2046  # word splitting is the point: one path per suite
uv run robot --dryrun --variable PROJECT:dryrun --outputdir results/dryrun \
  $(uv run python ci/list-suites.py --paths) || failed+=("dryrun")
echo "== keyword smoke tests"
uv run robot --outputdir results/smoke \
  resources/tests/smoke.robot resources/tests/keywords.robot || failed+=("smoke")

if [ ${#failed[@]} -gt 0 ]; then
  echo
  echo "static verification FAILED: ${failed[*]}"
  exit 1
fi
echo
echo "static verification passed"
```

- [ ] **Step 3: Write verify-live.sh**

```bash
#!/usr/bin/env bash
# Run one suite against a real Catalyst project, then prove one of its
# assertions is not vacuous, then tear down whatever happened.
#
# Usage: verify-live.sh <suite-path> <leg-id> [mutation-assignment]
#   suite-path          repo-relative, e.g. agents/langgraph/tests/quickstart.robot
#   leg-id              name fragment, e.g. agents-langgraph
#   mutation-assignment a Python assignment to override, as NAME=<literal>.
#                       Default: READY_MARKERS=("__mutation_check__",)
#
# The override is written to a generated variable file rather than passed with
# --variable, because --variable can only set scalars and the assertions worth
# breaking (READY_MARKERS, REQUESTS) are tuples. A CLI --variablefile outranks the
# suite's own `Variables` import, so this reaches any module-level name and needs
# no type guessing here.
set -uo pipefail

SUITE="${1:?usage: verify-live.sh <suite-path> <leg-id> [NAME=<python-literal>]}"
LEG="${2:?usage: verify-live.sh <suite-path> <leg-id> [NAME=<python-literal>]}"
MUTATION="${3:-READY_MARKERS=(\"__mutation_check__\",)}"

ROOT="$(git rev-parse --show-toplevel)"
eval "$(bash "$ROOT/tools/qs-tester/ci/project-name.sh" "$LEG" | grep '^PROJECT=')"
export PROJECT

# Tear down on every exit path, including a mid-run interrupt. A leaked project
# with agent infrastructure costs money until reap-orphans.sh collects it.
cleanup() { bash "$ROOT/tools/qs-tester/ci/teardown-project.sh" "$PROJECT"; }
trap cleanup EXIT INT TERM

bash "$ROOT/tools/qs-tester/ci/login.sh" || exit 1
cd "$ROOT/tools/qs-tester" || exit 1

echo "== live run: $SUITE (project $PROJECT)"
if ! uv run robot --variable "PROJECT:$PROJECT" --outputdir "results/$LEG" "../../$SUITE"; then
  echo "::error::live run FAILED. Read results/$LEG/log.html and the captured dev-run log."
  exit 1
fi

echo "== mutation check: overriding $MUTATION, expecting a FAILURE"
# Reuses the same project, so the marginal cost is one app restart rather than a
# second provisioning. The short timeouts keep a run we expect to fail from
# waiting out the full readiness window.
mkdir -p "results/$LEG-mutated"
printf '%s\n' "$MUTATION" > "results/$LEG-mutated/mutate.py"
if uv run robot --variable "PROJECT:$PROJECT" \
     --variablefile "results/$LEG-mutated/mutate.py" \
     --variable READINESS_TIMEOUT:20s --variable MARKER_TIMEOUT:20s \
     --outputdir "results/$LEG-mutated" "../../$SUITE"; then
  echo "::error::The suite PASSED with $MUTATION applied, so that assertion is vacuous:"
  echo "  it cannot fail, which means a broken quickstart would ship green."
  echo "  Check first that Robot actually loaded the variable file (it errors loudly"
  echo "  if the path is wrong), then that the suite reads the name from its"
  echo "  Variables import rather than from get_quickstart()."
  echo "  Fix the assertion; do not report this suite as verified."
  exit 1
fi

echo
echo "VERIFIED: $SUITE passed, and failed as expected with $MUTATION applied."
```

- [ ] **Step 4: Make them executable and check them**

```bash
chmod +x .claude/skills/add-quickstart-e2e-test/scripts/*.sh
for s in .claude/skills/add-quickstart-e2e-test/scripts/*.sh; do bash -n "$s" && echo "syntax ok: $s"; done
command -v shellcheck >/dev/null && shellcheck .claude/skills/add-quickstart-e2e-test/scripts/*.sh
bash .claude/skills/add-quickstart-e2e-test/scripts/verify-static.sh
```

Expected: syntax ok for all three; `static verification passed`.

- [ ] **Step 5: Test preflight's failure path**

```bash
env -u DIAGRID_API_KEY -u OPENAI_API_KEY -u GEMINI_API_KEY -u ANTHROPIC_API_KEY \
  bash .claude/skills/add-quickstart-e2e-test/scripts/preflight.sh agent; echo "exit=$?"
```

Expected: `exit=1`, listing the missing `DIAGRID_API_KEY` and the missing provider key. A preflight that cannot fail is as useless as a vacuous assertion.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/add-quickstart-e2e-test/scripts/
git commit -m "Add preflight, static and live verification scripts to the skill"
```

---

## Task 10: The skill's evals

**Files:**
- Create: `.claude/skills/add-quickstart-e2e-test/evals/evals.json`

**Interfaces:**
- Consumes: the finished skill from Tasks 8-9.
- Produces: the eval set, and a workspace of results the user reviews.

- [ ] **Step 1: Write the eval set**

```json
{
  "skill_name": "add-quickstart-e2e-test",
  "evals": [
    {
      "id": 1,
      "name": "agent-python-common-case",
      "prompt": "The agents/pydantic-ai quickstart has no end-to-end test. Add one and wire it into the nightly workflow like the langgraph one.",
      "expected_output": "A data module at tools/qs-tester/variables/agents_pydantic_ai.py transcribed from agents/pydantic-ai/README.md, a suite at agents/pydantic-ai/tests/quickstart.robot, a row in variables/suites.py, static checks green, and a BLOCKED report naming the missing credentials.",
      "files": [],
      "expectations": [
        "A data module exists at tools/qs-tester/variables/agents_pydantic_ai.py",
        "A suite exists at agents/pydantic-ai/tests/quickstart.robot",
        "variables/suites.py has a row whose suite path matches that suite",
        "ci/list-suites.py --validate exits 0",
        "check_readme_sync.py --all exits 0",
        "The dryrun resolves the new suite without errors",
        "Every command in SETUP, INSTALL, RUN and TEARDOWN appears in the README modulo the project name",
        "Documented commands the suite does not run are listed in UNCOVERED with a reason",
        "No expected response body was invented: any asserted field is traceable to the README or to an observed response, or the assertion is the status code only",
        "The final report says BLOCKED and names the missing credentials rather than claiming success",
        "No workflow YAML was edited, because python needs no new runtime setup step"
      ]
    },
    {
      "id": 2,
      "name": "agent-dotnet-new-runtime",
      "prompt": "We need CI coverage for the Microsoft Agent Framework .NET quickstart under agents/microsoft-dotnet. Can you set that up?",
      "expected_output": "Same artifacts as eval 1, plus runtime: dotnet in the manifest row, and confirmation that the e2e-agents job's existing .NET setup step covers it.",
      "files": [],
      "expectations": [
        "The manifest row sets runtime to dotnet and language to csharp or dotnet consistently with suites.RUNTIMES",
        "The data module's SETUP includes the documented project create with --enable-agent-infrastructure and the documented agent create",
        "The data module's RUN matches the README's documented dev run command verbatim modulo the project name",
        "The suite reads its model provider secret through Require Env Var before provisioning anything",
        "ci/list-suites.py --matrix agent includes the new row with runtime dotnet",
        "The report distinguishes what static checks proved from what only a live run could prove"
      ]
    },
    {
      "id": 3,
      "name": "mcp-auth-multi-phase",
      "prompt": "Write a Robot end-to-end test for the mcp-auth/python quickstart.",
      "expected_output": "A suite covering the documented happy path (project create --use, app create, apply -f, the dev run with its three --skip-* flags), with the grant/revoke phases either covered or explicitly listed as gaps rather than faked.",
      "files": [],
      "expectations": [
        "SETUP contains the documented project create --use, app create and apply -f commands in the documented order",
        "RUN keeps all three --skip-* flags exactly as documented: --skip-managed-kv, --skip-managed-pubsub, --skip-default-resiliency",
        "The documented fail-closed call and the allowed call after the grant are both in REQUESTS, in order. Note both return HTTP 200 from the local client: the upstream 404 (caller matches no rule) or 403 (ACCESS_DENIED) is surfaced inside the response body, so what distinguishes them is the asserted field, not the status code",
        "The grant command rides on the second request's commands key rather than being dropped or hoisted into SETUP",
        "Any phase left uncovered is recorded in UNCOVERED with a reason and noted in tools/qs-tester/README.md",
        "No assertion claims coverage of an authorization outcome the suite does not actually check",
        "check_readme_sync.py --all exits 0",
        "The report is BLOCKED or VERIFIED, never an unqualified success claim"
      ]
    },
    {
      "id": 4,
      "name": "canonical-undocumented-endpoint",
      "prompt": "The state quickstart has a DELETE /order/{id} endpoint in all four languages but I don't think it's tested. Add e2e coverage for it.",
      "expected_output": "A refusal to invent coverage: no README documents that endpoint, so the skill should say so, offer to document it first (which brings it under test) or to record it as a known gap, and not fabricate a request or expected body.",
      "files": [],
      "expectations": [
        "The skill states that no README documents DELETE /order/{id} and that this is why it is untested",
        "No request or expected response body was invented for the endpoint",
        "The skill offers documenting the endpoint first as the path to coverage, rather than testing it undocumented",
        "variables/quickstarts.py was not edited to add an undocumented request",
        "If anything was written, it is a gap note rather than an assertion",
        "The skill correctly identifies this as the canonical convention, not agent-family"
      ]
    }
  ]
}
```

**Field name:** the per-eval list is `expectations`, not `assertions`. skill-creator's
prose says "assertions", but its `references/schemas.md` defines `evals[].expectations`
and its scripts only ever read `expectations` — an evals.json using `assertions` parses
and presents zero checks to the grader. `grading.json` also uses `expectations`, with
per-item `text`/`passed`/`evidence`.

Eval 4 looks like a trick question and is the most valuable of the four. The skill's
whole value rests on assertions being traceable to a documented promise, and its most
likely failure is being helpful: fabricating a plausible `DELETE` request and an
expected body, producing something that passes, and quietly asserting behaviour
nobody promised. The harness README already records this endpoint as untested for
exactly this reason, so the correct answer is on record.

**What these evals do not cover:** adding a new *language* to a canonical API. All
sixteen (api, language) pairs already exist, so there is no real gap to exercise
without inventing a fixture quickstart. When a fifth language does land, add a fifth
eval from the real directory and assert the language-shaped work: a row in every dict
in `quickstarts.py`, a tagged test case in the existing suite, a CI matrix entry, and
a runtime setup step. Until then, `references/canonical-api.md` documents that path
but nothing verifies the skill follows it.

- [ ] **Step 2: Run the evals**

Follow skill-creator's eval flow: for each of the three prompts, spawn one subagent with the skill and one baseline subagent without it, in the same turn, saving outputs under
`.claude/skills/add-quickstart-e2e-test-workspace/iteration-1/<eval-name>/{with_skill,without_skill}/outputs/`.

The subagents will have no Catalyst credentials, so every run should end BLOCKED. That is the intended outcome and eval 1's most important assertion: a skill that reports success without a live run is the failure mode that matters, because the whole harness downstream trusts that claim.

- [ ] **Step 3: Grade, aggregate and review**

Grade each run against its assertions into `grading.json`, aggregate with skill-creator's
`python -m scripts.aggregate_benchmark <workspace>/iteration-1 --skill-name add-quickstart-e2e-test`,
then launch the review viewer and hand it to the user. Where an assertion is mechanically checkable (a file exists, a script exits 0, a command string appears in a README), write a script rather than eyeballing it, and reuse it next iteration.

- [ ] **Step 4: Improve the skill from the feedback, then commit**

Apply what the results show. Watch specifically for the two failure modes this skill is most likely to have: inventing an expected value the README does not document, and reporting success without a live run.

```bash
git add .claude/skills/add-quickstart-e2e-test/
git commit -m "Add evals for the add-quickstart-e2e-test skill"
```

---

## Verification summary

| Check | Command | Credentials |
|---|---|---|
| Manifest | `uv run python ci/list-suites.py --validate` | none |
| Unit tests | `uv run pytest -q` | none |
| doc-sync | `uv run python docsync/check_readme_sync.py --all` | none |
| Dryrun | `uv run robot --dryrun --variable PROJECT:dryrun $(uv run python ci/list-suites.py --paths)` | none |
| Keyword tests | `uv run robot resources/tests/smoke.robot resources/tests/keywords.robot` | none |
| All of the above | `scripts/verify-static.sh` | none |
| Live plus mutation | `scripts/verify-live.sh agents/langgraph/tests/quickstart.robot agents-langgraph` | `DIAGRID_API_KEY`, `OPENAI_API_KEY` |

---

## Outstanding: prove the langgraph suite, then enable it nightly

Task 5's Steps 8-11 were not run: no model provider key was available, and
`agents/langgraph` calls OpenAI. So `agents/langgraph` is registered with
`nightly: False`, and three things remain undone. Nothing else in this plan depends
on them, which is why the remaining tasks proceeded, but the suite is unproven until
they are done:

1. The live run (Step 8). One ephemeral Catalyst project with agent infrastructure,
   plus one model call.
2. Recording the observed response field (Step 9), which is why `REQUESTS[0]["field"]`
   is still `None`.
3. The mutation check (Step 10), which is the only evidence that the suite's
   assertions can fail at all.

To finish: export `DIAGRID_API_KEY` and `OPENAI_API_KEY`, then

```bash
bash .claude/skills/add-quickstart-e2e-test/scripts/verify-live.sh \
  agents/langgraph/tests/quickstart.robot agents-langgraph
```

which does the live run, the mutation check, and teardown on every exit path. Then set
that manifest row to `nightly: True` in the same commit as the evidence.

Until then the suite still earns its keep: the lint job dryruns it on every PR, the
doc-sync checker holds it to `agents/langgraph/README.md` in both directions, and a
`workflow_dispatch` run executes it, because dispatch ignores the `nightly` filter.

---

## Before merging: remove this plan and the spec

This repository does not keep superpowers specs and plans in git. Commit `622e732`
("docs: remove the design and plan documents") deleted the equivalent pair for the
python uv-workspace work once that work was done, and the only reason this pair is
committed now is to have something reviewable while the work is in progress.

So the last change on this branch, after every task above is done and green, is:

```bash
git rm docs/superpowers/plans/2026-07-31-quickstart-e2e-test-skill.md \
       docs/superpowers/specs/2026-07-31-quickstart-e2e-test-skill-design.md
git commit -m "Remove the design and plan documents"
```

Two things to check in the same commit, because removing these files is what makes
them dangle:

1. Nothing references either path. `grep -rn "2026-07-31-quickstart-e2e-test-skill"`
   must come back empty, including `tools/qs-tester/README.md` and any docstring in
   `variables/suites.py` or `variables/agents_langgraph.py`. Task 7 already fixes the
   pre-existing dangling pointer on line 9 of the harness README; do not add a new one.
2. Keep a copy outside the repository if the reasoning is still useful. The comments
   that matter are already in the code they explain, which is the point of writing
   them there.

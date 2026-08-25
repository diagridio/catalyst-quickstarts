# Agent Quickstart Realignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge `origin/main`, realign the harness and the `add-quickstart-e2e-test` skill with the agent quickstarts as they now exist, add two suites chosen for shape coverage, and make the skill's own examples machine-checked so this drift cannot recur silently.

**Architecture:** The merge comes first, because main changed the two resource files this work extends and added a data-contract key (`connected_apps`) that agent data modules do not yet provide. Then the langgraph module is corrected against the current README, a length rule and a new skill-docs checker are added, the skill's documents are updated under that checker's protection, and finally two new suites exercise the `dotnet` and `java` runtimes and the first three-level suite path.

**Tech Stack:** Robot Framework 7, Python 3.12+, `uv`, pytest, GitHub Actions, `diagrid` CLI (pinned `v1.67.0` on main).

Design spec: `docs/superpowers/specs/2026-08-25-agent-quickstart-drift-design.md`. Read it before Task 1.

## Global Constraints

- Documented commands run verbatim; only the project name is substituted. The two sanctioned exceptions stay: `diagrid login` becomes `diagrid login --api-key "$DIAGRID_API_KEY"`, and the documented project name becomes `qs-ci-…`.
- **The full ephemeral project name must be at most 55 characters.** Format is `qs-ci-agents-<name>-<run-id>`; the binding run-id is the local fallback (`local` + 10-digit epoch = 15 chars), so `name` gets 26 characters.
- Every ephemeral project name starts with `qs-ci-`, because `ci/reap-orphans.sh` collects by that prefix.
- Never invent an expected value. If a README does not document it and it cannot be read out of the repo, assert only what is documented and leave a comment naming the gap.
- Probe only a path the app actually serves. `Wait Until Apps Healthy` iterates `health_probes`, so an empty tuple is a legitimate no-op for an app with no GET route.
- `agents/dapr-agents/` is canonical. The top-level `dapr-agents/` tree is retained for Dapr University only; nothing in the skill may point at it.
- No new third-party dependencies. Python 3.12+.
- All three new/updated suites land `nightly: False`. None can be proven without a model provider key.
- Commit messages are plain imperative, no `feat:`/`fix:` prefix.

## Facts established by review, so nobody re-derives them

| Fact | Value |
|---|---|
| Provisioning flags (most agents) | `--enable-managed-workflow --deploy-managed-kv --deploy-managed-pubsub --wait --use` |
| Provisioning flags (spring-ai) | `--enable-managed-workflow --deploy-managed-kv --wait --use` |
| langgraph agent name / appID / port | `schedule-planner` / `schedule-planner` / 8005 |
| microsoft-dotnet agent / appID / port | `event-planner` / `event-planner` / 5050 |
| spring-ai/event-planner agent / appID / port | `spring-ai-event-planner` / same / 8080 |
| Routes on both new apps | `POST /run` only. No GET route, no Spring actuator. |
| microsoft-dotnet readiness marker | `Established gRPC bidirectional stream with Dapr sidecar` |
| spring-ai readiness marker | None documented |
| `--enable-agent-infrastructure` | Gone from the entire repository |

---

## Task 1: Merge origin/main and resolve the three conflicts

**Files:**
- Modify: `.github/workflows/e2e-quickstarts.yml`
- Modify: `tools/qs-tester/README.md`
- Modify: `tools/qs-tester/resources/catalyst.resource`

**Interfaces:**
- Consumes: nothing.
- Produces: a merged branch on which `resources/tests` (whole directory) is CI's harness-test step, `DIAGRID_CLI_VERSION` is `v1.67.0`, and `catalyst.resource` carries both main's `@{CONNECTED_APP_IDS}` / `Release App Connection` and this branch's `Run Documented Commands` / `Wait Until Ready Marker`.

- [ ] **Step 1: Merge and see the three conflicts**

```bash
git fetch origin
git merge origin/main
git status --short | grep '^UU'
```

Expected: exactly three `UU` entries, in `.github/workflows/e2e-quickstarts.yml`, `tools/qs-tester/README.md`, and `tools/qs-tester/resources/catalyst.resource`. If a fourth appears, stop and report it rather than resolving something this plan has not analysed.

- [ ] **Step 2: Resolve the workflow**

Take **main's** side for two things and keep this branch's side for the rest:

- `DIAGRID_CLI_VERSION: 'v1.67.0'` (main's bump wins).
- The harness-test step becomes main's whole-directory form, which also picks up this branch's `keywords.robot` with no further edit:

```yaml
      # The whole directory, not smoke.robot alone: these are the harness's own
      # credential-free tests (process teardown, the readiness gate) and a new
      # file here must not need a workflow edit to start running.
      - name: Test the harness keywords
        run: (cd tools/qs-tester && uv run robot --outputdir results/harness resources/tests)
```

Keep this branch's `discover` job, `e2e-agents` job, manifest-driven dryrun, manifest-validation step, and `report`'s `needs`. Then add the three-level glob to `pull_request.paths`, which the spring-ai suite in Task 8 will be the first to need:

```yaml
      - 'tools/qs-tester/**'
      - '*/tests/quickstart.robot'
      - '*/*/tests/quickstart.robot'
      - '*/*/*/tests/quickstart.robot'
      - '*/*/README.md'
      - '.github/workflows/e2e-quickstarts.yml'
```

- [ ] **Step 3: Resolve the harness README**

Take main's `resources/tests/` layout description and its `uv run robot resources/tests` recipe, and main's new "500 on the invocation request" failure-shape entry. Keep this branch's agent-family sections, runbook, and Limitations. Then fix the stale pin in the install line:

```bash
curl -sL https://downloads.diagrid.io/cli/install.sh | RELEASE_VERSION="v1.67.0" bash
```

- [ ] **Step 4: Resolve catalyst.resource by keeping both sides**

Both changes are additive and both are needed. Keep main's `*** Variables ***` block with `@{CONNECTED_APP_IDS}`, main's `Start Quickstart` body including the `Set Test Variable` line, main's `Stop Quickstart` loop and its `Release App Connection` keyword; and keep this branch's `Run Documented Commands` and `Wait Until Ready Marker` keywords appended after them.

Do not drop main's `Set Test Variable    @{CONNECTED_APP_IDS}    @{app_ids}` line. `Stop Quickstart` runs as a test teardown, where a local variable from `Start Quickstart` no longer exists, and without it every run leaves a `trust.diagrid.io` endpoint pointing at a dead tunnel.

- [ ] **Step 5: Verify the merge leaves the existing checks green**

```bash
cd tools/qs-tester
uv run python ci/list-suites.py --validate
uv run pytest -q
uv run python docsync/check_readme_sync.py --all
uv run robot --dryrun --variable PROJECT:dryrun --outputdir results/dryrun \
  $(uv run python ci/list-suites.py --paths)
uv run robot --outputdir results/harness resources/tests
```

Expected: manifest valid; pytest passes; the dryrun resolves every suite. **doc-sync will report four problems for langgraph**: two commands the harness runs that the README no longer documents, and two the README documents that nothing accounts for. That is the drift Task 3 fixes; record the four lines in your report and do not fix them here.

`resources/tests` now runs main's `smoke.robot`, `readiness.robot`, `teardown.robot` and this branch's `keywords.robot` together. Report the total count.

- [ ] **Step 6: Commit the merge**

```bash
git add -A
git commit -m "Merge origin/main into the agent-family harness work"
```

---

## Task 2: Give agent data modules the `connected_apps` key main now requires

**Files:**
- Modify: `tools/qs-tester/variables/agents_langgraph.py`
- Modify: `agents/langgraph/tests/quickstart.robot`
- Test: `tools/qs-tester/resources/tests/keywords.robot`

**Interfaces:**
- Consumes: `Start Quickstart`, `Stop Quickstart`, `Wait Until Apps Connected` from the merged `catalyst.resource`.
- Produces: `get_quickstart()` returning a `connected_apps` key, shape `[[app_id, port], …]`, matching what `quickstarts.get_quickstart` returns for canonical suites.

This is a merge consequence, not a cosmetic one. Main's `Start Quickstart` evaluates
`[app[0] for app in $qs["connected_apps"]]`, and the agent module has no such key, so **every
agent suite now dies at launch with a dictionary error**. The dryrun cannot catch it: `Evaluate`
and dict access are runtime behaviour.

- [ ] **Step 1: Write the failing test**

Add to `tools/qs-tester/resources/tests/keywords.robot`, in `*** Test Cases ***`:

```robot
Start Quickstart Records The Connected App IDs For Teardown
    # Regression test for a merge hazard: Start Quickstart reads
    # ${qs}[connected_apps] to remember which app connections Stop Quickstart must
    # release. An agent data module that omits the key fails here at launch, and a
    # --dryrun cannot catch it because the failure is a runtime dict access.
    ${qs}=    Create Dictionary
    ...    run=bash -c 'echo started; sleep 5'
    ...    dir=${TEMPDIR}
    ...    connected_apps=${{ [['probe-app', 8099]] }}
    Start Quickstart    ${qs}    qs-ci-demo-1    ${TEMPDIR}/connected.log
    Should Be Equal    ${CONNECTED_APP_IDS}[0]    probe-app
    [Teardown]    Run Keyword And Ignore Error    Stop Process Tree    apps
```

- [ ] **Step 2: Run it to see it pass, then prove it guards something**

Run: `cd tools/qs-tester && uv run robot --outputdir results/harness --test "Start Quickstart Records The Connected App IDs For Teardown" resources/tests/keywords.robot`

Expected: PASS. Then delete `connected_apps` from the `Create Dictionary` call, re-run, and confirm it FAILS with a dictionary/key error. Restore the key. Quote both outputs in your report: the test only earns its place if the missing key is what makes it fail.

- [ ] **Step 3: Add the key to the langgraph module**

In `tools/qs-tester/variables/agents_langgraph.py`, add beside `HEALTH_PROBES`:

```python
# (appID, port) pairs that `diagrid dev run` reports as
# `Connected App ID "<id>" to http://localhost:<port>`. Read from
# dev-python-langgraph.yaml, whose single app has appID schedule-planner on
# appPort 8005.
#
# Required, not optional: `Start Quickstart` records these so `Stop Quickstart`
# can release each local app connection, and a run that skips that leaves a
# trust.diagrid.io endpoint pointing at a dead tunnel, which makes the next run's
# 500s ambiguous.
#
# INFERRED, NOT OBSERVED: the harness README's rule is that the CLI prints the
# connection line for an app with a non-zero appPort, and this app's is 8005. No
# live run has confirmed the line appears for an agent app. If it does not,
# `Wait Until Apps Connected` waits out READINESS_TIMEOUT and the fix is to drop
# the gate rather than to widen the timeout.
CONNECTED_APPS = ((("schedule-planner", 8005),))
```

Careful with the parentheses: a one-element tuple of pairs is `(("schedule-planner", 8005),)`. Write it that way, not as `((("schedule-planner", 8005)))`, which is a plain tuple of two items and will iterate as characters.

Then in `get_quickstart()`, add the key and delete the now-false comment claiming agent quickstarts emit no connection line:

```python
        "connected_apps": [list(pair) for pair in CONNECTED_APPS],
```

- [ ] **Step 4: Use the gate in the suite**

In `agents/langgraph/tests/quickstart.robot`, add the connection gate before the readiness marker, since it is the stronger signal and the one the canonical suites use:

```robot
    Wait Until Apps Connected   ${qs}    ${log}
    FOR    ${marker}    IN    @{READY_MARKERS}
        Wait Until Ready Marker    ${log}    ${marker}
    END
```

- [ ] **Step 5: Verify and commit**

```bash
cd tools/qs-tester
uv run robot --outputdir results/harness resources/tests
uv run robot --dryrun --variable PROJECT:dryrun --outputdir results/dryrun \
  $(uv run python ci/list-suites.py --paths)
uv run pytest -q
```

```bash
git add -A
git commit -m "Record the connected app IDs for agent suites too"
```

---

## Task 3: Realign the langgraph module with its current README

**Files:**
- Modify: `tools/qs-tester/variables/agents_langgraph.py`

**Interfaces:**
- Consumes: `check_agent` from `docsync/check_readme_sync.py`.
- Produces: a module for which `check_readme_sync.py --all` reports zero problems.

- [ ] **Step 1: Confirm the four problems are still reported**

Run: `cd tools/qs-tester && uv run python docsync/check_readme_sync.py --all`

Expected: four langgraph problems. This is your baseline; the task is done when they are gone and nothing else broke.

- [ ] **Step 2: Correct `SETUP`**

```python
# README "## Run with Catalyst", steps 2 and 3. `--enable-agent-infrastructure`
# was replaced by the three managed-service flags; the agent is now named for its
# role in the shared event-planning scenario rather than for its framework.
SETUP = (
    "diagrid project create {project} --enable-managed-workflow --deploy-managed-kv --deploy-managed-pubsub --wait --use",
    "diagrid agent create schedule-planner --wait",
)
```

- [ ] **Step 3: Re-check `UNCOVERED` against the current README**

The crash-recovery section still documents two `dev run` invocations against `dev-crash-test.yaml`. Verify their exact spelling with:

```bash
git show HEAD:agents/langgraph/README.md | grep -n 'dev-crash-test'
```

Update the `UNCOVERED` entries to match verbatim, keeping a reason on each. If the README now documents a command that is neither in `SETUP`/`INSTALL`/`RUN`/`TEARDOWN`/`REQUESTS` nor in `UNCOVERED`, doc-sync will tell you in Step 5; decide honestly whether the suite should run it or whether it is out of scope, and write the reason.

- [ ] **Step 4: Leave `TEARDOWN` empty, and say why in one line**

The README still has no cleanup section, so `TEARDOWN = ()` stays. Confirm rather than assume:

```bash
git show HEAD:agents/langgraph/README.md | grep -c 'project delete'
```

Expected: `0`. If it is not zero, the README grew a cleanup step and `TEARDOWN` must run it.

- [ ] **Step 5: Verify zero problems and commit**

```bash
cd tools/qs-tester
uv run python docsync/check_readme_sync.py --all
uv run pytest -q
uv run robot --dryrun --variable PROJECT:dryrun --outputdir results/dryrun \
  $(uv run python ci/list-suites.py --paths)
```

Expected: doc-sync reports every README in sync, with no langgraph problems.

```bash
git add -A
git commit -m "Realign the langgraph module with its current README"
```

---

## Task 4: Enforce the 55-character project-name ceiling

**Files:**
- Modify: `tools/qs-tester/variables/suites.py`
- Test: `tools/qs-tester/tests/test_suites.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `suites.MAX_PROJECT_NAME` (int, 55), `suites.leg_id(row) -> str`, `suites.project_name_budget() -> int`, and a `validate()` rule using them. Tasks 7 and 8 add rows that must satisfy it.

- [ ] **Step 1: Write the failing tests**

Add to `tools/qs-tester/tests/test_suites.py`:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd tools/qs-tester && uv run pytest tests/test_suites.py -q`
Expected: five failures, `AttributeError: module 'suites' has no attribute 'project_name_budget'`.

- [ ] **Step 3: Implement**

Add to `tools/qs-tester/variables/suites.py`:

```python
# The ephemeral project name must fit Catalyst's limit. `ci/project-name.sh`
# builds `qs-ci-<leg>-<run-id>`, and agent legs use `agents-<name>`.
MAX_PROJECT_NAME = 55

# The binding case is a LOCAL run, not CI: GITHUB_RUN_ID is about 11 digits, but
# the local fallback is `local` plus a 10-digit epoch, which is longer. Sizing to
# the shorter CI form would let a name pass validation and then fail when someone
# runs it on their laptop.
_LEG_PREFIX = "agents-"
_WORST_RUN_ID = len("local") + 10


def project_name_budget():
    """Characters available for an agent row's `name`.

    Derived from the format rather than hard-coded, so this stays correct if the
    prefix or the leg format changes.
    """
    fixed = len("qs-ci-") + len(_LEG_PREFIX) + len("-") + _WORST_RUN_ID
    return MAX_PROJECT_NAME - fixed


def leg_id(row):
    """The leg fragment CI passes to ci/project-name.sh.

    Defaults to the row's `name`, which is the quickstart's path below `agents/`
    with slashes replaced by dashes, and is therefore unique by construction. A
    row may carry an explicit shorter `leg` when a deep path would exceed the
    budget.
    """
    return row.get("leg") or row["name"]
```

Then, inside `validate()`'s `if family == "agent":` block:

```python
            leg = leg_id(row)
            if len(leg) > project_name_budget():
                problems.append(
                    f"{where}: leg {leg!r} is {len(leg)} characters, over the "
                    f"{project_name_budget()}-character budget that keeps the ephemeral "
                    f"project name within {MAX_PROJECT_NAME} characters. Shorten it with an "
                    f"explicit `leg` on this row. Catching it here costs seconds; catching it "
                    f"at `diagrid project create` costs a nightly leg and leaks a half-made project."
                )
```

- [ ] **Step 4: Run the tests and the real manifest**

```bash
cd tools/qs-tester
uv run pytest -q
uv run python ci/list-suites.py --validate
```

Expected: all tests pass; the real manifest still validates.

- [ ] **Step 5: Prove the rule can fail**

Temporarily add a row whose name is one character over the budget, run `--validate`, and confirm it exits non-zero naming the limit. Remove the row. Quote the output. A rule nobody has seen fail buys nothing.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "Reject an agent leg that would overflow the project name"
```

---

## Task 5: Machine-check the skill's own command examples

**Files:**
- Create: `tools/qs-tester/docsync/check_skill_docs.py`
- Create: `tools/qs-tester/docsync/tests/test_skill_docs.py`
- Modify: `.github/workflows/e2e-quickstarts.yml`
- Modify: `.claude/skills/add-quickstart-e2e-test/scripts/verify-static.sh`

**Interfaces:**
- Consumes: `all_bash_lines` and `_FENCE` from `docsync/check_readme_sync.py`.
- Produces: `check_skill_docs.check(skill_dir, repo_root) -> list[str]`, `mask_project_name(command) -> str`, and a CLI exiting 1 on problems. Task 6 edits the files this checks.

- [ ] **Step 1: Write the failing tests**

Create `tools/qs-tester/docsync/tests/test_skill_docs.py`:

```python
from pathlib import Path

from check_skill_docs import check, mask_project_name

READMES = {
    "agents/langgraph/README.md": """\
## Run with Catalyst

```bash
diagrid project create langgraph-quickstart --enable-managed-workflow --deploy-managed-kv --deploy-managed-pubsub --wait --use
```

```bash
diagrid agent create schedule-planner --wait
```
""",
}


def _tree(tmp_path, skill_md):
    for rel, text in READMES.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(skill_md)
    return skill, tmp_path


def test_a_documented_command_passes(tmp_path):
    skill, root = _tree(tmp_path, """\
Run it like this:

```bash
diagrid agent create schedule-planner --wait
```
""")
    assert check(skill, root) == []


def test_a_stale_flag_fails(tmp_path):
    # The exact drift this checker exists for.
    skill, root = _tree(tmp_path, """\
```bash
diagrid project create {project} --enable-agent-infrastructure --wait --use
```
""")
    problems = check(skill, root)
    assert any("enable-agent-infrastructure" in p for p in problems)


def test_a_stale_agent_name_fails(tmp_path):
    # Agent names are deliberately not masked: a renamed agent is drift.
    skill, root = _tree(tmp_path, """\
```bash
diagrid agent create langgraph-agent --wait
```
""")
    assert any("langgraph-agent" in p for p in check(skill, root))


def test_an_illustrative_block_with_a_reason_is_skipped(tmp_path):
    skill, root = _tree(tmp_path, """\
<!-- illustrative: constructed to show the commands key; no README documents this -->

```bash
diagrid mcp grant --caller x --tool add
```
""")
    assert check(skill, root) == []


def test_an_illustrative_tag_without_a_reason_fails(tmp_path):
    skill, root = _tree(tmp_path, """\
<!-- illustrative: -->

```bash
diagrid mcp grant --caller x --tool add
```
""")
    assert any("reason" in p for p in check(skill, root))


def test_all_three_project_name_spellings_mask_alike():
    documented = "diagrid project create langgraph-quickstart --wait --use"
    placeholder = "diagrid project create {project} --wait --use"
    ephemeral = "diagrid project create qs-ci-agents-langgraph-local1 --wait --use"
    assert mask_project_name(documented) == mask_project_name(placeholder)
    assert mask_project_name(ephemeral) == mask_project_name(placeholder)
    flagged = "diagrid dev run -f x.yaml --project langgraph-quickstart --approve"
    assert mask_project_name(flagged).endswith("--project PROJECT --approve")


def test_a_non_diagrid_command_is_ignored(tmp_path):
    # Only `diagrid` lines are in scope; robot and uv invocations in the skill are
    # harness usage that no README documents.
    skill, root = _tree(tmp_path, """\
```bash
uv run robot --dryrun ../../agents/langgraph/tests/quickstart.robot
```
""")
    assert check(skill, root) == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd tools/qs-tester && uv run pytest docsync/tests/test_skill_docs.py -q`
Expected: `ModuleNotFoundError: No module named 'check_skill_docs'`.

- [ ] **Step 3: Implement the checker**

Create `tools/qs-tester/docsync/check_skill_docs.py`:

```python
"""Assert every `diagrid` command the skill shows is one a README documents.

The harness was already immune to a flag change: a suite's SETUP is per-quickstart
data transcribed from a README, and check_readme_sync compares the two in both
directions. What was not immune was the skill's own teaching material. When
`--enable-agent-infrastructure` was replaced across the quickstarts, the examples
in SKILL.md and references/ silently became false, and an agent following them
would have written a suite that fails doc-sync for a reason it had just
introduced.

So the discipline the harness applies to suites applies here too: a command that
cannot be traced to a README does not survive CI.

Scope is deliberately narrow. Only lines beginning `diagrid` inside a fenced block
are checked, because that is the surface that drifts: flags, subcommands and agent
names. `uv`, `robot` and `curl` lines in the skill are harness usage that no
README documents, and checking them would mean tagging most of the file.

Usage:
    python docsync/check_skill_docs.py
    python docsync/check_skill_docs.py --skill-dir path --repo-root path
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_readme_sync import all_bash_lines  # noqa: E402

# `<!-- illustrative: reason -->` on the line(s) above a fence exempts that block.
# A missing reason is itself a failure: an exemption nobody had to justify is how
# an exemption list rots into a way of silencing real drift.
_ILLUSTRATIVE = re.compile(r"<!--\s*illustrative:(?P<reason>.*?)-->", re.IGNORECASE | re.DOTALL)
_FENCE_OPEN = re.compile(r"^```(\w*)\s*$")

# Directories whose READMEs are the source of truth. The legacy top-level
# `dapr-agents/` tree is excluded on purpose: it is retained for Dapr University
# and is not a place the skill should send anyone.
_CORPUS_GLOBS = (
    "agents/*/README.md",
    "agents/*/*/README.md",
    "mcp-auth/*/README.md",
    "workflow/*/README.md",
    "state/*/README.md",
    "pubsub/*/README.md",
    "invocation/*/README.md",
)


def mask_project_name(command):
    """Collapse the three spellings of a project name to one token.

    Positional (`project create <name>`), flagged (`--project <name>`), and the
    harness placeholder (`{project}`). Agent names are deliberately NOT masked:
    `diagrid agent create langgraph-agent` should fail once no README documents
    that name, because a renamed agent is exactly the drift this catches.
    """
    masked = re.sub(r"\{project\}", "PROJECT", command)
    masked = re.sub(r"--project\s+\S+", "--project PROJECT", masked)
    masked = re.sub(
        r"\b(project\s+(?:create|delete))\s+\S+", r"\1 PROJECT", masked
    )
    return " ".join(masked.split())


def documented_commands(repo_root):
    """Every `diagrid` line in every README in the corpus, masked."""
    commands = set()
    for glob in _CORPUS_GLOBS:
        for readme in sorted(repo_root.glob(glob)):
            for line in all_bash_lines(readme.read_text()):
                if line.startswith("diagrid"):
                    commands.add(mask_project_name(line))
    return commands


def _blocks_with_context(markdown):
    """Yield (line_number, body, preceding_text) for each fenced block."""
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        opener = _FENCE_OPEN.match(lines[index])
        if not opener:
            index += 1
            continue
        start = index + 1
        end = start
        while end < len(lines) and not lines[end].startswith("```"):
            end += 1
        preceding = "\n".join(lines[max(0, index - 3):index])
        yield index + 1, "\n".join(lines[start:end]), preceding
        index = end + 1


def check(skill_dir, repo_root):
    """Return a list of problem descriptions. Empty means the skill is in sync."""
    skill_dir, repo_root = Path(skill_dir), Path(repo_root)
    documented = documented_commands(repo_root)
    problems = []

    files = [skill_dir / "SKILL.md", *sorted(skill_dir.glob("references/*.md"))]
    for path in files:
        if not path.is_file():
            continue
        markdown = path.read_text()
        for line_no, body, preceding in _blocks_with_context(markdown):
            tag = _ILLUSTRATIVE.search(preceding)
            if tag:
                if not tag.group("reason").strip():
                    problems.append(
                        f"{path.name}:{line_no}: an `illustrative` tag with no reason. "
                        "State why no README documents this command, so the exemption is a "
                        "decision rather than a way to silence the check."
                    )
                continue
            for line in all_bash_lines(f"```bash\n{body}\n```"):
                if not line.startswith("diagrid"):
                    continue
                masked = mask_project_name(line)
                if masked in documented:
                    continue
                close = difflib.get_close_matches(masked, sorted(documented), n=1)
                hint = f"\n  closest documented: {close[0]}" if close else ""
                problems.append(
                    f"{path.name}:{line_no}: shows a command no README documents:\n"
                    f"  {line}{hint}\n"
                    "  Either correct it against the README it describes, or tag the block "
                    "`<!-- illustrative: <reason> -->` if it is deliberately constructed."
                )
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(__file__).resolve().parents[3]
    parser.add_argument("--repo-root", type=Path, default=default_root)
    parser.add_argument(
        "--skill-dir",
        type=Path,
        default=default_root / ".claude" / "skills" / "add-quickstart-e2e-test",
    )
    args = parser.parse_args()

    problems = check(args.skill_dir, args.repo_root)
    for problem in problems:
        print(f"::error::{problem}")
    if problems:
        print(f"\n{len(problems)} stale command(s) in the skill's documentation")
        return 1
    print("Skill documentation is in sync with the quickstart READMEs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests**

Run: `cd tools/qs-tester && uv run pytest -q`
Expected: all pass, including the seven new ones.

- [ ] **Step 5: Run it against the real skill, and expect failures**

Run: `cd tools/qs-tester && uv run python docsync/check_skill_docs.py`

Expected: **non-zero**, reporting the stale `--enable-agent-infrastructure` and `langgraph-agent` commands in `SKILL.md` and `references/agent-quickstart.md`. That is Task 6's work. Record the exact list in your report; it is Task 6's checklist.

- [ ] **Step 6: Do NOT wire it into CI yet**

Task 6 wires the checker into the `lint` job and `verify-static.sh`, in the same commit that
makes it pass. Wiring it here would land a commit whose own gate is knowingly red, which teaches
the next person that a red check is something you scroll past.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "Check the skill's diagrid examples against the quickstart READMEs"
```

---

## Task 6: Update the skill's documents

**Files:**
- Modify: `.claude/skills/add-quickstart-e2e-test/SKILL.md`
- Modify: `.claude/skills/add-quickstart-e2e-test/references/agent-quickstart.md`
- Modify: `.claude/skills/add-quickstart-e2e-test/references/canonical-api.md`
- Modify: `.claude/skills/add-quickstart-e2e-test/references/harness-keywords.md`

**Interfaces:**
- Consumes: `check_skill_docs.py` from Task 5, which must exit 0 when this task is done.
- Produces: skill documentation describing the harness as it is after Tasks 1 through 4.

- [ ] **Step 1: Fix every command the checker flagged**

Work from Task 5 Step 5's list. The substitutions:

- `--enable-agent-infrastructure` becomes `--enable-managed-workflow --deploy-managed-kv --deploy-managed-pubsub`, and the spring-ai variant `--enable-managed-workflow --deploy-managed-kv` is worth showing beside it, because a reader needs to know the flags are per-quickstart data rather than a constant.
- `diagrid agent create langgraph-agent` becomes `diagrid agent create schedule-planner`.

- [ ] **Step 2: Move the worked examples off the legacy tree**

Two examples point at code readers should not follow:

- The "documents no project create" example is `dapr-agents/durable-agent`, which now lives at `agents/dapr-agents/durable-agent` **and now documents a `project create`**. The current no-provisioning example is `agents/dapr-agents/orchestrator`, which documents only a `dev run`.
- The multi-app example is `dapr-agents/multi-agent-workflow`, which exists only in the legacy tree. Replace it with `agents/dapr-agents/orchestrator`: nine apps on ports 8001 through 8009.

- [ ] **Step 3: Add what Tasks 2 and 4 changed in the contract**

- `connected_apps` is now a required key, with the reason: `Start Quickstart` records the IDs so `Stop Quickstart` can release each connection, and a run that skips it leaves a dead tunnel behind that makes the next run's 500s ambiguous.
- The manifest name is the path below `agents/` with slashes replaced by dashes, it must fit the 26-character budget, and `validate()` enforces that. Show `spring-ai-event-planner` as the three-level example.
- Quickstarts can be three levels deep, and the suite lives at `<family>/<group>/<name>/tests/quickstart.robot`.

- [ ] **Step 4: Add the phase-2 sentence about flags**

In `SKILL.md`'s phase 2, one sentence, because the checker cannot stop an agent copying a verified example into a new suite:

> Read the provisioning flags out of the README you are testing. The examples here are checked against real READMEs, but they are still examples: `spring-ai` omits `--deploy-managed-pubsub`, and the flags changed once already.

- [ ] **Step 5: Correct the readiness-marker guidance with the new evidence**

`agents/microsoft-dotnet` documents `Established gRPC bidirectional stream with Dapr sidecar`, and `agents/spring-ai/event-planner` documents no marker at all. Both are worth naming, because they show the marker is a property of the framework and that a quickstart may not give you one, in which case the connection gate is the readiness signal.

Also record the harder-won fact from Task 7 and 8's targets: neither new app serves any GET route, so `HEALTH_PROBES` is empty for both. The instruction to probe only a path the app really serves already exists; these are the examples that show it is not hypothetical.

- [ ] **Step 6: Wire the checker into CI and verify-static, now that it passes**

In the `lint` job, after the doc-sync step:

```yaml
      - name: Check the skill's examples against the READMEs
        run: (cd tools/qs-tester && uv run python docsync/check_skill_docs.py)
```

In `scripts/verify-static.sh`, add it in the same position relative to the other checks, so the
local order keeps matching CI's.

This lands here rather than in Task 5 so that no commit ever introduces a gate that is red at
the moment it is introduced.

- [ ] **Step 7: Verify the checker passes and the wiring holds**

```bash
cd tools/qs-tester
uv run python docsync/check_skill_docs.py
uv run pytest -q
bash ../../.claude/skills/add-quickstart-e2e-test/scripts/verify-static.sh
```

Expected: the checker exits 0, and `verify-static.sh` passes with the new check listed among the
others.

- [ ] **Step 8: Confirm the checker still catches drift**

Reintroduce `--enable-agent-infrastructure` into one reference file, run the checker, confirm non-zero, and revert. Quote the output.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "Update the skill's documents for the current agent quickstarts"
```

---

## Task 7: Add the microsoft-dotnet suite

**Files:**
- Create: `tools/qs-tester/variables/agents_microsoft_dotnet.py`
- Create: `agents/microsoft-dotnet/tests/quickstart.robot`
- Modify: `tools/qs-tester/variables/suites.py`

**Interfaces:**
- Consumes: everything from Tasks 1 through 4.
- Produces: a `runtime: dotnet` manifest row named `microsoft-dotnet`, and the first suite with a non-empty `TEARDOWN`.

Why this one: it is the only suite that exercises the `dotnet` CI setup step, a documented `project delete`, and a non-Uvicorn readiness marker.

- [ ] **Step 1: Write the data module**

Create `tools/qs-tester/variables/agents_microsoft_dotnet.py`:

```python
"""Data for the agents/microsoft-dotnet end-to-end suite.

Every command is transcribed verbatim from agents/microsoft-dotnet/README.md, with
the documented project name replaced by `{project}`. Change the README, change
this file, and `docsync/check_readme_sync.py --all` will say so if you change only
one.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

FAMILY = "agents"
NAME = "microsoft-dotnet"
LANGUAGE = "csharp"

DOCUMENTED_PROJECT = "dotnet-quickstart"
QUICKSTART_DIR = str(REPO_ROOT / "agents" / "microsoft-dotnet")

# README "## Run with Catalyst", steps 2 and 3.
SETUP = (
    "diagrid project create {project} --enable-managed-workflow --deploy-managed-kv --deploy-managed-pubsub --wait --use",
    "diagrid agent create event-planner --wait",
)

# README "## Setup". The documented `cd agents/microsoft-dotnet` is expressed as
# the working directory instead of a command.
INSTALL = "dotnet build"

RUN = "diagrid dev run -f dev-dotnet-agent.yaml --approve"

# README "## Clean Up". Unlike langgraph, this quickstart documents its cleanup,
# so the suite runs it.
TEARDOWN = ("diagrid project delete {project}",)

# README: "Wait until the output shows `Established gRPC bidirectional stream with
# Dapr sidecar`." Not a Uvicorn line: the marker is a property of the framework,
# and this is a .NET app.
READY_MARKERS = ("Established gRPC bidirectional stream with Dapr sidecar",)

# EMPTY ON PURPOSE. Program.cs registers exactly one route, `app.MapPost("/run")`,
# so there is no GET path to probe and `GET /` would 404 for the whole readiness
# timeout on a perfectly healthy app. Readiness rests on the connection gate below
# plus the documented marker above. If a health endpoint is ever added, probe it.
HEALTH_PROBES = ()

# appID and appPort from dev-dotnet-agent.yaml.
CONNECTED_APPS = (("event-planner", 5050),)

SECRETS = ("OPENAI_API_KEY",)

# README "### 2. Trigger the Agent".
#
# `field` is None because the README documents no response body. Fill it in from
# an observed live response with a comment naming that response as the source.
REQUESTS = (
    {
        "method": "POST",
        "port": 5050,
        "path": "/run",
        "payload": {"prompt": "Find a venue in Austin for a company gala"},
        "status": 200,
        "field": None,
    },
)

# Documented commands this suite deliberately does not run, each with its reason.
UNCOVERED = (
    (
        "diagrid dev run -f dev-dotnet-agent.yaml",
        "the crash-recovery flow's resume step; the crash itself needs a source "
        "edit, so the whole flow is out of scope",
    ),
)


def get_quickstart():
    """Everything the suite needs, in one flat dict."""
    return {
        "family": FAMILY,
        "name": NAME,
        "language": LANGUAGE,
        "dir": QUICKSTART_DIR,
        "setup": list(SETUP),
        "install": INSTALL,
        "run": RUN,
        "teardown": list(TEARDOWN),
        "health_probes": [list(probe) for probe in HEALTH_PROBES],
        "connected_apps": [list(pair) for pair in CONNECTED_APPS],
        "secrets": list(SECRETS),
    }
```

- [ ] **Step 2: Write the suite**

Create `agents/microsoft-dotnet/tests/quickstart.robot`, following `agents/langgraph/tests/quickstart.robot` as the template. Two differences to get right, both already in the data module:

- `TEARDOWN` is non-empty here, so `Clean Up Quickstart` actually runs a documented `diagrid project delete`. Keep the `Run Keyword And Ignore Error` guards: `Stop Process Tree` is not idempotent against an already-exited process.
- `HEALTH_PROBES` is empty, so `Wait Until Apps Healthy` is a no-op and the connection gate plus the marker are the readiness signals. Say so in a comment, or the next reader will "fix" the missing probe.

Tag it `[Tags]    csharp    microsoft-dotnet    agents`.

- [ ] **Step 3: Register it**

Add to `SUITES`:

```python
    {
        "suite": "agents/microsoft-dotnet/tests/quickstart.robot",
        "family": "agent",
        "name": "microsoft-dotnet",
        "data": "agents_microsoft_dotnet",
        "language": "csharp",
        "runtime": "dotnet",
        # False until a live run and a mutation check prove it. See the harness
        # README's Limitations.
        "nightly": False,
        "secrets": ("OPENAI_API_KEY",),
    },
```

- [ ] **Step 4: Verify**

```bash
cd tools/qs-tester
uv run python ci/list-suites.py --validate
uv run python docsync/check_readme_sync.py --all
uv run pytest -q
uv run robot --dryrun --variable PROJECT:dryrun --outputdir results/dryrun \
  $(uv run python ci/list-suites.py --paths)
uv run python ci/list-suites.py --matrix agent
```

Expected: manifest valid with the new row; doc-sync reports zero problems for it; the dryrun resolves one more test than before; the matrix includes a `runtime: dotnet` entry.

If doc-sync objects, the README is right and the module is wrong unless you have positive evidence otherwise. Say so explicitly if you conclude the README drifted.

- [ ] **Step 5: Run the suite without a model key**

```bash
uv run robot --variable PROJECT:qs-ci-agents-microsoft-dotnet-notreal \
  --outputdir results/dotnet-nokey ../../agents/microsoft-dotnet/tests/quickstart.robot
```

Expected: FAIL at `Require Env Var` naming `OPENAI_API_KEY`, with `Build Quickstart`, `Run Documented Commands` and `Start Quickstart` all `NOT RUN`. Confirm from `output.xml` that no `diagrid project create` was attempted, and quote the statuses. That ordering is what stops a missing secret from leaking a project in CI.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "Add the agents/microsoft-dotnet end-to-end suite"
```

---

## Task 8: Add the spring-ai/event-planner suite

**Files:**
- Create: `tools/qs-tester/variables/agents_spring_ai_event_planner.py`
- Create: `agents/spring-ai/event-planner/tests/quickstart.robot`
- Modify: `tools/qs-tester/variables/suites.py`

**Interfaces:**
- Consumes: everything from Tasks 1 through 4, and the three-level `paths` glob from Task 1.
- Produces: a `runtime: java` row named `spring-ai-event-planner`, and the first suite three directory levels deep.

Why this one: it is the only suite that exercises the `java` CI setup step, the reduced flag set, and a three-level suite path.

- [ ] **Step 1: Write the data module**

Create `tools/qs-tester/variables/agents_spring_ai_event_planner.py` on the same pattern as Task 7's, with these values, all transcribed from `agents/spring-ai/event-planner/README.md`:

```python
FAMILY = "agents"
NAME = "spring-ai-event-planner"
LANGUAGE = "java"

DOCUMENTED_PROJECT = "spring-ai-quickstart"
QUICKSTART_DIR = str(REPO_ROOT / "agents" / "spring-ai" / "event-planner")

# README "### 1. Deploy and Run" documents login, create, agent create and dev run
# in ONE fenced block. Note the reduced flag set: no --deploy-managed-pubsub,
# unlike every other agent quickstart. The flags are per-quickstart data, not a
# constant.
SETUP = (
    "diagrid project create {project} --enable-managed-workflow --deploy-managed-kv --wait --use",
    "diagrid agent create spring-ai-event-planner --wait",
)

# README "## Setup". The documented `cd event-planner` is expressed as the working
# directory; the `#` comment line above it is not a command.
INSTALL = "mvn package -DskipTests"

RUN = "diagrid dev run -f dev-spring-ai-event-planner.yaml --approve"

TEARDOWN = ("diagrid project delete {project}",)

# EMPTY ON PURPOSE, and this is the interesting one: this README documents no
# readiness wording at all. There is no "wait until" line to transcribe, so
# inventing one would be inventing an assertion. Readiness rests entirely on the
# connection gate below.
READY_MARKERS = ()

# EMPTY ON PURPOSE. EventPlannerController exposes only @PostMapping("/run"), and
# spring-boot-starter-actuator is not on the classpath, so there is no GET path to
# probe.
HEALTH_PROBES = ()

# appID and appPort from dev-spring-ai-event-planner.yaml.
CONNECTED_APPS = (("spring-ai-event-planner", 8080),)

SECRETS = ("OPENAI_API_KEY",)

REQUESTS = (
    {
        "method": "POST",
        "port": 8080,
        "path": "/run",
        "payload": {"prompt": "Find a venue in Austin for a company gala"},
        "status": 200,
        "field": None,
    },
)
```

Derive `UNCOVERED` from what the README documents but the suite does not run. Check with:

```bash
git show HEAD:agents/spring-ai/event-planner/README.md | grep -nE '^diagrid|dev run|project delete'
```

Every documented `diagrid` line must be in `SETUP`, `RUN`, `TEARDOWN` or `UNCOVERED` with a reason, or doc-sync fails in Step 4. `diagrid login` is exempt.

Then write `get_quickstart()` returning the same keys as Task 7's.

- [ ] **Step 2: Write the suite**

Create `agents/spring-ai/event-planner/tests/quickstart.robot`. The resource paths are one level deeper than the other agent suites:

```robot
Resource        ../../../../tools/qs-tester/resources/catalyst.resource
Resource        ../../../../tools/qs-tester/resources/quickstart.resource
Variables       ../../../../tools/qs-tester/variables/agents_spring_ai_event_planner.py
Library         ../../../../tools/qs-tester/variables/agents_spring_ai_event_planner.py
```

Count the `../` segments against the file's own depth rather than copying from langgraph. Both `READY_MARKERS` and `HEALTH_PROBES` are empty here, so the `FOR` loops over them are no-ops and `Wait Until Apps Connected` is the only readiness gate. Comment that, because a reader who sees two empty loops will otherwise assume something is missing.

Tag it `[Tags]    java    spring-ai-event-planner    agents`.

- [ ] **Step 3: Register it**

```python
    {
        "suite": "agents/spring-ai/event-planner/tests/quickstart.robot",
        "family": "agent",
        "name": "spring-ai-event-planner",
        "data": "agents_spring_ai_event_planner",
        "language": "java",
        "runtime": "java",
        "nightly": False,
        "secrets": ("OPENAI_API_KEY",),
    },
```

The name is 23 characters, inside the 26-character budget from Task 4. `--validate` will say so if that ever stops being true.

- [ ] **Step 4: Verify, including the glob that had nothing behind it**

```bash
cd tools/qs-tester
uv run python ci/list-suites.py --validate
uv run python docsync/check_readme_sync.py --all
uv run pytest -q
uv run robot --dryrun --variable PROJECT:dryrun --outputdir results/dryrun \
  $(uv run python ci/list-suites.py --paths)
```

Then confirm Task 1's three-level glob actually matches this suite, because until now nothing did.

**Use this matcher, not `fnmatch` and not `PurePath.match`.** Both of those report every glob as
matching, because their `*` crosses `/` and `PurePath.match` anchors at the tail. GitHub Actions
path filters do neither: `*` matches any character except `/`, and the pattern must match the
whole path. A check built on the wrong matcher prints all-True and teaches the opposite of the
truth.

```bash
cd "$(git rev-parse --show-toplevel)"
python3 -c "
import re
def gh_match(pattern, path):
    rx = '^' + ''.join('[^/]*' if c == '*' else re.escape(c) for c in pattern) + '\$'
    return re.match(rx, path) is not None

globs = ('*/tests/quickstart.robot', '*/*/tests/quickstart.robot', '*/*/*/tests/quickstart.robot')
for path in ('agents/langgraph/tests/quickstart.robot',
             'agents/spring-ai/event-planner/tests/quickstart.robot',
             'state/tests/quickstart.robot'):
    print(path)
    for g in globs:
        print('   ', g, '->', gh_match(g, path))
"
```

Expected, and each line matters:

- `state/tests/quickstart.robot` matches only `*/tests/quickstart.robot`, the canonical entry.
- `agents/langgraph/...` matches only `*/*/tests/quickstart.robot`, so that entry is load-bearing too and must not be dropped as redundant.
- `agents/spring-ai/event-planner/...` matches only `*/*/*/tests/quickstart.robot`, the entry Task 1 added.

If the spring-ai path matches nothing, the `paths` filter would run no checks at all on a PR
touching only this suite, which is the silent failure Task 1's edit exists to prevent.

- [ ] **Step 5: Run without a model key**

As in Task 7 Step 5, with this suite's path. Same expectation: FAIL at `Require Env Var`, provisioning `NOT RUN`, quoted from `output.xml`.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "Add the agents/spring-ai/event-planner end-to-end suite"
```

---

## Task 9: Documentation

**Files:**
- Modify: `tools/qs-tester/README.md`

**Interfaces:**
- Consumes: Tasks 1 through 8.
- Produces: the runbook and the honest limitations for three agent suites instead of one.

- [ ] **Step 1: Document the naming convention and the budget**

In the agent-family section, record that an agent row's `name` is the quickstart's path below `agents/` with slashes replaced by dashes, that it must fit 26 characters so the ephemeral project name stays within 55, that `validate()` enforces it, and that an explicit `leg` is the escape hatch for a deep path.

- [ ] **Step 2: Document the new checker**

Add `docsync/check_skill_docs.py` to the Layout list and to the credential-free checks, with one line on why it exists: the skill's examples went stale when the provisioning flags changed, and prose that nobody checks is prose that drifts.

- [ ] **Step 3: Document `connected_apps` for agent suites**

One entry explaining that agent data modules provide it, that `Start Quickstart` records the IDs for `Stop Quickstart` to release, and that the connection line's emission for an agent app is inferred from the appPort rule and not yet observed.

- [ ] **Step 4: Update Limitations honestly**

Three suites now, all `nightly: False`, none ever run against real Catalyst. Add:

- `microsoft-dotnet` and `spring-ai/event-planner` have empty `HEALTH_PROBES` because neither app serves a GET route, so their readiness rests on the connection gate; and for spring-ai there is no documented marker either.
- The connection line for an agent app is inferred, not observed.
- Eleven agent quickstarts still have no suite and therefore no drift detection beyond the skill-docs checker.

Do not upgrade the canonical suites' status, and do not imply any of the three agent suites has been proven.

- [ ] **Step 5: Verify every documented command runs**

Run each command the README now documents that needs no credentials, and confirm the output matches what the README claims. Then:

```bash
cd tools/qs-tester
uv run python ci/list-suites.py --validate
uv run pytest -q
uv run python docsync/check_readme_sync.py --all
uv run python docsync/check_skill_docs.py
bash ../../.claude/skills/add-quickstart-e2e-test/scripts/verify-static.sh
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "Document the three agent suites and the skill-docs checker"
```

---

## Verification summary

| Check | Command | Credentials |
|---|---|---|
| Manifest, including the length rule | `uv run python ci/list-suites.py --validate` | none |
| Unit tests | `uv run pytest -q` | none |
| README/harness sync | `uv run python docsync/check_readme_sync.py --all` | none |
| Skill examples | `uv run python docsync/check_skill_docs.py` | none |
| Dryrun, all suites | `uv run robot --dryrun --variable PROJECT:dryrun $(uv run python ci/list-suites.py --paths)` | none |
| Harness keyword tests | `uv run robot resources/tests` | none |
| All of the above | `scripts/verify-static.sh` | none |
| Live plus mutation, per suite | `scripts/verify-live.sh <suite> <leg>` | `DIAGRID_API_KEY`, `OPENAI_API_KEY` |

Three guards must each be seen failing, not just passing: the length rule (add a row one character over budget), the skill-docs checker (reintroduce `--enable-agent-infrastructure`), and the `connected_apps` test (delete the key). A guard nobody has seen fail is worth as little as an assertion nobody has seen fail.

## Still outstanding after this plan

- Live runs and mutation checks for all three suites. Blocked on a model provider key.
- One `workflow_dispatch` before the nightly can be trusted; CI has never executed this workflow.
- Why PR #293 triggered no CI run at all.
- The eval set has never been run.
- Eleven agent quickstarts have no suite. Adding one is what the skill is for.

## Before merging: remove this plan and the spec

Same as the previous cycle. This repository does not keep superpowers specs and plans in git; the reasoning that matters lives in comments beside the code it explains.

```bash
git rm docs/superpowers/plans/2026-08-25-agent-quickstart-drift.md \
       docs/superpowers/specs/2026-08-25-agent-quickstart-drift-design.md
git commit -m "Remove the design and plan documents"
```

Check first that nothing references either path: `grep -rn "2026-08-25-agent-quickstart-drift"` must come back empty.

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

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


# --- Widened surface: untagged fences and inline code spans -------------------
#
# The skill's own SKILL.md and references/*.md turned out to hold every stale
# `--enable-agent-infrastructure` example as prose with a single-backtick code
# span, never inside a ```bash fence — so the fence-only checker above passed
# with zero findings against the real skill, which is not the same thing as
# the skill being right. These tests hold the widened extraction (any fenced
# language, plus inline spans) to the same two rules: a placeholder-free,
# flagged `diagrid ...` command must match a README line verbatim, and any
# `--flag` a candidate names — fenced or inline, placeholder or not — must be
# documented for the same CLI object somewhere in the corpus.


def test_a_stale_flag_inside_an_untagged_fence_fails(tmp_path):
    skill, root = _tree(tmp_path, """\
```
diagrid project create {project} --enable-agent-infrastructure --wait --use
```
""")
    assert any("enable-agent-infrastructure" in p for p in check(skill, root))


def test_a_stale_flag_in_an_inline_code_span_fails(tmp_path):
    skill, root = _tree(tmp_path, """\
Provision it with `diagrid project create {project} --enable-agent-infrastructure --wait --use` first.
""")
    assert any("enable-agent-infrastructure" in p for p in check(skill, root))


def test_a_bare_partial_reference_does_not_fail(tmp_path):
    # `diagrid dev run` names no flags, so there is nothing about it that
    # could be stale. Demanding it match a README verbatim would fail on a
    # true statement no README happens to phrase identically (every
    # documented `dev run` carries at least `-f <file>`).
    skill, root = _tree(tmp_path, """\
Watch the terminal running `diagrid dev run` for the readiness marker.
""")
    assert check(skill, root) == []


def test_a_placeholder_command_with_all_flags_documented_does_not_fail(tmp_path):
    skill, root = _tree(tmp_path, """\
Run `diagrid project create {project} --wait --use` to provision.
""")
    assert check(skill, root) == []


def test_a_placeholder_command_with_an_undocumented_flag_fails(tmp_path):
    skill, root = _tree(tmp_path, """\
- **`agents/*`**: `diagrid project create <name> --enable-agent-infrastructure --wait --use`, then `diagrid agent create <agent-name> --wait`.
""")
    assert any("enable-agent-infrastructure" in p for p in check(skill, root))


def test_an_illustrative_tag_exempts_an_inline_candidate_in_the_same_paragraph(tmp_path):
    skill, root = _tree(tmp_path, """\
<!-- illustrative: constructed to show the commands key; no README documents this -->
See `diagrid mcp grant --caller x --tool add` as an example.
""")
    assert check(skill, root) == []


def test_an_illustrative_tag_without_a_reason_fails_for_an_inline_candidate(tmp_path):
    skill, root = _tree(tmp_path, """\
<!-- illustrative: -->
See `diagrid mcp grant --caller x --tool add` as an example.
""")
    assert any("reason" in p for p in check(skill, root))

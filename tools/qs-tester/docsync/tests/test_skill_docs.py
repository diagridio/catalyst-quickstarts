from pathlib import Path

from check_skill_docs import _SANCTIONED_EXCEPTIONS, check, mask_project_name

READMES = {
    "agents/langgraph/README.md": """\
## Run with Catalyst

```bash
diagrid project create langgraph-quickstart --enable-managed-workflow --deploy-managed-kv --deploy-managed-pubsub --wait --use
```

```bash
diagrid agent create schedule-planner --wait
```

```bash
diagrid dev run --project langgraph-quickstart --approve -- mvn spring-boot:run
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


# --- The sanctioned `diagrid login --api-key` exception ------------------------
#
# `diagrid login --api-key "$DIAGRID_API_KEY"` is one of exactly two sanctioned
# deviations from doc-sync (the other is the project-name substitution, already
# handled by `mask_project_name`): CI runs it in place of the documented bare
# `diagrid login`, which blocks on an interactive browser prompt, and no README
# will ever document it. It is a real command CI actually runs, not a
# constructed example, so it does not get an `illustrative` tag — that would
# misdescribe it, and the tag's block/paragraph-wide exemption would silently
# cover any other command that later sits next to it. It is encoded as an exact
# allowlist entry instead.


def test_the_sanctioned_login_api_key_exception_passes(tmp_path):
    skill, root = _tree(tmp_path, """\
```bash
diagrid login --api-key "$DIAGRID_API_KEY"
```
""")
    assert check(skill, root) == []


def test_a_different_api_key_value_still_fails(tmp_path):
    # The allowlist entry is matched exactly, not as a prefix, so a nearby
    # variation is still held to the same two rules as everything else.
    skill, root = _tree(tmp_path, """\
```bash
diagrid login --api-key "$SOME_OTHER_VAR"
```
""")
    assert check(skill, root) != []


def test_a_different_login_flag_still_fails(tmp_path):
    skill, root = _tree(tmp_path, """\
```bash
diagrid login --debug
```
""")
    assert check(skill, root) != []


def test_the_sanctioned_exceptions_list_is_exactly_one_entry():
    # Growing this list should require editing this test and stating why —
    # it is closed by the design, not a place to park a documentation gap.
    assert _SANCTIONED_EXCEPTIONS == (
        'diagrid login --api-key "$DIAGRID_API_KEY"',
    )


# --- Fence robustness: unterminated fences, info strings, indentation ---------
#
# `_fence_spans` used to treat an unterminated fence as running to end of
# file, and its opener regex didn't accept an info string beyond a single
# word or any leading indentation — so a fence like ` ```bash title=x` was
# never recognised as an opener, its own closing ``` was misread as the
# opener of a NEW block, and that swallowed everything after it as "fenced"
# content, silently dropping it from every check. For a checker whose only
# value is failing on drift, quietly checking nothing is worse than a false
# positive.


def test_a_truly_unterminated_fence_is_reported_as_a_problem(tmp_path):
    skill, root = _tree(tmp_path, """\
```bash
diagrid agent create schedule-planner --wait
""")
    problems = check(skill, root)
    assert any("closing" in p.lower() for p in problems)


def test_an_unrecognised_info_string_does_not_swallow_the_rest_of_the_file(tmp_path):
    skill, root = _tree(tmp_path, """\
```bash title=x
diagrid agent create schedule-planner --wait
```

Also see `diagrid project create {project} --enable-agent-infrastructure --wait --use` here.
""")
    problems = check(skill, root)
    assert any("enable-agent-infrastructure" in p for p in problems)


def test_an_indented_fence_inside_a_list_item_is_recognised(tmp_path):
    skill, root = _tree(tmp_path, """\
- Example:
  ```bash
  diagrid project create {project} --enable-agent-infrastructure --wait --use
  ```
""")
    problems = check(skill, root)
    assert any("enable-agent-infrastructure" in p for p in problems)


# --- Embedded string-literal commands (python/robotframework fences) ---------
#
# The docstring claimed this coverage before the extraction actually had it:
# `all_bash_lines` keeps only lines starting with `diagrid`, and an embedded
# Python string literal starts with a quote character instead. This is
# exactly the shape of `references/agent-quickstart.md`'s
# `REQUESTS[...]["commands"]` example, and the most natural place a future
# author pastes a command when writing a new agent-family suite.


def test_a_stale_flag_in_a_python_embedded_string_literal_fails(tmp_path):
    skill, root = _tree(tmp_path, """\
```python
COMMANDS = (
    "diagrid project create {project} --enable-agent-infrastructure --wait --use",
)
```
""")
    assert any("enable-agent-infrastructure" in p for p in check(skill, root))


def test_a_command_split_across_two_adjacent_string_literals_is_joined(tmp_path):
    # Python concatenates adjacent literals implicitly; a naive per-line quote
    # strip would see two truncated, unmatchable fragments and misreport a
    # command that is, joined, exactly what a README documents.
    skill, root = _tree(tmp_path, """\
```python
COMMANDS = (
    "diagrid agent create schedule-planner "
    "--wait",
)
```
""")
    assert check(skill, root) == []


def test_a_stale_flag_split_across_two_adjacent_string_literals_fails(tmp_path):
    skill, root = _tree(tmp_path, """\
```python
COMMANDS = (
    "diagrid project create {project} --enable-agent-infrastructure "
    "--wait --use",
)
```
""")
    assert any("enable-agent-infrastructure" in p for p in check(skill, root))


# --- Minor: a bare `--` stops flag collection ---------------------------------


def test_flags_after_a_bare_double_dash_are_not_checked_as_diagrid_flags(tmp_path):
    # Everything after a bare `--` belongs to the wrapped command, not to
    # diagrid, and must not be checked as though it were a diagrid flag.
    skill, root = _tree(tmp_path, """\
```bash
diagrid dev run --project {project} --approve -- uvicorn --port 8000
```
""")
    problems = check(skill, root)
    assert not any("--port" in p for p in problems)


# --- Minor: a malformed illustrative tag must not fail silently --------------


def test_a_malformed_illustrative_tag_without_a_colon_is_reported(tmp_path):
    skill, root = _tree(tmp_path, """\
<!-- illustrative no colon here -->

```bash
diagrid mcp grant --caller x --tool add
```
""")
    problems = check(skill, root)
    assert any("colon" in p for p in problems)


# --- I1: no fence shape may leave a `diagrid` line checked by nobody ---------
#
# `_fence_spans` treats a wrapping fence (```` , ~~~, or a marker carrying an
# info string) as ONE block whose body still holds ``` marker lines. Re-wrapping
# that body as "```bash\n...\n```" and re-parsing it through
# `check_readme_sync.all_bash_lines` re-split it on those inner markers and
# silently dropped every region whose re-derived language was not `bash` — with
# no diagnostic anywhere, because the outer fence closed cleanly. These three
# shapes are the reviewer's probes B, C and D, each of which produced exit 0.


def test_a_mispaired_closer_does_not_silently_drop_a_later_block(tmp_path):
    # Probe B. `` ``` (note) `` carries trailing text, so it is not a close and
    # the whole document is one block. Both commands are stale; both must be
    # reported, each on the line it is actually written on.
    skill, root = _tree(tmp_path, """\
```bash
diagrid agent create alpha-agent --wait --nosuchflag1
``` (note)
```python
diagrid agent create beta-agent --wait --nosuchflag2
```
""")
    problems = check(skill, root)
    assert any(p.startswith("SKILL.md:2:") and "alpha-agent" in p for p in problems)
    assert any(p.startswith("SKILL.md:5:") and "beta-agent" in p for p in problems)


def test_a_four_backtick_wrapper_does_not_hide_the_block_it_wraps(tmp_path):
    # Probe C. The shape an author writes to SHOW a fence — the skill teaches
    # people to write markdown, so this is a realistic thing for it to gain.
    skill, root = _tree(tmp_path, """\
Write the block like this:

````markdown
```bash
diagrid project create demo --enable-agent-infrastructure --wait --use
```
````
""")
    problems = check(skill, root)
    assert any("enable-agent-infrastructure" in p for p in problems)
    assert any(p.startswith("SKILL.md:5:") for p in problems)


def test_a_tilde_wrapper_does_not_hide_the_block_it_wraps(tmp_path):
    # Probe D. Same shape with the `~~~` marker, which is the marker the fence
    # widening newly added and the one that introduced this hole.
    skill, root = _tree(tmp_path, """\
Write the block like this:

~~~markdown
```bash
diagrid project create demo --enable-agent-infrastructure --wait --use
```
~~~
""")
    problems = check(skill, root)
    assert any("enable-agent-infrastructure" in p for p in problems)
    assert any(p.startswith("SKILL.md:5:") for p in problems)


# --- I1: the last-resort net that makes the invariant independent of pairing --


def test_a_command_in_an_orphan_gap_between_fences_is_still_checked(tmp_path):
    # The author meant lines 1 and 5 to be the pair and typed a stray ``` at
    # line 3. Fence pairing takes lines 1-3 as the block, leaves line 4 outside
    # every block, and reports line 5 as unterminated. Line 4 is in a code span
    # nobody wrote and a fence nobody recognised: without the net it is checked
    # by no path at all, and drift there is silent.
    skill, root = _tree(tmp_path, """\
```bash
diagrid agent create alpha-agent --wait --nosuchflag1
```
diagrid agent create beta-agent --wait --nosuchflag2
```
""")
    problems = check(skill, root)
    assert any("alpha-agent" in p for p in problems)
    assert any(p.startswith("SKILL.md:4:") and "beta-agent" in p for p in problems)


def test_the_net_does_not_double_report_a_line_a_fence_already_checked(tmp_path):
    # Every fenced command line is also a raw line of the file, so the net must
    # report only what the structured paths did not account for. One stale
    # command, one finding.
    skill, root = _tree(tmp_path, """\
```bash
diagrid agent create langgraph-agent --wait
```
""")
    problems = check(skill, root)
    assert len([p for p in problems if "langgraph-agent" in p]) == 1


def test_the_net_respects_an_illustrative_exemption(tmp_path):
    # A block the author exempted is accounted for, exemption included: the net
    # must not re-report through the back door what the fenced path let through.
    skill, root = _tree(tmp_path, """\
<!-- illustrative: constructed to show the commands key; no README documents this -->

```bash
diagrid mcp grant --caller x --tool add
```
""")
    assert check(skill, root) == []

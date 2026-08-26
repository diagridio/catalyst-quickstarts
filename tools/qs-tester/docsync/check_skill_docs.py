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

Scope is diagrid CLI usage, wherever the skill actually writes it: a line
beginning `diagrid` inside a fenced block of any language (an untagged fence, or
one of the ```python/```robotframework blocks that embed a command as a string
literal), and an inline single-backtick code span in prose — which turns out to
be how the skill actually shows most of its `diagrid` examples. `uv`, `robot` and
`curl` mentions are harness usage no README documents and stay out of scope
either way: they never start with `diagrid`, never start with a CLI object word
the corpus actually documents, and are never made up entirely of `--flag` tokens.

Two candidates need two different rules, because most inline mentions are partial
references rather than full invocations:

  1. Whole-command check: a candidate that starts with the literal word `diagrid`,
     names at least one flag, and holds no doc-placeholder (`<...>` or `{...}`)
     must match a documented command verbatim (after project-name masking). A
     flagless mention like `diagrid dev run` or `diagrid login` skips this rule
     entirely — it names nothing that could be stale, and every documented `dev
     run` spells more than that bare pair of words, so demanding a verbatim match
     would flag a true statement no README happens to phrase identically.

  2. Flag-level check: every `--flag` a candidate names, fenced or inline,
     placeholder or not, must appear in some documented `diagrid` command for the
     same CLI object (`project`, `agent`, `dev`, ...). This is the rule that
     actually catches `--enable-agent-infrastructure`: no README documents it for
     `project create` any more, so it fails whether written as `<name>`,
     `{project}`, or a real name, and whether or not the skill bothered to spell
     out the leading `diagrid` in that sentence.

A candidate that matches `_SANCTIONED_EXCEPTIONS` exactly skips both rules: the
design names exactly two commands CI runs that no README will ever document (the
other is the project name, already handled by `mask_project_name`), and neither
is a documentation gap to report.

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

# `<!-- illustrative: reason -->` exempts a candidate. A missing reason is itself
# a failure: an exemption nobody had to justify is how an exemption list rots
# into a way of silencing real drift. For a fenced block the tag must be one of
# the three lines above the fence (unchanged); for an inline candidate the tag
# exempts every candidate in the same paragraph, since a code span in prose has
# no block boundary of its own and a paragraph is the natural unit a single
# explanatory comment covers.
_ILLUSTRATIVE = re.compile(r"<!--\s*illustrative:(?P<reason>.*?)-->", re.IGNORECASE | re.DOTALL)
_FENCE_OPEN = re.compile(r"^```(\w*)\s*$")
_INLINE_CODE = re.compile(r"`([^`]+)`", re.DOTALL)
# A flag-only span is only trusted as a `diagrid` reference if its flag is a
# hyphenated compound (`--enable-agent-infrastructure`, `--deploy-managed-kv`):
# that naming shape is distinctive to diagrid's own flags in this document. A
# single bare word (`--variable`, `--nightly`, `--validate`) is generic enough
# that, with no `diagrid` or CLI object anywhere in the span to anchor it, it
# is exactly as likely to belong to `robot`, `ci/list-suites.py`, or
# `suites.validate()` — all of which this skill's prose mentions by a bare
# flag the same way it mentions diagrid's.
_COMPOUND_FLAG_TOKEN = re.compile(r"^--[A-Za-z]+(?:-[A-Za-z]+)+$")

# Sanctioned exceptions: commands CI actually runs that no README will ever
# document, because the design deliberately deviates from the README for a
# reason that has nothing to do with drift. This list is closed BY THE DESIGN,
# named in SKILL.md and tools/qs-tester/README.md as exactly two exceptions —
# it is not a convenience for silencing failures, and is not the place to put
# a command that merely lacks a README yet. The other sanctioned exception,
# the project name, is already handled structurally by `mask_project_name`,
# not by this list.
#
# Matched exactly against the masked candidate, never as a prefix or
# substring: `diagrid login --api-key` with a different value, or `diagrid
# login` with some other flag, is not this exception and must still be
# checked normally.
_SANCTIONED_EXCEPTIONS = (
    # CI runs this in place of the documented bare `diagrid login`, which
    # blocks on an interactive browser prompt (`ci/login.sh`). It is a real
    # command CI actually runs, not a constructed example, so it does not get
    # an `illustrative` tag either: that would misdescribe it, and the tag's
    # block/paragraph-wide exemption would silently cover any other command
    # that later sits next to it in the same paragraph or block.
    'diagrid login --api-key "$DIAGRID_API_KEY"',
)

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


def _flag_vocabulary(documented):
    """Every `--flag` documented for each CLI object (`project`, `agent`, ...),
    plus the global union, for the flag-level check.

    Grouped by object rather than the full two-word subcommand (`project
    create` vs `project delete`) because an inline mention regularly elides the
    verb — `` `project create --enable-agent-infrastructure --wait` `` names
    the object but a headless candidate cannot always be trusted to spell out
    which verb it means. Object-level grouping still separates namespaces that
    matter (`dev`'s `--skip-managed-kv` is not a `project` flag) while staying
    simple enough to compute from the corpus alone.
    """
    flags_by_object = {}
    all_flags = set()
    for command in documented:
        tokens = command.split()
        if len(tokens) < 2 or tokens[0] != "diagrid":
            continue
        obj = tokens[1]
        flags = {t for t in tokens if t.startswith("--")}
        flags_by_object.setdefault(obj, set()).update(flags)
        all_flags.update(flags)
    return flags_by_object, all_flags


def _known_objects(documented):
    """CLI object words (`project`, `agent`, `dev`, ...) actually seen right
    after `diagrid` somewhere in the corpus. Used to recognise a headless
    inline mention (`project create ...`, no `diagrid`) as in scope without
    hard-coding the CLI's vocabulary."""
    objects = set()
    for command in documented:
        tokens = command.split()
        if len(tokens) > 1 and tokens[0] == "diagrid":
            objects.add(tokens[1])
    return objects


def _is_flag_only(text):
    """True if `text` is nothing but one or more hyphenated-compound `--flag`
    tokens — how the skill shows a diagrid flag in isolation, e.g.
    `` `--enable-agent-infrastructure` ``, with no command around it at all."""
    tokens = [t.strip(",.;:") for t in text.split()]
    return bool(tokens) and all(_COMPOUND_FLAG_TOKEN.match(t) for t in tokens)


def _object_word(tokens):
    """The CLI object a candidate's flags belong to: `project` from either
    `diagrid project create ...` or a headless `project create ...`. `None`
    for a bare `--flag` mention with no object at all, which falls back to
    checking the flag against the whole corpus rather than one object's slice
    of it.
    """
    if not tokens:
        return None
    if tokens[0] == "diagrid":
        return tokens[1] if len(tokens) > 1 else None
    if tokens[0].startswith("--"):
        return None
    return tokens[0]


def _check_candidate(path, line_no, text, documented, flags_by_object, all_flags):
    """Rule 1 (whole-command) then rule 2 (flag-level) for one `diagrid`
    candidate, fenced or inline. Returns a list of problem strings."""
    masked = mask_project_name(text)

    if masked in _SANCTIONED_EXCEPTIONS:
        return []

    # Flags and the CLI object come from the UNMASKED text on purpose.
    # `mask_project_name`'s positional-name pattern assumes `project
    # create`/`delete` is always followed by a name token and consumes
    # whatever comes next; a headless mention that skips the name entirely
    # (`project create --enable-agent-infrastructure --wait`, as the skill
    # itself does in prose) would have its first flag swallowed as if it were
    # the name, hiding exactly the flag this check exists to catch. Masking is
    # still needed for rule 1's verbatim comparison against `documented`
    # (which stores masked commands), just not for deciding which flags a
    # candidate names.
    tokens = text.split()
    flags = [t.rstrip(",.;:") for t in tokens if t.startswith("--")]
    has_placeholder = ("<" in text and ">" in text) or ("{" in text and "}" in text)

    # Rule 1: restricted to candidates that literally start with `diagrid` and
    # name at least one flag. A headless or flag-only mention can never equal a
    # corpus entry (every documented command starts with `diagrid`), so
    # whole-matching those would only ever fail; a flagless `diagrid ...`
    # mention names nothing that could be stale, so it has nothing to verify.
    if tokens and tokens[0] == "diagrid" and flags and not has_placeholder:
        if masked in documented:
            return []
        close = difflib.get_close_matches(masked, sorted(documented), n=1)
        hint = f"\n  closest documented: {close[0]}" if close else ""
        return [
            f"{path.name}:{line_no}: shows a command no README documents:\n"
            f"  {text}{hint}\n"
            "  Either correct it against the README it describes, or tag the block "
            "`<!-- illustrative: <reason> -->` if it is deliberately constructed."
        ]

    # Rule 2: every flag must be documented for the same object, regardless of
    # placeholders — this is what catches a flag that has quietly stopped being
    # documented for any concrete command at all.
    object_word = _object_word(tokens)
    allowed = flags_by_object.get(object_word, set()) if object_word else all_flags
    problems = []
    for flag in flags:
        if flag in allowed:
            continue
        where = f"`diagrid {object_word}`" if object_word else "any documented `diagrid` command"
        problems.append(
            f"{path.name}:{line_no}: shows `{flag}`, which no README documents for {where}:\n"
            f"  {text}\n"
            "  Either correct it against the README it describes, or tag the block "
            "`<!-- illustrative: <reason> -->` if it is deliberately constructed."
        )
    return problems


def _no_reason_problem(path, line_no):
    return (
        f"{path.name}:{line_no}: an `illustrative` tag with no reason. "
        "State why no README documents this command, so the exemption is a "
        "decision rather than a way to silence the check."
    )


def _fence_spans(lines):
    """Yield 0-based (open_index, close_index) inclusive for each fenced block,
    of any language including untagged fences."""
    index = 0
    while index < len(lines):
        if _FENCE_OPEN.match(lines[index]):
            start = index
            end = start + 1
            while end < len(lines) and not lines[end].startswith("```"):
                end += 1
            yield start, min(end, len(lines) - 1)
            index = end + 1
        else:
            index += 1


def _blocks_with_context(markdown):
    """Yield (line_number, body, preceding_text) for each fenced block."""
    lines = markdown.splitlines()
    for start, end in _fence_spans(lines):
        body = "\n".join(lines[start + 1 : end])
        preceding = "\n".join(lines[max(0, start - 3) : start])
        yield start + 1, body, preceding


def _blank_fenced_regions(lines):
    """`lines` with every fenced block's content replaced by blanks, so inline
    code-span scanning only sees prose. Line numbers are preserved."""
    blanked = list(lines)
    for start, end in _fence_spans(lines):
        for i in range(start, end + 1):
            blanked[i] = ""
    return blanked


def _inline_candidates(markdown, known_objects):
    """Yield (line_number, text) for each inline `` `...` `` code span that
    looks like a diagrid CLI reference: it starts with `diagrid`, it starts
    with a CLI object word actually documented somewhere in the corpus (a
    headless `project create ...`), or it is made up entirely of `--flag`
    tokens with no command around it at all.

    A CommonMark inline span may itself wrap across a soft line break — the
    skill does this in a bullet point (`` `diagrid\\n  project create <name>
    ...` ``) — so line endings inside the span collapse to a single space
    before classifying it, matching how the span actually reads.
    """
    lines = markdown.splitlines()
    prose = "\n".join(_blank_fenced_regions(lines))
    for match in _INLINE_CODE.finditer(prose):
        raw = match.group(1)
        text = " ".join(raw.split())
        if not text:
            continue
        first = text.split()[0]
        if not (first == "diagrid" or first in known_objects or _is_flag_only(text)):
            continue
        # Anchor the report on the flag itself, not the opening backtick: a
        # span that wraps across a line break otherwise reports the line
        # above the one a reader (or `grep`) would actually find the flag on.
        flag_match = re.search(r"--[A-Za-z]", raw)
        offset = match.start(1) + (flag_match.start() if flag_match else 0)
        line_no = prose[:offset].count("\n") + 1
        yield line_no, text


def _paragraph_bounds(lines, line_no):
    """0-based (start, end) inclusive index bounds of the run of non-blank
    lines around 1-based `line_no` — the paragraph it sits in."""
    index = line_no - 1
    start = index
    while start > 0 and lines[start - 1].strip():
        start -= 1
    end = index
    while end < len(lines) - 1 and lines[end + 1].strip():
        end += 1
    return start, end


def _illustrative_tag_in_paragraph(lines, line_no):
    """The `illustrative` tag match if the paragraph containing `line_no`
    carries one, else `None`."""
    start, end = _paragraph_bounds(lines, line_no)
    paragraph = "\n".join(lines[start : end + 1])
    return _ILLUSTRATIVE.search(paragraph)


def check(skill_dir, repo_root):
    """Return a list of problem descriptions. Empty means the skill is in sync."""
    skill_dir, repo_root = Path(skill_dir), Path(repo_root)
    documented = documented_commands(repo_root)
    flags_by_object, all_flags = _flag_vocabulary(documented)
    known_objects = _known_objects(documented)
    problems = []

    files = [skill_dir / "SKILL.md", *sorted(skill_dir.glob("references/*.md"))]
    for path in files:
        if not path.is_file():
            continue
        markdown = path.read_text()
        lines = markdown.splitlines()

        # Fenced blocks: unchanged scope (a line literally starting with
        # `diagrid`, in a fence of any language), now run through the same
        # two-rule check as inline candidates.
        for line_no, body, preceding in _blocks_with_context(markdown):
            tag = _ILLUSTRATIVE.search(preceding)
            if tag:
                if not tag.group("reason").strip():
                    problems.append(_no_reason_problem(path, line_no))
                continue
            for line in all_bash_lines(f"```bash\n{body}\n```"):
                if not line.startswith("diagrid"):
                    continue
                problems.extend(
                    _check_candidate(path, line_no, line, documented, flags_by_object, all_flags)
                )

        # Inline code spans: the skill mostly teaches by prose, not fences.
        for line_no, text in _inline_candidates(markdown, known_objects):
            tag = _illustrative_tag_in_paragraph(lines, line_no)
            if tag:
                if not tag.group("reason").strip():
                    problems.append(_no_reason_problem(path, line_no))
                continue
            problems.extend(
                _check_candidate(path, line_no, text, documented, flags_by_object, all_flags)
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

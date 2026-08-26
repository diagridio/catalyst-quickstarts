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
beginning `diagrid` inside a fenced block of any language, backtick or tilde,
indented inside a list item or not, with or without an info string (an untagged
fence, or one of the ```python/```robotframework blocks that embed a command as
a quoted string literal — including one Python has wrapped across two adjacent
literals rather than written on a single line); and an inline single-backtick
code span in prose, which turns out to be how the skill actually shows most of
its `diagrid` examples. `uv`, `robot` and `curl` mentions are harness usage no
README documents and stay out of scope either way: they never start with
`diagrid`, never start with a CLI object word the corpus actually documents, and
are never made up entirely of `--flag` tokens.

A fence with no matching close before end of file is reported as its own
problem rather than silently treated as running to end of file: for a checker
whose only value is failing on drift, quietly checking nothing for the rest of
the document is worse than a false positive.

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

A bare `--` stops flag collection: by shell convention everything after it
belongs to a wrapped command (`diagrid dev run --approve -- mvn spring-boot:run`),
not to diagrid, and must not be attributed to diagrid's flag vocabulary or
checked against it.

An `illustrative`-looking comment missing the required colon exempts nothing
and is reported as its own problem naming the required form, rather than
silently falling through to be reported as ordinary drift with no hint that an
exemption was even attempted.

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
# explanatory comment covers. Sharp edge worth naming: a tight bullet list has
# no blank lines between items, so a tag placed above the list exempts every
# bullet in it, not just the one it was meant for — and bullets are this
# skill's dominant prose shape. Left as a known edge rather than fixed here.
_ILLUSTRATIVE = re.compile(r"<!--\s*illustrative:(?P<reason>.*?)-->", re.IGNORECASE | re.DOTALL)
# A comment that mentions `illustrative` but is missing the required colon
# (`<!-- illustrative -->`, `<!-- illustrative reason -->`) matches neither the
# well-formed tag above nor an exemption: it would otherwise exempt nothing and
# raise no error either, leaving the candidate reported as ordinary drift with
# no hint that an exemption was even attempted.
_ILLUSTRATIVE_MALFORMED = re.compile(r"<!--\s*illustrative(?!\s*:)", re.IGNORECASE)
# A fence marker: 3+ backticks or tildes, optionally indented (inside a list
# item), with anything as an info string. The SAME pattern is reused to find
# the matching close, which additionally requires the same fence character,
# at least as many characters, and nothing but whitespace after the marker —
# an info string on what would otherwise be a plain "```" close means it is
# not a close at all, and treating it as one is what let a later, unrelated
# fence get misread as belonging to this one.
_FENCE_MARK = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")
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

# A quoted string literal, single- or double-quoted, understanding a
# backslash escape so it doesn't stop at an escaped quote character. Used to
# find a `diagrid` command written as a data-module string, e.g. `python`'s
# `COMMANDS = ("diagrid ...",)`.
_QUOTED_STRING = re.compile(r'(["\'])((?:\\.|(?!\1).)*)\1')

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


def _flags(tokens):
    """`--flag` tokens in `tokens`, stopping at a bare `--`.

    By shell convention everything after a lone `--` belongs to a wrapped
    command (`diagrid dev run --approve -- mvn spring-boot:run`), not to
    diagrid itself — a bare `--` is not a flag either, and without this stop
    it was quietly entering `dev`'s vocabulary from exactly that documented
    command, and a foreign flag after it (`-- uvicorn --port 8000`) was being
    checked as if it were diagrid's own.
    """
    flags = []
    for token in tokens:
        if token == "--":
            break
        if token.startswith("--"):
            flags.append(token.rstrip(",.;:"))
    return flags


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
        flags = set(_flags(tokens))
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
    flags = _flags(tokens)
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


def _malformed_illustrative_problem(path, line_no, context):
    """A problem string if `context` holds an `illustrative`-looking comment
    missing the required colon, else `None`. Reported in addition to, not
    instead of, whatever the candidate's own check finds: the malformed
    comment exempts nothing (the safe direction), but silently — an author who
    wrote it believing it was an exemption gets no signal that it did not
    work, just an ordinary drift report with no mention of the attempt.
    """
    if _ILLUSTRATIVE.search(context) or not _ILLUSTRATIVE_MALFORMED.search(context):
        return None
    return (
        f"{path.name}:{line_no}: a comment near here looks like an `illustrative` "
        "tag but is missing the colon, so it exempts nothing. The required form is "
        "exactly `<!-- illustrative: <reason> -->`."
    )


def _fence_spans(lines):
    """Yield 0-based (open_index, close_index, closed) for each fence marker
    line: `(open, close, True)` for a properly closed fence, of any language,
    backtick or tilde, indented or not; `(open, open, False)` for a marker
    with no matching close before end of file.

    An unterminated fence is NOT treated as running to end of file. The
    caller reports it as its own problem via `_unterminated_fence_lines`, and
    scanning continues past just that one marker line, so one broken fence
    does not stop the rest of the document from being checked.
    """
    index = 0
    while index < len(lines):
        opener = _FENCE_MARK.match(lines[index])
        if not opener:
            index += 1
            continue
        marker = opener.group(1)
        fence_char, min_len = marker[0], len(marker)
        end = index + 1
        while end < len(lines):
            closer = _FENCE_MARK.match(lines[end])
            if (
                closer
                and closer.group(1)[0] == fence_char
                and len(closer.group(1)) >= min_len
                and not closer.group(2).strip()
            ):
                yield index, end, True
                index = end + 1
                break
            end += 1
        else:
            yield index, index, False
            index += 1


def _blocks_with_context(markdown):
    """Yield (line_number, body, preceding_text) for each properly closed
    fenced block. An unterminated marker is skipped here; `check()` reports it
    separately via `_unterminated_fence_lines`."""
    lines = markdown.splitlines()
    for start, end, closed in _fence_spans(lines):
        if not closed:
            continue
        body = "\n".join(lines[start + 1 : end])
        preceding = "\n".join(lines[max(0, start - 3) : start])
        yield start + 1, body, preceding


def _unterminated_fence_lines(markdown):
    """1-based line numbers of fence markers with no matching close."""
    lines = markdown.splitlines()
    return [start + 1 for start, _end, closed in _fence_spans(lines) if not closed]


def _blank_fenced_regions(lines):
    """`lines` with every fenced block's content replaced by blanks, so inline
    code-span scanning only sees prose. Line numbers are preserved. An
    unterminated marker blanks only its own line — nothing after it, since it
    is not actually fencing anything."""
    blanked = list(lines)
    for start, end, _closed in _fence_spans(lines):
        for i in range(start, end + 1):
            blanked[i] = ""
    return blanked


def _quoted_command_candidates(body):
    """Every run of adjacent quoted string literals in a fence body, joined
    the way Python's implicit adjacent-literal concatenation would join them,
    whose combined content starts with `diagrid`.

    This is what lets a `diagrid` command embedded as a data-module string
    literal count as a candidate — a `python` fence's `COMMANDS = ("diagrid
    ...",)`, the shape of `references/agent-quickstart.md`'s
    `REQUESTS[...]["commands"]` example — including one Python has wrapped
    across two adjacent literals rather than written on a single line. A
    naive per-line quote strip would see that as two truncated, unmatchable
    fragments and misreport a command that, joined, is exactly what a README
    documents.

    Yields (0-based line offset within `body`, joined content).
    """
    tokens = list(_QUOTED_STRING.finditer(body))
    i = 0
    while i < len(tokens):
        start = tokens[i].start()
        content = tokens[i].group(2)
        j = i + 1
        while j < len(tokens) and not body[tokens[j - 1].end() : tokens[j].start()].strip():
            content += tokens[j].group(2)
            j += 1
        normalised = " ".join(content.split())
        if normalised.startswith("diagrid"):
            yield body[:start].count("\n"), normalised
        i = j


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


def _paragraph_text(lines, line_no):
    """The text of the paragraph (run of non-blank lines) containing
    1-based `line_no`."""
    start, end = _paragraph_bounds(lines, line_no)
    return "\n".join(lines[start : end + 1])


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

        # A fence with no matching close is a problem in its own right —
        # everything after it would otherwise go unchecked for this block.
        for line_no in _unterminated_fence_lines(markdown):
            problems.append(
                f"{path.name}:{line_no}: fenced block opened here has no closing "
                "```/~~~ before end of file (or a later ``` that was meant to close "
                "it was mistaken for the opener of a new block, because it carried "
                "extra text after the marker). Close the fence, or remove the extra "
                "text from the line meant to close it."
            )

        # Fenced blocks: unchanged scope (a line literally starting with
        # `diagrid`, in a fence of any language), now run through the same
        # two-rule check as inline candidates, plus a second extraction for a
        # `diagrid` command embedded as a quoted string literal.
        for line_no, body, preceding in _blocks_with_context(markdown):
            tag = _ILLUSTRATIVE.search(preceding)
            if tag:
                if not tag.group("reason").strip():
                    problems.append(_no_reason_problem(path, line_no))
                continue
            malformed = _malformed_illustrative_problem(path, line_no, preceding)
            if malformed:
                problems.append(malformed)
            for line in all_bash_lines(f"```bash\n{body}\n```"):
                if not line.startswith("diagrid"):
                    continue
                problems.extend(
                    _check_candidate(path, line_no, line, documented, flags_by_object, all_flags)
                )
            for offset, content in _quoted_command_candidates(body):
                problems.extend(
                    _check_candidate(
                        path, line_no + 1 + offset, content, documented, flags_by_object, all_flags
                    )
                )

        # Inline code spans: the skill mostly teaches by prose, not fences.
        for line_no, text in _inline_candidates(markdown, known_objects):
            paragraph = _paragraph_text(lines, line_no)
            tag = _ILLUSTRATIVE.search(paragraph)
            if tag:
                if not tag.group("reason").strip():
                    problems.append(_no_reason_problem(path, line_no))
                continue
            malformed = _malformed_illustrative_problem(path, line_no, paragraph)
            if malformed:
                problems.append(malformed)
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

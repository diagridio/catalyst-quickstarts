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

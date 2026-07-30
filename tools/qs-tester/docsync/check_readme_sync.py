"""Assert each quickstart README's commands match what the suites actually run.

The READMEs are the source of truth for the end-to-end suites, so a README edit
that the suites have not followed is drift. This catches that on every PR, with no
credentials and no Catalyst project.

The check runs one way only: every documented command must be covered by the
harness. The suites legitimately do things no README describes — poll a health
endpoint, wait for a readiness marker, create and delete a project — so checking
the reverse direction would flag the harness's own internals.

Usage:
    python docsync/check_readme_sync.py state python
    python docsync/check_readme_sync.py --all
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path

# pytest's `pythonpath = ["docsync", "variables"]` setting (pyproject.toml) only
# applies when running under pytest. Running this file directly as a script
# (`uv run python docsync/check_readme_sync.py`) needs the variables directory
# on sys.path too, so the CLI entry point adds it itself.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "variables"))

import quickstarts as qs

# A fenced block: ```<lang>\n<body>\n```
_FENCE = re.compile(r"^```(\w*)\n(.*?)^```", re.MULTILINE | re.DOTALL)
# A section heading: `## 4. ...` or `### 6.1 ...`
_HEADING = re.compile(r"^#{2,3} (\d+(?:\.\d+)?)\.? ", re.MULTILINE)


def _section_span(markdown: str, section: str) -> tuple[int, int]:
    """Character span of a numbered section, up to the next same-or-higher heading."""
    starts = [(m.group(1), m.start()) for m in _HEADING.finditer(markdown)]
    for i, (number, start) in enumerate(starts):
        if number != section:
            continue
        for later_number, later_start in starts[i + 1 :]:
            # A subsection (6.1 inside 6) stays part of the parent section.
            if not later_number.startswith(f"{section}."):
                return start, later_start
        return start, len(markdown)
    return 0, 0


def _blocks(markdown: str, section: str, language: str) -> list[str]:
    start, end = _section_span(markdown, section)
    return [
        body.strip()
        for lang, body in (
            (m.group(1), m.group(2)) for m in _FENCE.finditer(markdown[start:end])
        )
        if lang == language
    ]


def extract_bash_blocks(markdown: str, section: str) -> list[str]:
    """Fenced ```bash blocks in a section. PowerShell blocks are ignored:
    every request is documented three ways and the suites use one."""
    return _blocks(markdown, section, "bash")


def extract_json_blocks(markdown: str, section: str) -> list[dict]:
    """Parsed ```json blocks in a section — the documented expected bodies.
    Blocks containing placeholders like <YOUR_INSTANCE_ID> are skipped, since
    they are illustrative rather than assertable."""
    parsed = []
    for block in _blocks(markdown, section, "json"):
        if "<" in block and ">" in block:
            continue
        try:
            parsed.append(json.loads(block))
        except json.JSONDecodeError:
            continue
    return parsed


def extract_curl_calls(markdown: str) -> list[dict]:
    """Method, URL and JSON payload of each documented curl invocation."""
    calls = []
    for block in extract_bash_blocks(markdown, "6"):
        if not block.startswith("curl"):
            continue
        tokens = shlex.split(block)
        method, url, payload = "GET", None, None
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token in ("-X", "--request"):
                method = tokens[i + 1]
                i += 2
            elif token in ("-d", "--data"):
                payload = json.loads(tokens[i + 1])
                i += 2
            elif token in ("-H", "--header"):
                i += 2
            elif token.startswith("http"):
                url = token
                i += 1
            else:
                i += 1
        calls.append({"method": method, "url": url, "payload": payload})
    return calls


def normalise_run_command(command: str) -> str:
    """Collapse the one sanctioned divergence: the READMEs document
    `--project <api>-quickstart`, the harness passes `{project}`."""
    return re.sub(r"--project \S+", "--project PROJECT", command).strip()


def check(api: str, language: str, repo_root: Path) -> list[str]:
    """Return a list of mismatch descriptions; empty means in sync."""
    readme = repo_root / api / language / "README.md"
    if not readme.is_file():
        return [f"{api}/{language}: README.md not found"]
    markdown = readme.read_text()
    problems = []
    where = f"{api}/{language}"

    documented_install = "\n".join(extract_bash_blocks(markdown, "4"))
    harness_install = qs.INSTALL[(api, language)]
    for line in documented_install.splitlines():
        line = line.strip()
        # Activation is expressed as `. .venv/bin/activate` in the harness and
        # `source .venv/bin/activate` in the README; same thing, different spelling.
        if line.startswith("source "):
            line = ". " + line.split(" ", 1)[1]
        # The READMEs document `npm install` because that is the right advice for a
        # reader: it works from a clean checkout and tolerates a lockfile that has
        # drifted from package.json. The harness deliberately runs `npm ci` instead,
        # because `npm install` REWRITES package-lock.json (it normalises the `name`
        # field to the directory name), which dirties the working tree on every
        # javascript leg and shows up as a spurious diff in CI. `npm ci` installs the
        # same locked dependency set and never writes the lockfile. Treat the two as
        # equivalent here rather than degrading the READMEs to match the harness.
        # Tradeoff: the javascript legs therefore no longer prove that the documented
        # `npm install` itself succeeds.
        line = line.replace("npm install", "npm ci")
        if line and line not in harness_install:
            problems.append(
                f"{where}: README install step not in harness: {line!r}\n"
                f"  harness has: {harness_install!r}"
            )

    documented_run = extract_bash_blocks(markdown, "5")
    if not documented_run:
        problems.append(f"{where}: no bash block found in README section 5")
    else:
        want = normalise_run_command(documented_run[0])
        got = normalise_run_command(qs.RUN[(api, language)])
        if want != got:
            problems.append(
                f"{where}: run command differs\n  README:  {want}\n  harness: {got}"
            )

    for call in extract_curl_calls(markdown):
        if call["payload"] is None:
            continue
        known = (qs.ORDER_PAYLOAD, qs.WORKFLOW_PAYLOAD)
        if call["payload"] not in known:
            problems.append(
                f"{where}: documented payload {call['payload']!r} is not one of "
                f"the harness payloads {known!r}"
            )

    expected_bodies = extract_json_blocks(markdown, "6")
    harness_bodies = _harness_bodies(api, language)
    for body in expected_bodies:
        if body not in harness_bodies:
            problems.append(
                f"{where}: README expected body not asserted by the harness:\n"
                f"  {body!r}\n  harness asserts: {harness_bodies!r}"
            )

    return problems


def _harness_bodies(api: str, language: str) -> list[dict]:
    """Every response body the suite for this (api, language) asserts."""
    if api == "state":
        return [qs.STATE_STORE_BODY[language], qs.STATE_RETRIEVE_BODY[language]]
    if api == "pubsub":
        return [qs.PUBSUB_PUBLISH_BODY[language]]
    if api == "invocation":
        return [qs.INVOCATION_BODY]
    # workflow: the start response is documented only with a placeholder instance
    # id, which extract_json_blocks skips, and the status body is not documented
    # concretely except for python's, which the suite asserts by key not by body.
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("api", nargs="?", choices=qs.APIS)
    parser.add_argument("language", nargs="?", choices=qs.LANGUAGES)
    parser.add_argument("--all", action="store_true", help="check all 16")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="repository root (default: three levels above this file)",
    )
    args = parser.parse_args()

    if args.all:
        pairs = [(a, l) for a in qs.APIS for l in qs.LANGUAGES]
    elif args.api and args.language:
        pairs = [(args.api, args.language)]
    else:
        parser.error("give both api and language, or --all")

    problems = []
    for api, language in pairs:
        problems.extend(check(api, language, args.repo_root))

    if problems:
        for problem in problems:
            print(f"::error::{problem}")
        print(f"\n{len(problems)} README/harness mismatch(es) in {len(pairs)} directories")
        return 1

    print(f"All {len(pairs)} README(s) in sync with the harness")
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
import importlib
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


def extract_json_bodies(markdown: str, section: str) -> list[dict]:
    """Documented response bodies in a section, from ```json AND ```text blocks.

    Section 7 quotes its response bodies in ```text blocks rather than ```json, so
    looking only at ```json would silently check nothing there.
    """
    bodies = list(extract_json_blocks(markdown, section))
    for block in _blocks(markdown, section, "text"):
        if not block.startswith("{"):
            continue
        try:
            bodies.append(json.loads(block))
        except json.JSONDecodeError:
            continue
    return bodies


def extract_curl_calls(markdown: str, section: str = "6") -> list[dict]:
    """Method, URL and JSON payload of each documented curl invocation."""
    calls = []
    for block in extract_bash_blocks(markdown, section):
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


def fenced_block_bodies(markdown):
    """The body of every fenced block, whatever its language.

    A log marker is a line the app PRINTS, so it has to be documented as output —
    inside a block — and not merely named in a sentence. Any fence language
    counts: READMEs write output blocks as ```text, ```console or untagged, and
    which one they pick says nothing about whether the marker is real.
    """
    return [m.group(2) for m in _FENCE.finditer(markdown)]


def normalise_project(command, documented_project):
    """Map a documented command onto the harness's `{project}` placeholder."""
    return command.replace(documented_project, "{project}").strip()


# Every attribute an agent-family data module must define. Data modules are
# hand-authored (Task 5+), so a forgotten field is a realistic mistake; reporting
# it as a scoped problem here — rather than letting the attribute access raise —
# means one bad module costs its own row's check, not the other sixteen READMEs
# `--all` also checks in the same run. Only agent-family modules are checked:
# `check_agent` is called from `--all` for `suites.agent_suites()` only, and the
# canonical suites read `variables/quickstarts.py`, a table with a different
# shape entirely.
#
# The first eight are what check_agent itself reads. CONNECTED_APPS,
# HEALTH_PROBES and CATALYST_PROBE_MARKERS are not — they are read by the
# module's own `get_quickstart()` and then indexed as `${qs}[connected_apps]`
# (`catalyst.resource`, by `Wait Until Apps Connected`), `${qs}[health_probes]`
# (`quickstart.resource`, by `Wait Until Apps Healthy`) and
# `${qs}[catalyst_probe_markers]` (`catalyst.resource`, by
# `Wait Until Catalyst Attached`). Empty is legal for all three; absent is
# not, and an absent attribute surfaces only as a NameError
# inside `get_quickstart()` itself — the test's first keyword, before
# `diagrid project create` runs, so no cloud project is spent. (The genuine
# KeyError shape — the attribute exists but `get_quickstart()` drops it from
# the returned dict — is a different failure this guard still does not
# catch.) Doc-sync is the only credential-free check that sees these modules
# at all, so requiring them here is what makes them required.
_REQUIRED_MODULE_ATTRS = (
    "DOCUMENTED_PROJECT",
    "SETUP",
    "INSTALL",
    "RUN",
    "TEARDOWN",
    "READY_MARKERS",
    "REQUESTS",
    "UNCOVERED",
    "CONNECTED_APPS",
    "HEALTH_PROBES",
    "CATALYST_PROBE_MARKERS",
)


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

    where = row["name"]
    missing = [name for name in _REQUIRED_MODULE_ATTRS if not hasattr(module, name)]
    if missing:
        return [
            f"{where}: data module {module!r} is missing required attribute(s): "
            f"{', '.join(missing)}"
        ]

    quickstart_dir = Path(row["suite"]).parent.parent
    readme = repo_root / quickstart_dir / "README.md"
    if not readme.is_file():
        return [f"{row['name']}: {readme} not found"]

    markdown = readme.read_text()
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

    # Log markers must appear inside a fenced block, not merely somewhere in the
    # file. A prose mention is not evidence the app prints anything:
    # `agents/langgraph` shipped `check_availability` as its log marker because
    # the README says "Use the `check_availability` tool" and main.py defines that
    # tool — but `call_tools` invokes it without logging, so the marker could never
    # match. The suite passed this check and then timed out against real Catalyst.
    # Requiring a fenced block ties the marker to documented OUTPUT.
    #
    # READY_MARKERS deliberately does NOT get this rule: `agents/langgraph`
    # documents `Uvicorn running on` as inline code in a sentence ("Wait until the
    # output shows ..."), which is a perfectly good way to document a readiness
    # marker and would fail here.
    fenced = fenced_block_bodies(markdown)
    for marker in [r["log_marker"] for r in module.REQUESTS if r.get("log_marker")]:
        if not any(marker in body for body in fenced):
            if marker in markdown:
                problems.append(
                    f"{where}: log marker {marker!r} appears in the README but not "
                    "inside a fenced block. A log marker is a line the app prints, "
                    "so it must be documented as output; a prose mention is not "
                    "evidence anything prints it."
                )
            else:
                problems.append(
                    f"{where}: log marker {marker!r} does not appear in any fenced "
                    "block in the README"
                )

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

    problems.extend(_check_crash_section(api, language, markdown, where))

    return problems


# The response shape every crash demo returns. Named here so a README that drops a
# field, or renames `result`, fails this check instead of being quietly accepted.
_CRASH_BODY_KEYS = {"id", "result", "message"}
_CRASH_PAYLOAD_KEYS = {"id", "reference"}


def _check_crash_section(api: str, language: str, markdown: str, where: str) -> list[str]:
    """Check README section 7, the crash-recovery demo, against the harness.

    Section 7 was outside this checker when it was written, which is how three
    READMEs came to document three different response bodies for one endpoint.
    """
    if api != "workflow":
        return []

    problems = []
    start, end = _section_span(markdown, "7")
    documented = markdown[start:end]
    has_section = bool(documented.strip()) and "/crash/run" in documented

    if language not in qs.CRASH_LANGUAGES:
        # javascript ships no crash demo. If one appears, the harness needs a case for
        # it, so say so rather than passing silently.
        if has_section:
            problems.append(
                f"{where}: README documents a crash demo but {language} is not in "
                f"CRASH_LANGUAGES, so no suite case drives it"
            )
        return problems

    if not has_section:
        return [f"{where}: no crash-recovery section 7 found, but the harness drives one"]

    # The documented request body. `id` is a sanctioned divergence: the README documents
    # a memorable `trip-42` while the suite mints a unique id per run, precisely so the
    # test can be run twice. `reference` is not: the confirmation code is derived from
    # it, so a README documenting a different one documents a different answer.
    for call in extract_curl_calls(markdown, "7"):
        payload = call["payload"]
        if payload is None:
            continue
        if set(payload) != _CRASH_PAYLOAD_KEYS:
            problems.append(
                f"{where}: documented /crash/run payload has keys {sorted(payload)}, "
                f"expected {sorted(_CRASH_PAYLOAD_KEYS)}"
            )
        if payload.get("reference") != qs.CRASH_REFERENCE:
            problems.append(
                f"{where}: documented reference {payload.get('reference')!r} is not the "
                f"harness reference {qs.CRASH_REFERENCE!r}"
            )

    # The documented response body, which is where the three-way drift lived.
    for body in extract_json_bodies(markdown, "7"):
        if "result" not in body and "message" not in body:
            continue
        if set(body) != _CRASH_BODY_KEYS:
            problems.append(
                f"{where}: documented /crash/run body has keys {sorted(body)}, expected "
                f"{sorted(_CRASH_BODY_KEYS)}: every crash demo returns all three"
            )
        if body.get("result") is not None and body["result"] != qs.CRASH_CONFIRMATION:
            problems.append(
                f"{where}: documented result {body['result']!r} is not the confirmation "
                f"the harness asserts, {qs.CRASH_CONFIRMATION!r}"
            )

    # The proof line the README tells the reader to look for has to be the one the
    # suite waits on. CRASH_COMMITTING_MARKER is deliberately excluded: it carries the
    # delay, and the README documents the 30s default while the suite injects 20s.
    if qs.CRASH_COMMITTED_MARKER not in documented:
        problems.append(
            f"{where}: section 7 never quotes the committed marker the harness waits "
            f"for: {qs.CRASH_COMMITTED_MARKER!r}"
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
    parser.add_argument(
        "--all",
        action="store_true",
        help="check every (api, language) README plus every agent-family suite "
        "registered in variables/suites.py",
    )
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
    # One entry per README this run actually checked. Counting `pairs` alone
    # under-reports as soon as an agent-family suite is registered: `--all`
    # checks those too, and a count that says 16 while 17 READMEs were read
    # quietly hides whichever one was added last.
    checked = []
    for api, language in pairs:
        checked.append(f"{api}/{language}")
        problems.extend(check(api, language, args.repo_root))

    # Agent-family suites are registered in the manifest rather than being a
    # fixed api x language product, so they are checked from there.
    if args.all:
        import suites

        for row in suites.agent_suites():
            checked.append(str(Path(row["suite"]).parent.parent))
            problems.extend(check_agent(row, args.repo_root))

    if problems:
        for problem in problems:
            print(f"::error::{problem}")
        print(f"\n{len(problems)} README/harness mismatch(es) in {len(checked)} directories")
        return 1

    print(f"All {len(checked)} README(s) in sync with the harness")
    return 0


if __name__ == "__main__":
    sys.exit(main())

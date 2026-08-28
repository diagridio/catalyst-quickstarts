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
    {
        "suite": "agents/langgraph/tests/quickstart.robot",
        "family": "agent",
        "name": "langgraph",
        "data": "agents_langgraph",
        "language": "python",
        "runtime": "python",
        # True as of 2026-08-28: this suite has had a green live run against a real
        # Catalyst project AND a mutation check that `ci/check_mutation.py`
        # accepted — READY_MARKERS overridden to "__mutation_check__" made
        # `Wait Until Ready Marker` FAIL, naming the sentinel, with the enclosing
        # test failing too. That is the bar; the two other agent suites have met
        # neither half and stay False.
        #
        # What this does NOT cover: the mutation targeted READY_MARKERS only, so
        # the two assertions added while getting this suite green — the
        # `[ACTIVITY] Executing node 'tools'` log marker and
        # `Wait Until Catalyst Attached` — have not been shown to fail when what
        # they check breaks. Both are worth their own mutation run.
        "nightly": True,
        "secrets": ("OPENAI_API_KEY",),
    },
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
    {
        "suite": "agents/spring-ai/event-planner/tests/quickstart.robot",
        "family": "agent",
        "name": "spring-ai-event-planner",
        "data": "agents_spring_ai_event_planner",
        "language": "java",
        "runtime": "java",
        # False for the same reason as the two rows above: never run live, and
        # this one's `status: 200` is expected to fail when it is. See the
        # harness README's Limitations.
        "nightly": False,
        "secrets": ("OPENAI_API_KEY",),
    },
)

_REQUIRED = {
    "canonical": ("suite", "family", "api", "languages", "nightly", "secrets"),
    "agent": ("suite", "family", "name", "data", "language", "runtime", "nightly", "secrets"),
}

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
    seen_names = set()

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
            if row["name"] in seen_names:
                problems.append(
                    f"{where}: duplicate agent name {row['name']!r}; name keys the "
                    "ephemeral project, the CI artifact and the failure summary "
                    "file, so a second suite reusing it would collide with the "
                    "first at runtime"
                )
            seen_names.add(row["name"])

            leg = leg_id(row)
            if not isinstance(leg, str):
                # `_REQUIRED` only checks key presence, not type, so a `name` (or
                # `leg`) that is present but not a string reaches here. This must
                # report a problem rather than raise: validate() runs in CI's lint
                # job, where an uncaught TypeError is a worse failure mode than a
                # reported problem, and it would also abort validation of every
                # row after this one.
                problems.append(
                    f"{where}: leg {leg!r} must be a string (from `name` or an "
                    f"explicit `leg`), got {type(leg).__name__}"
                )
            elif len(leg) > project_name_budget():
                problems.append(
                    f"{where}: leg {leg!r} is {len(leg)} characters, over the "
                    f"{project_name_budget()}-character budget that keeps the ephemeral "
                    f"project name within {MAX_PROJECT_NAME} characters. Shorten it with an "
                    f"explicit `leg` on this row. Catching it here costs seconds; catching it "
                    f"at `diagrid project create` costs a nightly leg and leaks a half-made project."
                )

            if row["runtime"] not in RUNTIMES:
                problems.append(
                    f"{where}: runtime must be one of {RUNTIMES}, got {row['runtime']!r}"
                )
            data = repo_root / "tools" / "qs-tester" / "variables" / f"{row['data']}.py"
            if not data.is_file():
                problems.append(f"{where}: data module {data.name} does not exist")

    return problems

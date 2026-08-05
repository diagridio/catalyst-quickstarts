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
        "nightly": True,
        "secrets": ("OPENAI_API_KEY",),
    },
)

_REQUIRED = {
    "canonical": ("suite", "family", "api", "languages", "nightly", "secrets"),
    "agent": ("suite", "family", "name", "data", "language", "runtime", "nightly", "secrets"),
}


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
            if row["runtime"] not in RUNTIMES:
                problems.append(
                    f"{where}: runtime must be one of {RUNTIMES}, got {row['runtime']!r}"
                )
            data = repo_root / "tools" / "qs-tester" / "variables" / f"{row['data']}.py"
            if not data.is_file():
                problems.append(f"{where}: data module {data.name} does not exist")

    return problems

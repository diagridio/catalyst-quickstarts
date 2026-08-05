"""The four python-quickstart CI workflows must sync the whole uv workspace.

`uv sync --all-packages` is locked in two other places already: the harness data
(by the tests in test_python_install_run.py) and the READMEs (by
docsync/check_readme_sync.py). Neither of those touches the GitHub Actions
workflow files. Each workflow's "build local" step only proves `uv sync`
succeeds before building and pushing Docker images — it never runs
`diagrid dev run`, so these jobs exit 0 whether or not the app can actually
start. Reverting a "build local" step to the old per-app pattern (e.g.
`cd invocation/python/client && uv sync && cd ../server && uv sync`) would
still pass CI; the regression would only surface in the next nightly
end-to-end run, which is too late to catch it at review time. This test closes
that gap by reading the workflow YAML as plain text (no YAML parser needed,
keeping the lint job's dependencies unchanged).
"""

import re

import pytest
import quickstarts as qs

WORKFLOW_FILES = (
    "invoke_python.yaml",
    "pubsub_python.yaml",
    "state_python.yaml",
    "workflow_python.yaml",
)

# Subdirectories that hold a single app inside a multi-app workspace
# (invocation/pubsub). A `uv sync` run from inside one of these only installs
# that one app's dependencies, not the whole workspace, which is exactly the
# old, broken pattern this guard exists to keep out.
MEMBER_DIRS = ("client", "server", "publisher", "subscriber")

_STEP_START = re.compile(r"^\s*-\s*name:\s*build local\s*$")
_NEXT_STEP = re.compile(r"^\s*-\s*(name|uses):")


def _build_local_step(workflow_file):
    """Return only the text of the "build local" step.

    Scoping to just this step (rather than scanning the whole file) matters
    for the negative check below: later steps in these same workflows build
    and push per-app Docker images and legitimately set
    `working-directory: invocation/python/client` etc. Those are not sync
    commands and must not trip the member-dir check.
    """
    path = qs.REPO_ROOT / ".github" / "workflows" / workflow_file
    lines = path.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if _STEP_START.match(line))
    end = next(
        (i for i in range(start + 1, len(lines)) if _NEXT_STEP.match(lines[i])),
        len(lines),
    )
    return "\n".join(lines[start:end])


@pytest.mark.parametrize("workflow_file", WORKFLOW_FILES)
def test_build_step_syncs_the_whole_workspace(workflow_file):
    step = _build_local_step(workflow_file)
    assert "uv sync --all-packages" in step


@pytest.mark.parametrize("workflow_file", WORKFLOW_FILES)
def test_build_step_has_no_member_level_sync(workflow_file):
    step = _build_local_step(workflow_file)
    for member in MEMBER_DIRS:
        assert member not in step, (
            f"{workflow_file}'s build-local step mentions {member!r} — a "
            "per-app `uv sync` inside a workspace member installs only that "
            "member, not the whole workspace `uv sync --all-packages` needs"
        )

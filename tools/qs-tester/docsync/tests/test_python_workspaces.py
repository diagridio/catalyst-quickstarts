"""invocation/python and pubsub/python are uv workspaces, not two loose projects.

Each holds two apps in subdirectories while `diagrid dev run` runs from the parent
directory, so the virtual environment has to live at the parent. A workspace root
gives both apps one lock and one venv, which is what makes a single
`uv sync --all-packages` able to serve both. See
docs/superpowers/specs/2026-07-31-python-quickstart-uv-workspaces-design.md.
"""

import tomllib

import pytest
import quickstarts as qs

# api -> the app subdirectories that must be declared as workspace members
WORKSPACES = {
    "invocation": ["client", "server"],
    "pubsub": ["publisher", "subscriber"],
}


@pytest.mark.parametrize("api,members", sorted(WORKSPACES.items()))
def test_workspace_root_declares_both_members(api, members):
    root = qs.REPO_ROOT / api / "python" / "pyproject.toml"
    assert root.is_file(), f"{api}/python/pyproject.toml is missing"
    data = tomllib.loads(root.read_text())
    assert data["tool"]["uv"]["workspace"]["members"] == members
    # A [build-system] would make uv try to build the root and members as
    # distributions; they are intentionally non-packaged.
    assert "build-system" not in data


@pytest.mark.parametrize("api,members", sorted(WORKSPACES.items()))
def test_single_lock_lives_at_the_workspace_root(api, members):
    base = qs.REPO_ROOT / api / "python"
    assert (base / "uv.lock").is_file(), f"{api}/python/uv.lock is missing"
    for member in members:
        assert not (base / member / "uv.lock").exists(), (
            f"{api}/python/{member}/uv.lock must be deleted — "
            "the workspace root owns the single lock"
        )

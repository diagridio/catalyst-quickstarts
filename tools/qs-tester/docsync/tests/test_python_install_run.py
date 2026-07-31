"""All python quickstarts document one identical dependency flow.

Section 4 is a single whole-workspace `uv sync --all-packages`, and section 5 is
prefixed with `uv run`, so the venv that sync creates next to the
`diagrid dev run` config is the one the launched app resolves `uvicorn` from.
Nothing is ever activated, which is why there is no OS-specific install step in
the python READMEs any more. See
docs/superpowers/specs/2026-07-31-python-quickstart-uv-workspaces-design.md.
"""

import pytest
import quickstarts as qs

# Widened to all four in the task that converts invocation and pubsub. Keeping it
# narrow means each conversion commit leaves the suite green.
PYTHON_APIS = ("workflow", "state")


@pytest.mark.parametrize("api", PYTHON_APIS)
def test_install_is_one_whole_workspace_sync(api):
    assert qs.INSTALL[(api, "python")] == "uv sync --all-packages"


@pytest.mark.parametrize("api", PYTHON_APIS)
def test_run_is_prefixed_with_uv_run(api):
    assert qs.RUN[(api, "python")].startswith("uv run diagrid dev run")


@pytest.mark.parametrize("api", PYTHON_APIS)
def test_nothing_creates_or_activates_a_venv(api):
    install = qs.INSTALL[(api, "python")]
    assert "uv venv" not in install
    assert "activate" not in install

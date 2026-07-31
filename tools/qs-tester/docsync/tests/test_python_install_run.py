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

PYTHON_APIS = qs.APIS


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


def test_harness_no_longer_tracks_venv_activation():
    """`ACTIVATE_VENV` and the `activate_venv` key existed only to wrap the run
    command in `bash -c '. .venv/bin/activate && ...'`. Nothing activates a venv
    now, so both must be gone — a leftover key invites the wrapper's return."""
    assert not hasattr(qs, "ACTIVATE_VENV")
    assert "activate_venv" not in qs.get_quickstart("invocation", "python")

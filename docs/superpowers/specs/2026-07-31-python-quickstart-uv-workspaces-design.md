# Python quickstarts: uv workspaces and a single documented pattern

Date: 2026-07-31
Status: approved, ready for implementation planning
Branch: `worktree-python-uv-workspaces` (based on `origin/main`)

## Problem

The four Python quickstarts document three different dependency-setup patterns, and one
of them is broken.

`invocation/python` and `pubsub/python` hold two apps in subdirectories (`client`/`server`,
`publisher`/`subscriber`), each its own uv project, while the `diagrid dev run` config sits
in the parent directory. The READMEs bridge that with a shared virtual environment:

```bash
uv venv
source .venv/bin/activate
uv sync --active --directory client && uv sync --active --directory server
```

`uv sync` is exact by default: it removes any package absent from the project it is
syncing. The server sync therefore uninstalls `requests`, a client-only dependency, and
the client dies at startup:

```
== APP - client == ModuleNotFoundError: No module named 'requests'
❌ App process "client" exited with error code: exit status 1
```

This broke the nightly e2e run (GitHub Actions run 30607870105). Reproduced locally with
the repository's own `pyproject.toml`/`uv.lock` files:

```
after client sync: requests -> 2.33.0
after server sync: requests -> ModuleNotFoundError: No module named 'requests'
```

`pubsub/python` runs the same pattern and is not broken only by accident: the subscriber's
dependency set happens to cover the publisher's, so the second sync removes nothing. It
does, however, *replace versions*. Measured:

```
REMOVED by subscriber sync:  aiohttp==3.14.1   starlette==0.52.1
ADDED   by subscriber sync:  aiohttp==3.14.0   starlette==1.0.1  cloudevents …
```

The publisher runs versions from the subscriber's lock rather than its own, so a security
bump landing in `publisher/uv.lock` alone is silently undone in the shared venv. The first
publisher-only *package* anyone adds breaks the leg outright.

Separately, `state/python` documents `uv venv` + activation it does not need (single
project, config alongside), while `workflow/python` — same shape — documents neither and
instead prefixes its run command with `uv run`. Python is the only language whose section 4
carries an OS-split for shell activation.

## Root cause

Two apps, two locks, one shared virtual environment, and a dependency-installer that
prunes. The shared venv is required only because the `diagrid dev run` config launches a
bare `uvicorn`, which must be resolvable on `PATH` in the environment the CLI inherits.

## Design

One invariant replaces the three patterns: **every Python quickstart directory is a uv
project sitting next to its `diagrid dev run` config, so `uv run` finds the venv.**

```
workflow/python/     pyproject.toml  (exists, single project)   uv.lock (exists)
state/python/        pyproject.toml  (exists, single project)   uv.lock (exists)
invocation/python/   pyproject.toml  (NEW, workspace root)      uv.lock (NEW)
                     client/pyproject.toml      (member — dependencies kept, own lock deleted)
                     server/pyproject.toml      (member — dependencies kept, own lock deleted)
pubsub/python/       pyproject.toml  (NEW, workspace root)      uv.lock (NEW)
                     publisher/pyproject.toml   (member)
                     subscriber/pyproject.toml  (member)
```

Both workspace roots are identical apart from the name and members:

```toml
[project]
name = "invocation-python"
version = "0.1.0"
requires-python = ">=3.12"

[tool.uv.workspace]
members = ["client", "server"]
```

The root declares no dependencies; it exists to anchor the workspace and own the shared
`.venv`. With no `[build-system]`, uv treats root and members as non-packaged — verified:
the lock records all three projects, `uv pip list` shows none of them installed as a
distribution, so no `[tool.uv] package = false` is needed.

Members keep their `dependencies` lists untouched. That is what keeps the Dockerfiles
working with no edits: each copies its own `pyproject.toml` and runs
`uv pip install --system .` from inside the member directory, never consulting a lock.

### Documented flow

Identical in all four Python READMEs, differing only in the config filename and project
name. Section 4 loses its macOS/Linux-vs-Windows split entirely, which is the largest
reader-facing improvement:

```bash
# 4. Install Dependencies
uv sync --all-packages

# 5. Run the application with Catalyst Cloud
uv run diagrid dev run -f <api>-quickstart.yaml --project <api>-quickstart --approve
```

`uv sync --all-packages` is used in all four, including the two single-project
quickstarts. Verified to exit 0 on a plain non-workspace project, so it is not misleading
there, and it makes section 4 byte-identical across the four.

The four `diagrid dev run` config files are **not modified**. `command: [uvicorn, main:app, …]`
stays as-is, because `uv run` puts `.venv/bin` on `PATH` and the app inherits it.

This generalises a pattern already proven in this repository rather than inventing one:
`workflow/python` documents `uv run diagrid dev run` today and its e2e leg passes.

### What this buys, precisely

- **Version drift becomes impossible.** One lock per quickstart means one resolution per
  package, whatever is synced.
- **`--inexact` becomes unnecessary.** The documented flow performs a single
  whole-workspace sync, so there is no second sync to prune anything.
- **Dependabot improves with no config change.** The `uv` pull requests are automatic
  security updates that discover lockfiles on their own; they will target one root lock
  per quickstart instead of two that can diverge.

### What this does not buy

The workspace layout alone does **not** prevent pruning. A member-level `uv sync`
resolves upward to the workspace root and syncs only that member into the shared root
venv, still exactly. Verified (`2.34.2` here is the freshly resolved workspace version, not
the `2.33.0` currently pinned in the per-app lock):

```
requests before: 2.34.2
(cd server && uv sync)   ->  - requests==2.34.2
requests after:  ModuleNotFoundError: No module named 'requests'
```

Immunity comes from the invariant *"always sync from the root with `--all-packages`"*, not
from the layout. Consequences: the documented flow must never instruct a member-level
sync, the per-language CI steps must be corrected (below), and the invariant is recorded
as a comment in both workspace roots.

## Changes

### New files

- `invocation/python/pyproject.toml` — workspace root, members `client`, `server`
- `pubsub/python/pyproject.toml` — workspace root, members `publisher`, `subscriber`

### Regenerated / deleted locks

- New: `invocation/python/uv.lock`, `pubsub/python/uv.lock` (via `uv lock` at each root)
- Deleted: `invocation/python/{client,server}/uv.lock`,
  `pubsub/python/{publisher,subscriber}/uv.lock`

### READMEs (all four)

- `workflow/python/README.md`, `state/python/README.md`, `pubsub/python/README.md`,
  `invocation/python/README.md`
- Section 4 becomes a single `uv sync --all-packages` block. Delete the `uv venv` +
  activation blocks and the macOS/Linux-vs-Windows split from `state`, `pubsub` and
  `invocation`. Delete the `--inexact` note from `invocation` (added by the stopgap; see
  Sequencing).
- Section 5 becomes `uv run diagrid dev run -f <api>-quickstart.yaml --project
  <api>-quickstart --approve` in all four. Only `workflow` already reads this way.

### Harness — `tools/qs-tester/variables/quickstarts.py`

- `INSTALL`: all four Python entries become `"uv sync --all-packages"`. Delete the
  `uv venv` explainer comment above the dict.
- `RUN`: add `_UV_DEV_RUN = "uv run " + _DEV_RUN`; all four Python entries use it.
  `workflow/python`'s hand-written string collapses into it.
- Delete the `ACTIVATE_VENV` set and the `"activate_venv"` key returned by
  `get_quickstart()`.

### Harness — `tools/qs-tester/resources/catalyst.resource`

- Delete the `IF ${qs}[activate_venv]` block and its comment in `Start Quickstart`; the
  keyword becomes unconditional.

### Harness — `tools/qs-tester/resources/process.resource`

- **Rewrite the comment above the PID-tree fallback; keep the code.** It currently
  justifies the fallback by naming the `bash -c '. .venv/bin/activate && …'` wrapper.
  Once that wrapper is gone the comment is false and invites deleting a fallback that is
  still required — the chain becomes `diagrid dev run` → `uv run` → `python …/uvicorn`.
  Update the justification to name the `uv run` wrapper.

### Harness — `tools/qs-tester/docsync/check_readme_sync.py`

No change. The `source ` → `. ` normalisation and its two test fixtures stay: generic
input handling that remains correct, and removing it would delete coverage for an idiom
that could reappear. The substring install check and the exact run check both pass with
the new strings.

### CI — per-language workflows

`uv sync` inside a member populates the *root* venv and prunes siblings, so the current
steps would leave the root venv without `requests`. Required, not cleanup:

- `.github/workflows/invoke_python.yaml` — `cd invocation/python/client && uv sync && cd ../server && uv sync`
  becomes `cd invocation/python && uv sync --all-packages`
- `.github/workflows/pubsub_python.yaml` — same shape, becomes
  `cd pubsub/python && uv sync --all-packages`
- `.github/workflows/state_python.yaml`, `.github/workflows/workflow_python.yaml` —
  `uv sync` becomes `uv sync --all-packages`, matching their READMEs

`.github/workflows/e2e-quickstarts.yml` needs no change; it drives everything through the
harness.

### New regression test

In `tools/qs-tester/docsync/tests`, assert every Python `INSTALL` equals
`uv sync --all-packages` and every Python `RUN` starts with `uv run diagrid dev run`. This
locks in the invariant and is the natural first step for the implementation plan.

It belongs in `docsync/tests` specifically because that is the only pytest directory the
`lint` job runs (`uv run pytest docsync/tests -q`), and because `pyproject.toml` puts
`variables` on the pytest path, so the test can import `quickstarts` directly. Placed
anywhere else it would silently never run in CI.

## Verification

Local, no credentials. Per quickstart, after `uv sync --all-packages` at the root:

- exactly one `.venv`, at the root; no member `.venv`
- `uv run bash -c 'command -v uvicorn'` resolves into that venv
- every app module imports, including client-only `requests` and subscriber-only
  `cloudevents`
- the regenerated root locks contain `requests` (invocation) and `cloudevents` (pubsub)

Then the `lint` job from `e2e-quickstarts.yml`, run locally from `tools/qs-tester`:

- `uv run robot --dryrun` over all four suites
- `uv run python docsync/check_readme_sync.py --all` → 16 of 16 in sync
- `uv run pytest docsync/tests -q`
- `uv run robot resources/tests/smoke.robot` (process teardown)

Requires credentials, and is the real gate: `workflow_dispatch` of `e2e-quickstarts.yml`
with `language: python`, `api: all`. Nothing local proves `diagrid dev run` behaves under
`uv run` for the three legs that do not already do it.

Baseline on this branch before any change: doc-sync 16/16, 6 unit tests pass, 4 smoke
tests pass.

## Risks

| Risk | Mitigation |
| --- | --- |
| Member-level `uv sync` re-prunes the shared venv | Docs never instruct it; CI steps corrected; invariant commented in both workspace roots. Residual: a user doing it by hand. |
| `uv run` re-resolves at startup, so a stale lock now errors instead of silently running | Locks committed; CI syncs first. Net safer, but a new failure mode to recognise. |
| Teardown gains a process layer (`uv run`) | SIGTERM propagation verified to reach the uvicorn child and release the port; `smoke.robot` covers it; `process.resource` comment corrected so the fallback is not mistaken for dead code. |
| `docs.diagrid.io` duplicates these READMEs | Outside this repository. Flagged for follow-up handoff, not fixed here. |
| Rebase conflict with the `--inexact` stopgap once merged | Expected. Resolve by taking this design's section 4 and `quickstarts.py`. |

## Sequencing

The `--inexact` stopgap on `fix/python-invocation-inexact-sync` merges first, to turn the
nightly green while this work is built and validated. It adds `--inexact` to both syncs in
`invocation/python/README.md` and `quickstarts.py`. This design supersedes it: the flag and
its explanatory note are deleted here.

## Out of scope

- `pubsub/python/publisher/main.py` catches `grpc.RpcError` without importing `grpc`, so a
  publish failure raises `NameError` instead of the intended HTTP 500. Real, unrelated,
  found in passing; separate fix.
- Non-Python quickstarts.
- The rejected alternative: putting `uv run uvicorn` in the `diagrid dev run` configs and
  keeping per-app locks. It also removes activation, but cannot deliver
  `uv run diagrid dev run` in the READMEs and leaves the two locks free to diverge.

## Done means

- All four Python READMEs' sections 4 and 5 are identical modulo the API name.
- No `uv venv` or shell activation remains in Python quickstart docs or in the harness.
- `ACTIVATE_VENV` and the `bash -c` activation wrapper are deleted, and
  `process.resource`'s fallback comment is corrected rather than left stale.
- All local gates green, including the new invariant test.
- A real `workflow_dispatch` run is green for `language: python` across all four APIs.

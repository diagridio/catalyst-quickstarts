# Design: realign the e2e harness and skill with the current agent quickstarts

Date: 2026-08-25

## Why

`main` has moved 27 commits since this branch forked at `beaa606`, and every quickstart
under `agents/` changed. Three facts the harness and the `add-quickstart-e2e-test` skill
encode verbatim are now wrong, and one of them is the command that creates the Catalyst
project.

This is drift of exactly the kind the harness exists to catch, and it did catch it. The
point of this document is what to change, not whether something is broken.

## How the findings below were verified

- `git diff beaa606..origin/main -- agents/` for the shape of the change.
- Every documented `diagrid` command extracted from all 15 READMEs under `agents/` on
  `origin/main`, not from the copies in this worktree.
- The branch's own `check_agent` run against `origin/main`'s `agents/langgraph/README.md`
  in a scratch tree. It returned four problems, two in each direction.
- `git merge-tree origin/main HEAD` for merge conflicts.
- `agents/langgraph/main.py` and the installed `diagrid` SDK for the health-probe route.

## Findings

### 1. The provisioning flag is gone (blocks merge)

`--enable-agent-infrastructure` no longer appears in any quickstart in the repository.
Agent projects are now created with the same managed-service flags the canonical APIs use:

```
diagrid project create <name> --enable-managed-workflow --deploy-managed-kv --deploy-managed-pubsub --wait --use
```

The three `spring-ai` quickstarts omit `--deploy-managed-pubsub` and create with
`--enable-managed-workflow --deploy-managed-kv --wait --use`.

This invalidates `variables/agents_langgraph.py`'s `SETUP`, the guiding-principle example
in `SKILL.md`, and several passages in `references/agent-quickstart.md`.

It also simplifies something. `ci/setup-project.sh` already creates projects with
`--deploy-managed-kv --deploy-managed-pubsub --enable-managed-workflow --wait --use`,
which is now character-for-character what an agent quickstart documents. The skill's
"README documents no provisioning, so ask which flags" decision path can therefore carry a
documented default instead of an open question, while still asking when a quickstart
deviates the way `spring-ai` does.

### 2. Agent names and appIDs are now semantic, one per quickstart

`agents/langgraph` documents `diagrid agent create schedule-planner --wait`, not
`langgraph-agent`, and its dev config's `appID` changed to match. The full set:

| Quickstart | Agent name |
|---|---|
| adk | entertainment-planner |
| claude-agents | photography-planner |
| crewai | venue-scout |
| dapr-agents/durable-agent | invitations-manager |
| deepagents | supervisor, researcher, analyst, transportation-planner |
| langgraph | schedule-planner |
| microsoft-dotnet | event-planner |
| openai-agents | catering-coordinator |
| pydantic-ai | decoration-planner |
| spring-ai/crash-recovery | spring-ai-crash-recovery |
| spring-ai/durable-memory | spring-ai-durable-memory |
| spring-ai/event-planner | spring-ai-event-planner |
| strands | budget-planner |

The names are coordinated: they are roles in one event-planning scenario, which is also why
`agents/dapr-agents/orchestrator` runs nine of them together.

### 3. The pub/sub component was renamed

`pubsub_name` changed from `agent-pubsub` to `pubsub` in every `main.py`, and the resource
files renamed with it. This does not affect the health probe: `runner.serve()` registers
`GET /dapr/subscribe` when both `pubsub_name` and `subscribe_topic` are passed, and both
still are. Only prose that names `agent-pubsub` is stale.

### 4. Quickstarts are now three directory levels deep

`agents/dapr-agents/{durable-agent,orchestrator}` and
`agents/spring-ai/{crash-recovery,durable-memory,event-planner}` put a README two levels
below `agents/`, so their suites would live at `agents/spring-ai/event-planner/tests/quickstart.robot`.

What still works: `suites.quickstart_dir()` and `check_agent()` both derive the quickstart
directory as the suite's grandparent, which is correct at any depth.

What breaks: the workflow's `pull_request.paths` entry `'*/*/tests/quickstart.robot'` matches
three path segments and will not match four. A PR touching only a `spring-ai` suite would run
no checks at all.

### 5. There are now two `dapr-agents` trees

Top-level `dapr-agents/` (43 files) and `agents/dapr-agents/` (22 files) both exist on `main`.
The skill's references name the top-level one. Which is canonical is a repository question,
not a harness question, and it is listed under Open questions below.

### 6. The pinned CLI version moved

`main` pins `DIAGRID_CLI_VERSION: 'v1.67.0'`; this branch still has `v1.36.0`, and
`tools/qs-tester/README.md` documents the v1.36.0 install line. `preflight.sh` reads the pin
out of the workflow rather than hard-coding it, so it needs no change, but the README line does.

### 7. Multi-agent and multi-config quickstarts are now normal

`agents/deepagents` documents four `agent create` commands and three dev configs
(`dev-python-deepagents.yaml`, `dev-crash-test.yaml`, `dev-subagent-workflows.yaml`).
`agents/dapr-agents/orchestrator` runs nine apps on ports 8001 through 8009 and documents no
`project create` at all, only a `dev run`.

The data-module contract already expresses all of this: `SETUP` is an ordered tuple,
`READY_MARKERS` and `HEALTH_PROBES` are tuples, and `UNCOVERED` absorbs the dev configs a
suite does not run. What is stale is the worked examples in the references, which predate these
shapes.

### 8. Readiness markers and ports are confirmed non-uniform

`agents/microsoft-dotnet` documents waiting for `Established gRPC bidirectional stream with
Dapr sidecar`, not a Uvicorn line. `spring-ai` is Java on 8080. Documented trigger ports now
span 5050, 8001 through 8010, and 8080. The references already say markers are a property of
the framework rather than the language; these are the concrete examples to cite.

### 9. What did not change

- `mcp-auth/python` is untouched since the fork. Its three `--skip-*` flags and its two
  documented calls both returning HTTP 200 are still accurate in the references.
- `agents/langgraph`'s trigger is still `POST http://localhost:8005/agent/run` with the same
  payload, and its readiness wording is still `Uvicorn running on`.
- `agents/langgraph` still documents no cleanup command, so `TEARDOWN = ()` remains correct.
- Both sanctioned exceptions still hold: the documented bare `diagrid login`, and the
  documented project name.

### 10. The open PR will fail its own lint job

Running this branch's `check_agent` against `main`'s current langgraph README returns four
problems: two commands the harness runs that the README no longer documents, and two commands
the README documents that nothing accounts for. `git merge-tree` also reports three conflicts,
in `.github/workflows/e2e-quickstarts.yml`, `tools/qs-tester/README.md`, and
`tools/qs-tester/resources/catalyst.resource`.

This is the doc-sync guard working as designed. Nothing shipped silently wrong, and the fix is
mechanical.

## What must change

| File | Change |
|---|---|
| `tools/qs-tester/variables/agents_langgraph.py` | `SETUP` to the managed-service flags and `diagrid agent create schedule-planner --wait`. Re-check `UNCOVERED` against the current crash-test commands. |
| `.claude/skills/add-quickstart-e2e-test/SKILL.md` | The guiding-principle example, which still shows `--enable-agent-infrastructure` and `langgraph-agent`. |
| `references/agent-quickstart.md` | The same flag and name in every worked example; the `agent-pubsub` references; add the `spring-ai` flag variant and the three-level path shape; refresh the multi-app example against `orchestrator`'s nine apps. |
| `references/harness-keywords.md` | Only if a signature moved; none did. Verify rather than assume. |
| `.github/workflows/e2e-quickstarts.yml` | Add `'*/*/*/tests/quickstart.robot'` to `pull_request.paths`. Resolve the merge conflict against main's version, keeping main's CLI pin. |
| `tools/qs-tester/README.md` | The v1.36.0 install line; resolve the merge conflict. |
| `tools/qs-tester/resources/catalyst.resource` | Resolve the merge conflict (main changed this file too). |
| `.claude/skills/add-quickstart-e2e-test/scripts/preflight.sh` | No change. It parses the pin from the workflow. Confirm that still holds after the merge. |

## Open questions

1. **Which `dapr-agents` tree is canonical**, the top-level one or `agents/dapr-agents/`?
   The references should name one and only one.
2. **Should coverage expand beyond langgraph in this cycle?** Nine of the agent quickstarts now
   share one shape (python, `runner.serve()`, `POST /agent/run`, a Uvicorn marker), so the
   second and third suites would be cheap. The counter-argument is that none of them can be
   proven without a model provider key, so they would all land `nightly: False`.
3. **How should `spring-ai` be covered**, given it is one directory with three independent
   quickstarts, each with its own project name and its own flags?
4. **Should the skill gain an explicit "re-read the flags from the README you are testing"
   step?** This drift was a flag change, and a skill that treats provisioning flags as
   quickstart-specific data rather than as a constant would have been immune to it.

## Verification

The same credential-free gate as before, all of which must be green:

- `uv run python ci/list-suites.py --validate`
- `uv run pytest -q`
- `uv run python docsync/check_readme_sync.py --all`, which must report zero problems for every
  registered agent suite against the current READMEs
- the manifest-driven dryrun
- `smoke.robot` plus `keywords.robot`
- `scripts/verify-static.sh`

Plus one new check that would have caught this class of drift earlier: after resolving the
merge, confirm doc-sync passes against `origin/main`'s READMEs rather than the branch's copies.

## Out of scope

- The langgraph live run and mutation check. Still blocked on a model provider key, unchanged
  by any of this.
- Deduplicating the two `dapr-agents` trees, which is a repository decision.
- Anything under `mcp-auth/`, which has not changed.

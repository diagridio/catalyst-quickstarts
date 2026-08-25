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

### 5. There are now two `dapr-agents` trees, and only one is canonical

Top-level `dapr-agents/` (43 files) and `agents/dapr-agents/` (22 files) both exist on `main`.
The root README links only to `agents/dapr-agents/`, and both trees were last touched by the
same commit, "Restore Dapr component files since they are used in Dapr university tracks".

Confirmed with the project owner: **`agents/dapr-agents/` is canonical; the top-level tree is
retained only for the Dapr University component files.**

Two of the skill's worked examples point at the legacy tree, and one of them at a quickstart
that exists nowhere else:

- `dapr-agents/durable-agent`, cited as the "documents no project create" example, becomes
  `agents/dapr-agents/durable-agent`. Note that this quickstart now *does* document a
  `project create`, so the example needs a different subject: the no-provisioning case is now
  `agents/dapr-agents/orchestrator`.
- `dapr-agents/multi-agent-workflow`, cited as the multi-app example, has no counterpart under
  `agents/`. Replace it with `agents/dapr-agents/orchestrator`, which runs nine apps on ports
  8001 through 8009 and is a stronger example anyway.

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
| Merge `origin/main` first | Three conflicts to resolve before anything else: `.github/workflows/e2e-quickstarts.yml`, `tools/qs-tester/README.md`, `tools/qs-tester/resources/catalyst.resource`. Keep main's CLI pin (`v1.67.0`). |
| `tools/qs-tester/variables/agents_langgraph.py` | `SETUP` to the managed-service flags and `diagrid agent create schedule-planner --wait`. Re-check `UNCOVERED` against the current crash-test commands. |
| `tools/qs-tester/variables/agents_microsoft_dotnet.py` | New. `runtime: dotnet`, port 5050, `POST /run`, the gRPC readiness marker, and a non-empty `TEARDOWN` from its documented `project delete`. |
| `tools/qs-tester/variables/agents_spring_ai_event_planner.py` | New. `runtime: java`, port 8080, `POST /run`, the reduced flag set, and a documented `project delete`. |
| `agents/microsoft-dotnet/tests/quickstart.robot` | New suite. |
| `agents/spring-ai/event-planner/tests/quickstart.robot` | New suite, and the first at three levels deep. |
| `tools/qs-tester/variables/suites.py` | Three agent rows with compound path-derived names, all `nightly: False`. |
| `docsync/check_skill_docs.py` + `docsync/tests/test_skill_docs.py` | New checker and its tests, per the section above. |
| `.claude/skills/add-quickstart-e2e-test/SKILL.md` | The guiding-principle example, which still shows `--enable-agent-infrastructure` and `langgraph-agent`; plus the phase-2 sentence about reading flags from the README under test. |
| `references/agent-quickstart.md` | The same flag and name in every worked example; the `agent-pubsub` references; add the spring-ai flag variant and the three-level path shape; move the no-provisioning example to `agents/dapr-agents/orchestrator` and the multi-app example off the legacy `multi-agent-workflow`. |
| `references/harness-keywords.md` | Only if a signature moved; none did. Verify rather than assume. |
| `.github/workflows/e2e-quickstarts.yml` | Add `'*/*/*/tests/quickstart.robot'` to `pull_request.paths`, and a step running the new skill-docs checker in `lint`. |
| `tools/qs-tester/README.md` | The v1.36.0 install line; document the compound naming convention and the new checker. |
| `scripts/verify-static.sh` | Add the skill-docs checker, keeping the order matching CI's `lint` job. |
| `scripts/preflight.sh` | No change. It parses the pin from the workflow. Confirm that still holds after the merge. |

## Keeping the skill's own documentation true
name-1234567890123456789012345678901234567890
name-12345678901234567890123456789012345678901234567890

The harness was already immune to this drift. `SETUP` is per-quickstart data transcribed from a
README, and doc-sync compares the two in both directions, which is how the four problems in
finding 10 surfaced. What rotted is the skill's *teaching material*: static examples in
`SKILL.md` and `references/agent-quickstart.md` that show `--enable-agent-infrastructure` and
`langgraph-agent` as though they were constants.

Those examples have two failure modes. They become false, and an agent may copy them instead of
reading the README it is actually testing. The second is worse, because it produces a suite that
fails doc-sync for a reason the agent just introduced.

So the same discipline the harness applies to suites now applies to the skill's own docs: a
claim that cannot be traced to a source does not survive CI.

### `docsync/check_skill_docs.py`

A fourth checker beside the three that exist, run in CI's `lint` job and by
`scripts/verify-static.sh`.

**What it checks.** Every fenced block in `SKILL.md` and `references/*.md`, and within each
block, the lines beginning `diagrid`. Each must appear verbatim in at least one quickstart
README after the project name is masked. Nothing else in those files is inspected.

**Corpus.** Every `README.md` under `agents/`, `mcp-auth/`, and the canonical
`<api>/<language>/` directories. The legacy top-level `dapr-agents/` tree is excluded, since it
is no longer a place a reader should be sent.

**Name masking, and what is deliberately not masked.** Three spellings of the project name
collapse to one token: `{project}`, the positional name in `project create|delete <name>`, and
`--project <name>`. Agent names are *not* masked, so `diagrid agent create langgraph-agent
--wait` fails once no README documents it. That is the second half of this drift, and it should
be caught rather than normalised away.

**Reuse.** `all_bash_lines()` already joins backslash continuations and normalises whitespace;
both sides of the comparison go through it. `normalise_run_command()` already handles
`--project`.

**Escape hatch.** `<!-- illustrative: reason -->` immediately above a block exempts it. A
missing or empty reason is itself a failure, so the hatch cannot decay into a silent bypass.
This mirrors `UNCOVERED`'s (command, reason) shape, which already forces the same decision for
suites.

**Failure output** names the file and line, the offending command, and the closest documented
line, so the fix is visible without hunting.

**Tests** (`docsync/tests/test_skill_docs.py`): a documented command passes; a command carrying
`--enable-agent-infrastructure` fails against the current READMEs, as a regression test for this
exact drift; a tagged block with a reason is skipped; a tagged block without one fails; all
three project-name spellings match; an agent name no README documents fails.

**One complementary sentence in SKILL.md's phase 2**, because a checker cannot stop an agent
copying a stale example into a new suite: read the flags from the README you are testing, since
these examples are verified but they are still examples.

**What this does not do.** It verifies commands, not prose. The invented `nightly` consumer that
a review caught in `canonical-api.md` would still pass, because that class of error needs a
reader rather than a parser. It also only detects drift once the READMEs and the skill are in the
same tree, which is the guarantee doc-sync already gives, no more.

## Decisions

Settled with the project owner:

1. **`agents/dapr-agents/` is canonical.** Top-level `dapr-agents/` is retained only for Dapr
   University component files, and the skill's examples move off it (see finding 5).
2. **Three suites in this cycle**, chosen for distinct shape rather than count:
   `agents/langgraph` (realigned), `agents/microsoft-dotnet`, `agents/spring-ai/event-planner`.
   Rationale in the next section.
3. **Compound path-derived manifest names**: the path below `agents/` with slashes replaced by
   dashes. So `langgraph`, `microsoft-dotnet`, `spring-ai-event-planner`,
   `dapr-agents-orchestrator`. The `name` keys the ephemeral project, the CI artifact and the
   failure summary, so it must be unique forever; deriving it from the path makes collisions
   impossible by construction and a leaked project self-describing in the Catalyst console.
4. **Machine-check the skill's examples** rather than relying on an instruction to re-read them,
   per the section above.

One sub-question stays open and becomes a pre-flight check rather than an assumption:
`qs-ci-agents-spring-ai-event-planner-<run-id>` is roughly 48 characters, and Catalyst's
project-name length limit is unknown. Verify it before the spring-ai suite is written. If the
limit is tighter, drop the `agents-` infix from the leg id, which is the smallest change that
preserves uniqueness.

### Why these three suites

`agents/langgraph` alone would leave the `dotnet` and `java` CI setup steps unexercised and six
contract features implemented but used by no real suite. These three cover all but two of them:

| Feature | Exercised by |
|---|---|
| `runtime: dotnet` CI setup step | microsoft-dotnet |
| `runtime: java` CI setup step | spring-ai/event-planner |
| Non-empty `TEARDOWN` (documented `project delete`) | microsoft-dotnet, spring-ai/event-planner |
| A non-Uvicorn readiness marker | microsoft-dotnet (`Established gRPC bidirectional stream with Dapr sidecar`) |
| A three-level suite path, and the new `paths` glob | spring-ai/event-planner |
| The reduced flag set (no `--deploy-managed-pubsub`) | spring-ai/event-planner |

Two features still have no real user, and the spec records that rather than implying otherwise:
a request's `commands` key (needs `mcp-auth`) and several `READY_MARKERS` for a multi-app
quickstart (needs `agents/dapr-agents/orchestrator`). Both remain unit-tested only.

All three suites land `nightly: False`, because none can be proven without a model provider key.
That is not a new gap: it is the same gap langgraph already has, recorded in the harness README's
Limitations.

## Verification

The same credential-free gate as before, all of which must be green:

- `uv run python ci/list-suites.py --validate`, now with three agent rows
- `uv run pytest -q`
- `uv run python docsync/check_readme_sync.py --all`, which must report zero problems for all
  three agent suites against the current READMEs
- `uv run python docsync/check_skill_docs.py`, the new checker
- the manifest-driven dryrun, which should resolve 20 tests: 16 canonical plus three agent suites
- `smoke.robot` plus `keywords.robot`
- `scripts/verify-static.sh`

Three checks specific to this work, because each closes a gap that let something ship unverified:

1. After resolving the merge, run doc-sync against `origin/main`'s READMEs rather than the
   branch's copies. Running it against stale copies is what would have hidden this drift.
2. Confirm the new `'*/*/*/tests/quickstart.robot'` glob actually matches the spring-ai suite.
   A path filter with nothing behind it is the kind of fix that looks done and is not, and until
   this cycle there was no three-level suite to match.
3. Confirm the skill-docs checker fails when it should: temporarily reintroduce
   `--enable-agent-infrastructure` into a reference file and require a non-zero exit. A checker
   nobody has seen fail is worth as little as an assertion nobody has seen fail.

Then verify the Catalyst project-name length limit before writing the spring-ai suite, per the
open sub-question in Decisions.

## Out of scope

- The live runs and mutation checks for all three suites. Still blocked on a model provider key,
  unchanged by any of this. All three land `nightly: False`.
- The remaining eleven agent quickstarts. They keep no suite and therefore no drift detection
  beyond the skill-docs checker, which validates the skill's examples against their READMEs but
  holds those READMEs to nothing. Adding them is what the skill is for, and the first real test
  of it should be a human asking for one.
- Deleting the legacy top-level `dapr-agents/` tree. It is retained deliberately for Dapr
  University, so the only change here is that the skill stops pointing at it.
- Anything under `mcp-auth/`, which has not changed since the fork. Its three `--skip-*` flags
  and its two documented calls both returning HTTP 200 are still accurate in the references.
- Why CI has never run on PR #293. Six minutes of polling produced zero check-runs even though
  the workflow is active and runs nightly on `main`. That is a real problem, because the `lint`
  job is what would have surfaced this drift at review time, but it is a CI configuration
  question rather than part of this realignment.

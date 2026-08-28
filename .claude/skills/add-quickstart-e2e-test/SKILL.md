---
name: add-quickstart-e2e-test
description: Add a Robot Framework end-to-end test for a quickstart in this repository and wire it into the nightly GitHub Actions workflow. Use this whenever someone wants a quickstart covered by tests or CI, in any phrasing, including "add an e2e test for the langgraph quickstart", "the microsoft-dotnet quickstart has no CI coverage", "write a Robot test for mcp-auth", "we just added a Go state quickstart, test it", or just "is this quickstart tested?" followed by "fix that". Handles both conventions in this repo: the canonical (api x language) quickstarts and the flat agent-family ones under agents/, dapr-agents/ and mcp-auth/.
---

# Add a quickstart end-to-end test

## What you are building

A suite that runs the commands a quickstart's README documents and asserts what
that README promises, so drift between the docs, the code and Catalyst is caught
automatically. The harness lives in `tools/qs-tester`; read its README first if
you have not.

## The rule that decides every judgement call

If a README documents a command, run that command verbatim, substituting only the
project name. Where a README documents nothing, the harness supplies its own
command and labels it infrastructure.

Two exceptions, both already implemented, neither to be re-litigated:

1. `diagrid login` becomes `diagrid login --api-key "$DIAGRID_API_KEY"` via
   `ci/login.sh`. The documented bare form blocks on a browser prompt.
2. The documented project name becomes `qs-ci-<leg>-<run-id>` via
   `ci/project-name.sh`. The `qs-ci-` prefix is what `ci/reap-orphans.sh`
   collects by; a name without it leaks forever.

Never invent an expected value. If the README does not document it and it cannot
be read out of the repo, assert only what is documented and leave a comment
naming the gap. An assertion nobody can trace to a source is worse than no
assertion, because it reads as coverage.

## Phase 0: preflight, before writing anything

Run `scripts/preflight.sh <family>`. It checks the credentials, CLI version and
harness sync you need to finish. A missing key found now costs seconds; found
after you have written four files, it costs the whole run.

If something is missing, say so immediately and ask whether to continue writing
without being able to verify. Do not quietly proceed to a state you cannot prove.

## Phase 1: classify

Which convention is this quickstart?

- Path is `workflow/`, `state/`, `pubsub/` or `invocation/`, README has numbered
  sections (`## 4. Install`, `## 5. Run`, `## 6.`): **canonical**. Read
  `references/canonical-api.md`.
- Path is `agents/`, `dapr-agents/`, `mcp-auth/` or similar, README has named
  sections: **agent-family**. Read `references/agent-quickstart.md`.

Read one reference, not both. They share little and the differences are what
matter.

## Phase 2: extract the facts

From the README first, in this order: install, provisioning, run, readiness
marker, trigger request, expected response, log markers, cleanup, required
secrets.

Where the README is silent about something the test needs, read the dev config
YAML (`appPort`, `appID`) or the app source, and record in a comment where the
value came from. Where the README is silent about something the test would only
guess at, such as a response body shape, leave it unasserted and say why in a
comment.

Read the provisioning flags out of the README you are testing. The examples
here are checked against real READMEs, but they are still examples: `spring-ai`
omits `--deploy-managed-pubsub`, and the flags changed once already.

List every documented command you are NOT going to run, with its reason. That
list becomes `UNCOVERED`, and doc-sync fails if a documented command is in
neither `UNCOVERED` nor the suite. Crash-recovery flows that need source edits,
and endpoints no README documents, belong in `UNCOVERED`.

### When the README documents no project creation

Some quickstarts need a project but never say how to make one.
`agents/dapr-agents/orchestrator` is the clearest case: its seven prerequisites
are the CLI, Python, uv, three model API keys and "all 8 specialist agents
running" — no Catalyst project among them — and its documented flow is `cd
dapr-agents/orchestrator` and `uv sync`, then `diagrid login` and `uv run
diagrid dev run -f dev-multi-agent-orchestration.yaml`. No `project create`
anywhere, and no `--project` flag on `dev run` either. Transcribe the install
steps like any other documented command; it is the provisioning that is absent.
Under the guiding principle, provisioning is then infrastructure, and
`ci/setup-project.sh` owns it, exactly as for the canonical APIs.

That script's flags were chosen for the canonical APIs, though
(`--deploy-managed-kv --deploy-managed-pubsub --enable-managed-workflow`), and
the flags an agent quickstart's own README documents are not a constant either:
`agents/langgraph` and `agents/microsoft-dotnet` both document
`--enable-managed-workflow --deploy-managed-kv --deploy-managed-pubsub`, while
`agents/spring-ai/event-planner` documents `--enable-managed-workflow
--deploy-managed-kv` only, with no `--deploy-managed-pubsub`. Deciding which
set an undocumented case like orchestrator's nine apps actually needs, from
nothing, is guessing, which is the one thing this skill must not do.

So: leave `SETUP` empty, note in the data module that provisioning is
undocumented, and **ask** which flags the project needs before running anything.
Say what you know (the quickstart's `dev run` passes no `--project` at all,
nothing documents creating one, and the flags other agent quickstarts document
are these) and what you need decided. A wrong flag here either fails the whole
leg or, worse, provisions something that works by accident and hides a
documentation gap readers will hit.

## Phase 3: write

Follow the files that already exist rather than inventing a layout:
`tools/qs-tester/variables/agents_langgraph.py` and
`agents/langgraph/tests/quickstart.robot` are the agent-family template;
`variables/quickstarts.py` and `state/tests/quickstart.robot` are the canonical
one. `references/harness-keywords.md` lists the keywords available with their
signatures, so you do not write a keyword that already exists.

Conventions that matter here: a `*** Comments ***` header naming which README
sections the suite mirrors, and a comment on every truncation, divergence or
value that came from somewhere other than the README. The next person to read
this file will be debugging a nightly failure at speed.

Register the suite in `tools/qs-tester/variables/suites.py`. For a genuinely new
runtime, also add the setup step to the `e2e-agents` job; otherwise touch no YAML.

## Phase 4: static verification

Run `scripts/verify-static.sh`. It runs the manifest validation, the dryrun,
doc-sync and the unit tests, which is exactly what CI's lint job runs. Loop until
green.

When doc-sync disagrees with you, the README is right and your data module is
wrong, unless you have positive evidence the README itself drifted. Say so
explicitly if you conclude that.

## Phase 5: live verification

The two families need different procedures, because they get their project from
different places.

**Agent-family:** run `scripts/verify-live.sh <suite-path>`. It reads the row's
leg from the manifest (`ci/list-suites.py --row`, the same field the nightly
matrix carries), computes two ephemeral project names from it, logs in, runs
the suite, runs the mutation check against the *second* project, and tears
both down on every exit path. Two projects, not one: an agent-family suite
provisions itself in `SETUP` from its README's documented `project
create`/`agent create`, and `Run Documented Commands` stops at the first
non-zero exit, so a mutated run against the already-provisioned first project
dies in `SETUP` before it ever reaches the mutated assertion.

**Canonical:** the script refuses these, and prints the procedure to run instead
— it is documented in `tools/qs-tester/README.md` under "Create a project and run
a suite". The difference is that `ci/setup-project.sh` provisions the project
from outside the suite, and all four language tests share appIDs and ports
5001/5002, so you run one language per project with `--include <language>`. The
mutation check is the same idea with a different target: the canonical suites
read their expected bodies from the `Variables` import too
(`${STATE_STORE_BODY}` and friends), so a generated `--variablefile` can break
one, and `ci/check_mutation.py` confirms which keyword failed.

A green run alone is not enough. The mutation check re-runs the suite with one
assertion deliberately broken and requires a failure. Two ways that check can lie
to you, both of which the tooling now catches — do not talk yourself past either:

- If the mutated run **passes**, the assertion is vacuous, which is worse than
  having no assertion: it makes a broken quickstart ship green.
- If the mutated run **fails for another reason** — a project that already
  exists, a build error, a missing key — that failure would have happened without
  the mutation and proves nothing. `ci/check_mutation.py` parses the mutated
  run's `output.xml` and requires the *named keyword* to have status FAIL
  **inside a test that also FAILed**, with the mutation's sentinel in its
  message; a keyword recorded `NOT RUN` fails the check, and so does a keyword
  that FAILed but got caught and swallowed by something like `Run Keyword And
  Return Status`, leaving the enclosing test PASSing (`resources/tests/
  keywords.robot` does exactly this on purpose, to prove the checker rejects
  it). Because a clean verdict already requires the enclosing test to have
  failed, it implies robot's own exit code was non-zero — take the checker's
  verdict; there is no separate exit-code check to add on top.

## Phase 6: report

Exactly two shapes. There is no "probably fine".

**VERIFIED.** The live run passed and the mutation check failed as expected.
State which suite, which assertions it makes, which variable you mutated, and
what remains unproven (undocumented response shapes, other assertions no
mutation check covered).

**BLOCKED.** You could not complete the live run. State what is missing, what
you wrote anyway, what static checks passed, and the exact commands that finish
the job.

Reporting BLOCKED honestly is a success. Reporting VERIFIED without a green live
run and a failed mutation run is the one outcome that damages the harness,
because everything downstream trusts that claim.

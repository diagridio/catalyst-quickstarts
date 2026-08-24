# qs-tester

End-to-end tests for the `workflow`, `state`, `pubsub`, and `invocation` quickstarts,
built on [Robot Framework](https://robotframework.org/). The tests run the *actual*
commands each quickstart's README documents and assert the responses and log output
that README promises, so drift between the docs, the code, and Catalyst is caught
automatically.

## Layout

- `resources/process.resource` — background process lifecycle and PID-tree teardown.
  `Stop Process Tree` is not idempotent: calling it against a process that has
  already exited raises (`PermissionError`/`EPERM` on Darwin, surfacing through
  Robot's `Process` library) instead of doing nothing. This was discovered twice
  during implementation, which is why every call site wraps it in
  `Run Keyword And Ignore Error` — see `Stop Quickstart` in `catalyst.resource`
  and `Clean Up Quickstart` in `agents/langgraph/tests/quickstart.robot`. Do the
  same in any new teardown keyword that calls it directly.
- `resources/catalyst.resource` — `diagrid dev run` launch, stop, readiness markers.
- `resources/quickstart.resource` — build, health polling, HTTP assertions.
- `resources/tests/smoke.robot` — tests the process-teardown keywords themselves.
  Needs no credentials and runs in under a minute. CI's `lint` job runs it on
  every PR, together with `resources/tests/keywords.robot`, so a change to
  `process.resource` is guarded rather than relying on someone remembering to run
  it locally.
- `resources/tests/keywords.robot` — tests the keywords the agent-family suites
  depend on (`Require Env Var`, `Run Documented Commands`,
  `Wait Until Ready Marker`, `POST And Expect Field`, the health probe), against
  `resources/tests/echo_server.py` on localhost. No Catalyst project, no
  credentials, no network. Also in the `lint` job.
- `variables/quickstarts.py` — the per-(API, language) table. **Everything in it is
  transcribed from a README.** Change a README, change this file.
- `docsync/check_readme_sync.py` — asserts the two stay in agreement.
- `ci/` — Catalyst project lifecycle scripts.
- `variables/suites.py` — the registry of every suite. The lint dryrun, the CI
  agents matrix and doc-sync all read it, so registering a suite is one row here
  rather than three edits in the workflow.
- `variables/agents_<name>.py` — one per agent-family quickstart, holding that
  quickstart's documented command sequence verbatim.
- `ci/list-suites.py` — reads the manifest for CI (`--paths`, `--matrix agent`,
  `--validate`, `--row <suite>`).
- `ci/check_mutation.py` — the mutation check's verdict: did the mutated run fail
  on the assertion the mutation broke, or on something else? See "Running an
  agent-family suite locally" below.
- `ci/project-name.sh`, `ci/login.sh` — the ephemeral name, and the API-key login.

Each suite lives next to the quickstarts it tests: `state/tests/quickstart.robot`,
`pubsub/tests/quickstart.robot`, and so on. Each canonical suite has four tests
tagged `csharp`, `java`, `javascript`, `python`. Agent-family suites (see "Two
kinds of quickstart" below) have exactly one test each, at `<family>/<name>/tests/quickstart.robot`.

## Running locally

`robot`, `rebot`, `uv` and the doc-sync checker all run from `tools/qs-tester/`, so
suite paths are relative to it (`../../state/tests/quickstart.robot`).

### One-time setup

```bash
export DIAGRID_API_KEY=...     # a Catalyst API key
(cd tools/qs-tester && uv sync)
```

You'll also need the `diagrid` CLI on your `PATH` to create/delete a project (see
below); CI installs a pinned version — see "CLI version" below if you want the same
one locally.

### Create a project and run a suite

Every suite needs a Catalyst project. `ci/setup-project.sh` creates a throwaway one
and prints its name:

```bash
export LANG_ID=python
eval "$(bash tools/qs-tester/ci/setup-project.sh | grep '^PROJECT=')"

cd tools/qs-tester
uv run robot --include python --variable PROJECT:$PROJECT \
  --outputdir results/state ../../state/tests/quickstart.robot
```

Delete it when you are done — these are not free:

```bash
bash tools/qs-tester/ci/teardown-project.sh "$PROJECT"
```

The only thing the harness ever rewrites in a documented run command is
`--project`: every quickstart README says `--project <api>-quickstart`, and
`Start Quickstart` substitutes the ephemeral project name for it. Everything
else in the command — the file, the flags, `mvn spring-boot:run`, the `uv run`
prefix — runs exactly as the README shows it.

### Selecting languages and APIs

Each suite has four tests tagged by language. Filter with `--include` / `--exclude`
(repeatable, `--include` ORs):

```bash
# one language, one API
uv run robot --include python --variable PROJECT:$PROJECT \
  ../../state/tests/quickstart.robot

# two languages
uv run robot --include csharp --include java --variable PROJECT:$PROJECT \
  ../../pubsub/tests/quickstart.robot

# all four APIs, one language, one combined report
uv run robot --include python --variable PROJECT:$PROJECT --name "Quickstarts (python)" \
  ../../workflow/tests/quickstart.robot ../../state/tests/quickstart.robot \
  ../../pubsub/tests/quickstart.robot ../../invocation/tests/quickstart.robot
```

Only one language at a time per project: all four languages of a given quickstart
share appIDs (`order-app`, `publisher`/`subscriber`, `client`/`server`,
`order-workflow`) and ports 5001/5002, so two languages cannot run concurrently in
one project or on one machine.

### Two kinds of quickstart

The canonical APIs (`workflow`, `state`, `pubsub`, `invocation`) are an
(api × language) matrix: one suite per API, four language-tagged tests, all data
in `variables/quickstarts.py`.

Agent-family quickstarts (`agents/*`, `dapr-agents/*`, `mcp-auth/*`) are a flat
list. Each has exactly one language, its own suite at
`<family>/<name>/tests/quickstart.robot`, and its own data module. Three things
differ and are worth knowing before you touch one:

1. **They provision themselves.** Their READMEs document `diagrid project create`
   (with `--enable-agent-infrastructure` for `agents/*`), `agent create` and
   sometimes `app create` and `apply -f`, so the suite runs those documented
   commands through `Run Documented Commands`. `ci/setup-project.sh` is for the
   canonical suites, whose READMEs document no provisioning at all.
2. **The `dev run` command can be bare.** `agents/*` documents
   `project create ... --use` followed by a `dev run` with no `--project`. The
   suite reproduces that exactly, so a regression in `--use` fails here.
3. **Assertions are structural.** Responses contain model output, so the suites
   assert the documented status code, a named field being present and non-empty
   where a response shape is known, and a log marker showing the expected tool
   ran.

Nightly membership is per suite (`nightly` in the manifest), and CI reads it
only for agent-family rows — canonical scheduling stays the business of the
`e2e` job's own hand-written language matrix. Each agent leg costs a project
with agent infrastructure plus real model tokens, so suites left at
`nightly: False` run only on `workflow_dispatch`.

### Running an agent-family suite locally

Every suite's log-marker and readiness waits read from two variables defined in
`resources/process.resource`: `${MARKER_TIMEOUT}` (default `60s`) and
`${READINESS_TIMEOUT}` (default `180s`) — the values these waits used before
they were parameterised. Both are overridable with `robot --variable`, which is
what lets the mutation check below give up in seconds instead of waiting out a
three-minute readiness timeout.

```bash
export DIAGRID_API_KEY=...
export OPENAI_API_KEY=...           # whichever secrets the manifest row lists
eval "$(bash tools/qs-tester/ci/project-name.sh agents-langgraph | grep '^PROJECT=')"
bash tools/qs-tester/ci/login.sh
cd tools/qs-tester
uv run robot --variable PROJECT:$PROJECT --outputdir results/agents-langgraph \
  ../../agents/langgraph/tests/quickstart.robot
bash ci/teardown-project.sh "$PROJECT"
```

`agents/langgraph/README.md` documents no cleanup step, so `TEARDOWN` in its data
module is empty and `ci/teardown-project.sh` is what actually deletes the
project here — not a safety net finding nothing already gone, which is what it
would be for an agent quickstart whose README documents its own
`diagrid project delete` (`agents/microsoft-dotnet` does). It stays in the
sequence either way, because for a quickstart that does self-delete it is the
net for a suite that died before reaching its own teardown.

To prove an assertion is not vacuous, re-run with the assertion broken and
require a failure. Two things make this check mean something.

**A second, empty project.** Not the one the green run just used. An
agent-family suite provisions itself inside `SETUP` from its README's documented
`project create` and `agent create`, and `Run Documented Commands` stops at the
first non-zero exit — so against the first project the `project create` fails,
the suite dies in `SETUP`, and the mutated assertion is never reached. That run
exits non-zero without proving anything.

**A verdict on which keyword failed**, not on robot's exit code. Any failure
makes robot exit non-zero; only a FAIL on the mutated assertion is evidence.
`ci/check_mutation.py` reads the mutated run's `output.xml`, requires a keyword
with the given name to have status FAIL, and (given a third argument) requires
the mutation's sentinel to appear in its failure message. A keyword the run never
reached is recorded `NOT RUN` and fails this check.

The override goes through a generated variable file rather than `--variable`,
because `--variable` can only set scalars and the interesting targets
(`READY_MARKERS`, `REQUESTS`) are tuples:

```bash
eval "$(bash ci/project-name.sh agents-langgraph-mut | grep '^PROJECT=')"
MUT_PROJECT="$PROJECT"

mkdir -p results/mutated
cat > results/mutated/mutate.py <<'EOF'
READY_MARKERS = ("__mutation_check__",)
EOF
uv run robot --variable PROJECT:$MUT_PROJECT \
  --variablefile results/mutated/mutate.py \
  --variable READINESS_TIMEOUT:20s --variable MARKER_TIMEOUT:20s \
  --outputdir results/mutated ../../agents/langgraph/tests/quickstart.robot

# The verdict. Exits non-zero unless the mutated assertion is what failed.
uv run python ci/check_mutation.py results/mutated/output.xml \
  "Wait Until Ready Marker" "__mutation_check__"

bash ci/teardown-project.sh "$MUT_PROJECT"
```

A PASS from the mutated robot run means the assertion never fails and is
worthless. A non-zero exit that `check_mutation.py` rejects means the run broke
somewhere else and the assertion is still unproven.

`.claude/skills/add-quickstart-e2e-test/scripts/verify-live.sh` runs this whole
sequence — green run, mutated run against a second project, verdict, teardown of
both on every exit path including SIGINT — for agent-family suites. It refuses
canonical suites, which need `ci/setup-project.sh` and one language at a time
(see "Create a project and run a suite" above); for those, run the two robot
invocations by hand with `--include <language>` and finish with the same
`check_mutation.py` call, naming the keyword your mutation targets
(`POST And Expect`, say, if you broke `STATE_STORE_BODY`).

### Checks that need no Catalyst project

```bash
cd tools/qs-tester

# resolve syntax, keywords and variables without running anything — every suite
# in the manifest, canonical and agent-family alike
uv run robot --dryrun --variable PROJECT:dryrun --outputdir results/dryrun \
  $(uv run python ci/list-suites.py --paths)

# assert every registered suite's manifest row is well-formed
uv run python ci/list-suites.py --validate

# assert the READMEs and the harness still agree, canonical and agent-family alike
uv run python docsync/check_readme_sync.py --all

# unit-test the doc-sync checker and the manifest itself
uv run pytest -q

# process-lifecycle and harness keywords, no Catalyst project or credentials needed
uv run robot resources/tests/smoke.robot resources/tests/keywords.robot
```

`ci/list-suites.py --paths` reads `variables/suites.py`, so this is the same
command the CI `lint` job runs, and registering a new suite there is what puts it
under this check — no separate edit here. Filtering to only the four canonical
suites, for a quicker local loop, means falling back to the glob
(`../../*/tests/quickstart.robot`): the single `*` matches one path segment, so
it resolves to exactly `workflow`, `state`, `pubsub`, `invocation` and does not
reach agent-family suites, which live two segments deep
(`agents/langgraph/tests/quickstart.robot`).

### CLI version

The `diagrid` CLI installer (`https://downloads.diagrid.io/cli/install.sh`) does
**not** take the version as a positional argument. It reads the `RELEASE_VERSION`
environment variable and requires the leading `v` (its GCS layout depends on it):

```bash
curl -sL https://downloads.diagrid.io/cli/install.sh | RELEASE_VERSION="v1.36.0" bash
```

CI pins `DIAGRID_CLI_VERSION` in `.github/workflows/e2e-quickstarts.yml`; use the
same value locally if you want CI parity.

## When a suite fails

Open `results/<api>/log.html` — it shows every keyword with its arguments and the
captured HTTP response. The `diagrid dev run` output is captured to
`results/<api>/<api>-dev-run.log`; log-marker failures are usually clearest there.

Two failure shapes worth recognising:

- **A response body mismatch** is either a transcription error in
  `variables/quickstarts.py` or genuine drift between a README and its app. Check
  the README before changing the table.
- **A log marker timing out** usually means the wording changed in the app. The
  marker table records which markers are language-invariant and which are not;
  see the per-marker comments in the "Log markers" section of
  `variables/quickstarts.py` for why each is truncated where it is.

### Readiness markers are not uniform per API

`diagrid dev run` only prints `Connected App ID "<id>" to http://localhost:<port>` for
an app that has a **non-zero `appPort`** in its dev config. This is not the same for
every language of a given API: pubsub's `publisher` has an `appPort` in csharp and
python but not in java or javascript, so `diagrid dev run` emits that connection
line for the publisher in only two of the four languages (java and javascript wait
on the subscriber's line only). `CONNECTED_APPS` in `variables/quickstarts.py` is
therefore keyed by `(api, language)`, not by API alone — do not "simplify" it back
to a per-API dict, the divergence is real and verified against each language's dev
config, not a typo.

## Adding a language or API

1. Add its entries to every dict in `variables/quickstarts.py`, transcribed from the
   new README.
2. Add a tagged test case to the relevant suite calling the existing keyword.
3. Run `uv run python docsync/check_readme_sync.py --all` — it will tell you what you
   missed.
4. Add the language to the CI matrix in `.github/workflows/e2e-quickstarts.yml`, and a
   runtime-setup step for it.

## Limitations

- **The four canonical suites' situation is unchanged.** Each has been verified
  only with `robot --dryrun` (syntax, keywords, variables resolve) and the
  doc-sync checker (the READMEs and the harness agree on what commands exist). No
  suite has executed `diagrid dev run` against live Catalyst, so no assertion
  below has actually been seen to pass — or to fail correctly — against the real
  thing. Confirming that is on whoever runs this harness with real credentials
  first.
- **The new `agents/langgraph` suite has never run against real Catalyst
  either.** No model provider key was available while it was written:
  `DIAGRID_API_KEY` is set in the dev environment, but `OPENAI_API_KEY`,
  `GEMINI_API_KEY` and `ANTHROPIC_API_KEY` are all unset, and this quickstart
  calls OpenAI. Consequently no assertion in it has been seen to fail when the
  thing it checks is broken — no mutation check has run — and
  `REQUESTS[0]["field"]` in `variables/agents_langgraph.py` is still `None`,
  because the response shape can only come from an observed live response. What
  *is* verified: the lint dryrun resolves the suite, the doc-sync checker holds
  it to `agents/langgraph/README.md` in both directions, and it fails fast on a
  missing model key — `Require Env Var` fails before `Build Quickstart`,
  `Run Documented Commands` and `Start Quickstart` ever run (all three are
  recorded `NOT RUN`), so a missing secret cannot leak a Catalyst project. It is
  registered `nightly: False` for exactly that reason; flipping that flag needs a
  green live run plus a mutation check, with the flag flip landing in the same
  commit as the evidence (see "Running an agent-family suite locally" above).
- **The CI workflow itself has never been executed.** Everything wired for
  agent-family suites is static analysis (YAML parse, `actionlint`, the
  credential-free harness commands above). Someone has to push the branch and
  run one `workflow_dispatch` before the nightly schedule can be trusted.
- Three things in particular remain unproven for the canonical suites and matter most:
  1. That the log-marker assertions (readiness markers, "log marker timing out"
     above) genuinely **fail** when the marker they wait for is absent from the
     `diagrid dev run` output, rather than passing vacuously.
  2. That the pubsub subscriber-delivery assertion genuinely **fails** when the
     subscription is broken. This is the single most important unproven assertion
     in the harness: if it does not actually fail on a broken subscription, a
     broken subscription ships green.
  3. The real `GET /workflow/status/{id}` response shape for csharp, java, and
     javascript. No README documents it — only the python README shows a status
     body (`"runtimeStatus":1`) — which is why those three languages' status
     assertions are deliberately weak (HTTP 200 plus non-empty body only, no
     shape check).
- doc-sync is a string presence and equality check, not a proof of execution. It
  catches a README edit the suites have not followed; it does not guarantee every
  documented command is executed and asserted.
- The suites test only the documented flow. `DELETE /order/{id}` and
  `POST /workflow/terminate/{id}` exist in every implementation but are documented
  in no README, so they are untested. Documenting them brings them under test.
- **Model nondeterminism.** Agent-family suites assert structure, not content: a
  documented status code, a non-empty named field where a shape is known, and a
  tool-call log marker. A model refusal, a rate limit or an unusually slow
  completion can fail a leg without anything being wrong in the quickstart.
  There is no retry; if this proves noisy, one retry on the trigger request is
  the first thing to try.
- **One mutation check per suite** proves one assertion. The others are unproven
  in the same sense as the log markers above.

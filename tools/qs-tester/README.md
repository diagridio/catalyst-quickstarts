# qs-tester

End-to-end tests for the `workflow`, `state`, `pubsub` and `invocation`
quickstarts, and for three agent-family ones (`agents/langgraph`,
`agents/microsoft-dotnet`, `agents/spring-ai/event-planner`), built on
[Robot Framework](https://robotframework.org/). The tests run the *actual*
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
- `resources/tests/` — the harness's own tests. `smoke.robot` covers the
  process-teardown keywords, `keywords.robot` covers the keywords the
  agent-family suites depend on against `echo_server.py`, `readiness.robot`
  covers the invocation readiness gate against `flaky_server.py`, and
  `teardown.robot` covers the two Stop Quickstart paths that release nothing.
  `keywords.robot` also covers the Catalyst-attach gate. None need credentials, they run in seconds, and
  CI's `lint` job runs the whole directory on every PR that trips the
  workflow's `paths` filter — run them locally too when you touch
  `process.resource`, `catalyst.resource` or either gate.
- `variables/quickstarts.py` — the per-(API, language) table. **Everything in it is
  transcribed from a README.** Change a README, change this file.
- `docsync/check_readme_sync.py` — asserts the two stay in agreement.
- `docsync/check_skill_docs.py` — the same discipline applied to the
  `add-quickstart-e2e-test` skill: `diagrid` commands the skill's own SKILL.md
  and `references/` show have to be traceable to a quickstart README. Two rules,
  each with its own reach, not one rule applied twice: a candidate that names at
  least one flag and holds no `<...>`/`{...}` placeholder must match a documented
  command verbatim, and separately every `--flag` any candidate names must appear
  in a documented command for the same CLI object. A *flagless* mention
  (`diagrid login`, a bare `diagrid dev run`) is covered by neither — it names
  nothing that could go stale — and a block tagged `illustrative` is exempt from
  both. The module docstring spells out the exemptions and the one known hole.
  It exists because the skill's examples went stale the moment the provisioning
  flags changed and nobody noticed — prose that nobody checks is prose that
  drifts. Needs no credentials, and CI's `lint` job runs it on every PR that
  touches the skill directory, a quickstart README or the harness — all three
  are in the workflow's `paths` filter, so a skill-only PR does trigger a run.
- `ci/` — Catalyst project lifecycle scripts.
- `variables/suites.py` — the registry of every suite. The lint dryrun, the CI
  agents matrix and doc-sync all read it, so registering a suite is one row here
  rather than three edits in the workflow.
- `variables/agents_<name>.py` — one per agent-family quickstart, holding that
  quickstart's documented command sequence verbatim. The file name is the
  manifest row's `data` key: the quickstart's path below `agents/` with every
  `/` and `-` replaced by `_`, so `agents/spring-ai/event-planner` is
  `variables/agents_spring_ai_event_planner.py`.
- `ci/list-suites.py` — reads the manifest for CI (`--paths`, `--matrix agent`,
  `--validate`, `--row <suite>`).
- `ci/check_mutation.py` — the mutation check's verdict: did the mutated run fail
  on the assertion the mutation broke, or on something else? See "Running an
  agent-family suite locally" below.
- `ci/project-name.sh`, `ci/login.sh` — the ephemeral name, and the API-key login.

Each suite lives next to the quickstarts it tests: `state/tests/quickstart.robot`,
`pubsub/tests/quickstart.robot`, and so on. Each canonical suite has four tests
tagged `csharp`, `java`, `javascript`, `python`. Agent-family suites (see "Two
kinds of quickstart" below) have exactly one test each, at
`<quickstart-dir>/tests/quickstart.robot` — wherever the quickstart itself
lives. That is not a fixed depth: `agents/langgraph/tests/quickstart.robot` is
two segments below the repository root and
`agents/spring-ai/event-planner/tests/quickstart.robot` is three.

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

The only thing the harness ever rewrites in a documented command is the project
name. Every canonical quickstart README spells `--project <api>-quickstart` in
its `dev run`, and `Start Quickstart` substitutes the ephemeral name for it. The
three agent READMEs are the exception: their `dev run` is bare, because a
documented `project create ... --use` already selected the project, and the
suites reproduce that bareness on purpose — see "The `dev run` command can be
bare" below. For those, the substitution lands in the documented `project
create` (and `project delete`, where the README documents one — `agents/langgraph`
does not) commands instead. Everything else — the file, the
flags, `mvn spring-boot:run`, the `uv run` prefix — runs exactly as the README
shows it.

### Selecting languages and APIs

Each canonical suite has four tests tagged by language; each agent-family suite
has one, tagged with its language, its own name and `agents`. Filter with
`--include` / `--exclude` (repeatable, `--include` ORs):

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

Agent-family quickstarts (`agents/*`, `dapr-agents/*`, `mcp-auth/*`) are not a
matrix. Each has exactly one language, its own suite beside it at
`<quickstart-dir>/tests/quickstart.robot`, and its own data module. They are not
a flat two-level list either: `agents/spring-ai/event-planner` sits three
segments deep, so nothing here may assume a `<family>/<name>` shape. Six things
differ and are worth knowing before you touch one:

1. **They provision themselves.** Most of their READMEs document `diagrid
   project create` with per-quickstart managed-service flags, then `agent
   create`, and sometimes `app create` and `apply -f`, so the suite runs those
   documented commands through `Run Documented Commands`. The flags are transcribed data,
   not a constant: `agents/langgraph` and `agents/microsoft-dotnet` both
   document `--enable-managed-workflow --deploy-managed-kv
   --deploy-managed-pubsub --wait --use`, while `agents/spring-ai/event-planner`
   documents the same set without `--deploy-managed-pubsub`. (The older
   `--enable-agent-infrastructure` was replaced by these flags and appears in no
   README any more — a document that still states it as current is stale.)
   Not every one of them provisions, though: `agents/dapr-agents/orchestrator`
   documents no `project create` at all, and `mcp-auth/python` documents one
   with no managed-service flags — read the README you are testing rather than
   the family (the skill's `references/agent-quickstart.md` catalogues the
   three shapes). `ci/setup-project.sh` is for the canonical suites, whose
   READMEs document no provisioning at all, and for an agent quickstart whose
   README documents none either.
2. **The `dev run` command can be bare.** The three suites here all follow a
   documented `project create ... --use` with a `dev run` carrying no
   `--project`. The suite reproduces that exactly, so a regression in `--use`
   fails here. (`mcp-auth/python` documents the opposite — an explicit
   `--project` — which is why this is per-quickstart data too.)
3. **Assertions are structural.** Responses contain model output, so the suites
   assert a status code, a named field being present and non-empty where a
   response shape is known, and a log marker showing the expected tool ran. Be
   careful with the status code: **none of the three READMEs behind these
   suites documents one**, so the `status: 200` in all three data modules is an
   assumption rather than a transcription, and for two of the three it is
   probably wrong — see "Limitations".
4. **The manifest row's `name` is a path, and it has a 26-character budget.** An
   agent row's `name` is the quickstart's path below `agents/` with slashes
   replaced by dashes (`agents/spring-ai/event-planner` →
   `spring-ai-event-planner`), which makes it unique by construction. It is also
   the leg CI hands `ci/project-name.sh`, so the ephemeral project is
   `qs-ci-agents-<name>-<run-id>`. Catalyst caps that at 55 characters, and the
   binding run id is the *local* fallback (`local` plus a 10-digit epoch, 15
   characters — longer than a GitHub run id), which leaves exactly 26 for
   `name`. `suites.validate()` enforces it, so `ci/list-suites.py --validate`
   fails the lint job in seconds instead of failing at `diagrid project create`
   inside a nightly leg and leaking a half-made project. A row that needs more
   room may carry an explicit, shorter `leg`, which `suites.leg_id` prefers over
   `name`; `spring-ai-event-planner` at 23 characters is the tightest real case
   so far and needs no such escape hatch.
5. **`connected_apps` is part of every agent data module.** Its
   `get_quickstart()` returns `connected_apps`, the `(appID, appPort)` pairs
   read out of the quickstart's dev config. `Start Quickstart` records those app
   IDs into `@{CONNECTED_APP_IDS}` so `Stop Quickstart` can call `Release App
   Connection` for each, which is what keeps a finished run from leaving a
   `trust.diagrid.io` endpoint pointing at a dead tunnel; `Wait Until Apps
   Connected` waits for the matching `Connected App ID "<id>" to
   http://localhost:<port>` line. That an agent app emits that line at all was
   **confirmed** by the 2026-08-27 live run, so the appPort rule ("Readiness
   markers are not uniform per API" below) holds here too.
6. **They need a Catalyst-attach gate that the canonical suites do not.** Every
   readiness signal above — the connection line, the readiness marker, the
   health probe — is satisfied by the *local* process. None of them means
   Catalyst has attached to the app, and a workflow call made before it has does
   not fail: it hangs, and it never recovers. Measured on `agents/langgraph`,
   2026-08-27: the documented POST fired 25 ms after the health probe went green
   hung for the full 120 s client timeout and never created a workflow instance,
   and **twelve retries over 181 s never got it back** — the first call into the
   window poisons the app's workflow client for good. That is why the gate runs
   *before* the first request instead of wrapping it in a retry. Gated on
   `${qs}[catalyst_probe_markers]`, the same request answered 200 in ~1 s on
   three consecutive runs. The marker is an *inbound* request from Catalyst in
   the app's own captured output (`GET /dapr/config` for langgraph), so it is
   per-quickstart data like `READY_MARKERS`. Only `agents/langgraph` has a
   verified marker; the other two carry `CATALYST_PROBE_MARKERS = ()` and a note.
   Two active probes were tried first and are **vacuous** — see "The
   Catalyst-attach gate" in the skill's `references/agent-quickstart.md`.

Nightly membership is per suite (`nightly` in the manifest), and CI reads it
only for agent-family rows — canonical scheduling stays the business of the
`e2e` job's own hand-written language matrix. Each agent leg costs a project
with managed services plus real model tokens, so suites left at
`nightly: False` run only on `workflow_dispatch`.

### Running an agent-family suite locally

Every suite's log-marker and readiness waits read from three variables defined
in `resources/process.resource`: `${MARKER_TIMEOUT}` (default `60s`),
`${READINESS_TIMEOUT}` (default `180s`) and `${CONNECT_TIMEOUT}` (default
`180s`). All are overridable with `robot --variable`, which is what lets the
mutation check below give up in seconds instead of waiting out a three-minute
readiness timeout.

**Do not shorten `${CONNECT_TIMEOUT}`.** It bounds `Wait Until Apps Connected`
alone, which waits on Catalyst establishing the dev tunnel — measured at 32-36s
against a real project, where every other wait finishes in about five seconds.
It is a separate variable precisely so the mutation check can shorten the others
without starving it. When the two were one variable, the documented
`--variable READINESS_TIMEOUT:20s` killed the connection gate at 20s and the run
died before reaching the mutation; `check_mutation.py` rejected the result (the
target keyword came back `NOT RUN`), but only after a Catalyst project had been
spent on a run that proved nothing.

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

# assert the add-quickstart-e2e-test skill's own `diagrid` examples are still
# commands some quickstart README documents
uv run python docsync/check_skill_docs.py

# unit-test the doc-sync checkers and the manifest itself
uv run pytest -q

# the harness's own keyword tests, no Catalyst project or credentials needed
uv run robot resources/tests
```

`ci/list-suites.py --paths` reads `variables/suites.py`, so this is the same
command the CI `lint` job runs, and registering a new suite there is what puts it
under this check — no separate edit here. Filtering to only the four canonical
suites, for a quicker local loop, means falling back to the glob
(`../../*/tests/quickstart.robot`): the single `*` matches one path segment, so
it resolves to exactly `workflow`, `state`, `pubsub`, `invocation` and does not
reach agent-family suites, which live at least two segments deep
(`agents/langgraph/tests/quickstart.robot`, and three for
`agents/spring-ai/event-planner/tests/quickstart.robot`).

### CLI version

The `diagrid` CLI installer (`https://downloads.diagrid.io/cli/install.sh`) does
**not** take the version as a positional argument. It reads the `RELEASE_VERSION`
environment variable and requires the leading `v` (its GCS layout depends on it):

```bash
curl -sL https://downloads.diagrid.io/cli/install.sh | RELEASE_VERSION="v1.67.0" bash
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
- **A 500 on the invocation request** means Catalyst could not reach the server app
  through the dev tunnel. Curl the API directly to see the error the client app
  discards (`client/main.py` logs only `result.reason`):

  ```bash
  TOKEN=$(diagrid appid get client --project "$PROJECT" -o json | jq -r .status.apiToken)
  URL=$(diagrid project get "$PROJECT" -o json | jq -r .status.endpoints.http.url)
  curl -i -X POST "$URL/neworder" -H 'dapr-app-id: server' -H "dapr-api-token: $TOKEN" \
    -H 'content-type: application/json' -d '{"orderId":1}'
  ```

  `ERR_DIRECT_INVOKE ... app is not in a healthy state` means the app channel is
  not routable: either the startup window the gate exists to absorb, or a project
  whose app connection was never released (see `Release App Connection`).

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

- **Only the invocation suite has been run against a real Catalyst project**, and
  only its `python` and `csharp` legs (2026-08-24). python failed first — the client
  returned 500 because Catalyst could not yet route to the server app — which is
  what `Wait Until Not Server Error` was added for; it then passed, and a repeat run
  logged the gate absorbing two real 500s over 6.5s before the documented 200. The
  race is not python-specific: a hand-run csharp session answered 500 on the first
  POST after both readiness signals were satisfied too. Both legs pass with the
  gate. The teardown fix was verified the same way: the `server` app ID's app
  endpoint is cleared after the suite, where it used to keep a dead
  `trust.diagrid.io` tunnel.
  The other three canonical suites have been verified only with `robot --dryrun` (syntax,
  keywords, variables resolve) and the doc-sync checker (the READMEs and the harness
  agree on what commands exist), so their assertions have not been seen to pass —
  or to fail correctly — against the real thing.
- java and javascript were checked by reading their clients, not by running them:
  both return 500 for a failed invocation (`ResponseEntity.status(500)`,
  `res.status(500)`), which is the signal the gate polls, so the gate is sound for
  all four. The way to confirm a client's failure mapping without waiting for the
  race is to disconnect the target app mid-session
  (`diagrid dev stop --app-id server`) and POST to the client: that is how csharp's
  mapping was verified. Note that `dev stop` also kills the local `diagrid dev run`
  process, which is harmless in teardown (the process tree is already stopped by
  then) but will end a session you are still using.
- **`agents/langgraph` is `nightly: True`; the other two are not.** The bar for
  that flag is a green live run *plus* a mutation check the verdict tool accepts,
  and only langgraph has cleared it (2026-08-28). `agents/microsoft-dotnet` and
  `agents/spring-ai/event-planner` have had neither half. The bullets that follow
  are what that costs.
- **`agents/langgraph` has run against real Catalyst three times and not yet
  passed**, but each run has failed further along than the last. 2026-08-27:
  - Runs 1 and 2 died 120s into the documented POST, which hung and never created
    a workflow instance — the suite was firing inside Catalyst's attach window
    (the sixth bullet of "Two kinds of quickstart"). Run 2 also proved the *first*
    gate written for this, an active probe of the app's own
    `GET /agent/run/{workflow_id}`, was **vacuous**: it passed in 76ms and the
    POST hung anyway. It was removed, not patched.
  - Run 3, with `Wait Until Catalyst Attached` in place, got past the window —
    the gate waited 6.0s and the POST was answered in 5.4s. It then failed on
    `InvalidExpectedStatus: 200`: RequestsLibrary rejects a non-string
    `expected_status`, and an agent suite reads its status from a Python data
    module, where `200` is an int. Latent in all three agent modules from the
    start and invisible until now, because the hang always raised first. Fixed by
    converting in `POST And Expect`/`GET And Expect`/`POST And Expect Field`, with
    the int path now covered in `resources/tests/keywords.robot` — every test
    there had been passing a Robot literal, which is already a string, which is
    exactly why the harness's own tests could not catch it.
  Between them these runs settled a lot that was previously only reasoned:
  `SETUP`'s documented `project create` and `agent create` both succeed (7-11s
  together); `diagrid dev run` does print `Connected App ID "schedule-planner" to
  http://localhost:8005` for an agent app, so `CONNECTED_APPS` is right and
  `Wait Until Apps Connected` is not vacuous (32-36s); the `Uvicorn running on`
  marker arrives; `HEALTH_PROBES`' `GET /dapr/subscribe` really answers 200
  against the live app; and teardown releases the app connection.
  The gate was additionally verified out-of-suite against a real project with an
  OpenAI-free clone of `main.py`, so the LLM could not be the variable: 4/4
  ungated runs hung permanently at readiness+0, 3/3 gated runs answered 200 in
  ~1s, marker arriving at t+1s, t+3s and t+3s.
  - A hand-run of the same quickstart on 2026-08-28 then completed the whole
    documented flow (LLM call, `tools` node, `COMPLETED`) and showed the suite's
    remaining assertion could never have passed: `REQUESTS[0]["log_marker"]` was
    `check_availability`, and **nothing prints that string** — `call_tools` in
    `main.py` invokes the tool without logging it. doc-sync did not catch it
    because it only requires a marker to appear *somewhere* in the README, and
    the prose "Use the `check_availability` tool" satisfied that. The marker is
    now `[ACTIVITY] Executing node 'tools' as Dapr activity`, which the SDK really
    prints and which the README now documents in a `text` block, and
    `REQUESTS[0]["field"]` is `"status"` — a key the response envelope carries
    only on the completed path.
  - Run 4, with all of the above in place, **passed end to end** against a real
    Catalyst project (2026-08-28).
  - The mutation check then passed on 2026-08-28, but only on the second attempt,
    and the first attempt is the more useful record. It failed with
    `Wait Until Apps Connected` timing out at 20.07s, because the documented
    recipe's `--variable READINESS_TIMEOUT:20s` starved a gate that legitimately
    takes 32-36s — so the run died before reaching the mutation.
    `ci/check_mutation.py` rejected it (`statuses seen: NOT RUN`), which is
    exactly what that tool exists for: robot exited non-zero both times, and only
    one of the two runs proved anything. `${CONNECT_TIMEOUT}` now bounds the
    connection gate separately. On the retry the gate took its honest 36.10s and
    the mutated `Wait Until Ready Marker` failed at 20.08s naming the sentinel.
  Still open, and worth knowing before trusting the green:
  - The mutation targeted `READY_MARKERS` only. The two assertions added while
    getting this suite green — the `[ACTIVITY] Executing node 'tools'` log marker
    and `Wait Until Catalyst Attached` — have **not** been shown to fail when what
    they check breaks. Given this suite already shipped one gate that passed in
    76ms while doing nothing and one marker that could never match, those are the
    two least worth taking on trust.
  - The doc-sync gap that let `check_availability` through is now closed: a log
    marker must appear inside a fenced block, so a prose mention no longer counts
    as documentation that the app prints it. `READY_MARKERS` is exempt on
    purpose — `Uvicorn running on` is documented as inline code in a sentence.
- **`agents/microsoft-dotnet` and `agents/spring-ai/event-planner` have never
  run either**, for the same missing model key, and each carries two weaknesses
  `agents/langgraph` does not:
  - **`HEALTH_PROBES` is empty for both, on purpose.** Neither app serves a GET
    route — `microsoft-dotnet`'s `Program.cs` registers only
    `app.MapPost("/run")`, and `event-planner`'s `EventPlannerController` only
    `@PostMapping("/run")`, with no `spring-boot-starter-actuator` on the
    classpath — so `Wait Until Apps Healthy` does nothing for them and readiness
    rests on the connection gate. `agents/microsoft-dotnet` still has its
    documented `Established gRPC bidirectional stream with Dapr sidecar` marker;
    `agents/spring-ai/event-planner`'s README documents no readiness wording at
    all, so `READY_MARKERS` is empty too and the connection line is the *only*
    readiness signal that suite has.
  - **Their trigger request asserts `status: 200`, and this is expected to fail
    on the first credentialed run.** Neither app is expected to answer the call
    at all: tool 2 crashes the process mid-request by design.
    `agents/spring-ai/event-planner`'s `EventPlannerTools.java` calls
    `Runtime.getRuntime().halt(1)` before the controller returns, and
    `agents/microsoft-dotnet`'s README says of the same step "The process exits
    — this is expected." A live run will most likely see a connection error
    rather than any matchable status code. The assertion is left exactly as it
    stands, deliberately: what replaces it has to come from an observed
    response, and putting a plausible-looking value there instead is the
    guessing that `field = None` in `variables/agents_langgraph.py` exists to
    refuse. Recorded here so the first live run fails on a documented line
    rather than a mysterious one.
- **None of the three agent READMEs documents a status code**, so
  `REQUESTS[...]["status"] = 200` in `variables/agents_langgraph.py`,
  `variables/agents_microsoft_dotnet.py` and
  `variables/agents_spring_ai_event_planner.py` is an assumption in every case,
  not something transcribed. For `agents/langgraph` a 200 is at least plausible
  — the endpoint returns normally — but it is still unverified. For the other
  two it is worse than unverified; see the bullet above.
- **The connection line for an agent app is inferred, not observed.**
  `CONNECTED_APPS` in all three agent data modules comes from reading the
  quickstart's dev config and applying the appPort rule ("Readiness markers are
  not uniform per API" above); no agent suite has yet seen `diagrid dev run`
  print that line. This matters most for `agents/spring-ai/event-planner`, whose
  entire readiness gate it is: if the inference is wrong there, the symptom is a
  readiness timeout on a perfectly healthy quickstart.
- **Eleven of the fourteen `agents/*` quickstarts have no suite at all** (adk,
  claude-agents, crewai, dapr-agents/durable-agent, dapr-agents/orchestrator,
  deepagents, openai-agents, pydantic-ai, spring-ai/crash-recovery,
  spring-ai/durable-memory, strands), and neither do `dapr-agents/*` or
  `mcp-auth/*`. Nothing detects drift in them beyond
  `docsync/check_skill_docs.py`, which only sees the commands the skill itself
  quotes. Adding a suite is what the `add-quickstart-e2e-test` skill is for.
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
  documented command is executed and asserted. One exception, added after it let a
  broken marker through: a `log_marker` must be found inside a fenced block, not
  merely somewhere in the file.
- The suites test only the documented flow. `DELETE /order/{id}` and
  `POST /workflow/terminate/{id}` exist in every implementation but are documented
  in no README, so they are untested. Documenting them brings them under test.
- **Model nondeterminism.** Agent-family suites assert structure, not content: a
  status code (assumed, not documented — see the bullets above), a non-empty
  named field where a shape is known, and a tool-call log marker. A model
  refusal, a rate limit or an unusually slow completion can fail a leg without
  anything being wrong in the quickstart.
  There is no retry; if this proves noisy, one retry on the trigger request is
  the first thing to try.
- **One mutation check per suite** proves one assertion. The others are unproven
  in the same sense as the log markers above.
- **The mutation procedure itself has never been executed end to end.**
  `ci/check_mutation.py`'s verdict is unit-tested and was checked against two
  real `output.xml` files, and `verify-live.sh` parses correctly and refuses
  canonical suites (both checked), but neither script has run against Catalyst,
  so "the mutated run reaches its assertion because it gets its own project" is
  reasoning about `Run Documented Commands`, not an observation.

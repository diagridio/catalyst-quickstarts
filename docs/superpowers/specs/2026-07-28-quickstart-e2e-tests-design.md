# Design: End-to-end tests for the workflow, state, pubsub, and invocation quickstarts

Date: 2026-07-28

## Problem

The `workflow/`, `state/`, `pubsub/`, and `invocation/` quickstarts ship in four languages
each — 16 runnable applications. Nothing verifies that they still work. The 16 existing
GitHub workflows (`workflow_python.yaml`, `pubsub_csharp.yaml`, and so on) only compile the
code and push container images; none of them start an app, call an endpoint, or assert a
result.

That leaves three classes of breakage invisible until a user hits them:

- **Runtime drift** — a Dapr SDK release changes behaviour, a managed Catalyst component is
  renamed, an endpoint stops responding.
- **Cross-language divergence** — a fix lands in one language and not the other three.
- **Doc drift** — the documented commands stop matching the code.

## Goal

A scheduled daily GitHub Actions run that executes all 16 quickstarts against a real
Diagrid Catalyst project, asserts both the HTTP contract and the application log output,
and opens or updates a single GitHub issue naming exactly what broke.

## Non-goals

- Unit or integration tests inside the quickstart applications.
- Testing the `agents/`, `dapr-agents/`, `mcp-auth/`, or `mcp-access-control/` quickstarts.
- Replacing the existing build-and-push workflows.
- Testing the local-Dapr path (`dapr run -f` with the checked-in Redis component yamls).
  The tests exercise the Catalyst path the documentation describes.

## Constraints discovered in the repository

These shaped the design and are worth stating, because several are non-obvious.

**All four languages of a given quickstart share appIDs and ports.** Every state
implementation uses appID `order-app` on port 5001; pubsub uses `publisher`/`subscriber` on
5001/5002; invocation uses `client`/`server` on 5001/5002; workflow uses `order-workflow` on
5001. Two languages therefore cannot run concurrently in the same Catalyst project, nor on
the same runner. Splitting the test matrix by **language** solves both: within one leg the
four APIs run sequentially and their appIDs do not overlap.

**Catalyst's managed components are named `kvstore` and `pubsub`.** The pubsub default
(`pubsub`) matches all four languages. The KV store does not: `state/java` defaults to
`kvstore`, while `state/python`, `state/javascript`, and `state/csharp` default to
`statestore`.

**`workflow/java` has no `workflow-quickstart.yaml`.** The other three workflow languages
have one. Per the README design spec (`2026-07-28-quickstart-readmes-design.md`), the
documented command for this one case is the `--app-id` form rather than `-f`.

**Application log destination is already correct.** Every `*-quickstart.yaml` sets
`appLogDestination: console`, so application stdout is merged into the `diagrid dev run`
console stream. Capturing that one stream per suite captures every app's log output — which
is what makes log assertions possible without extra plumbing.

## Prior art

`diagrid-labs/dapr-university-instruqt/tools/track-tester` is the model: Robot Framework
suites that run the real commands a user runs and assert on the output, driven by a daily
GitHub Actions workflow with a per-language matrix, `rebot`-merged reports, and an
auto-updating drift issue. This design follows its structure and reuses its hardest-won
piece of code (process teardown, below).

## Architecture

New harness at `tools/qs-tester/`; suites co-located with the quickstarts they test.

```
tools/qs-tester/
├── pyproject.toml            # robotframework>=7,<8 + robotframework-requests
├── uv.lock
├── README.md                 # how to run a single leg locally
├── resources/
│   ├── catalyst.resource     # project lifecycle, `diagrid dev run`, process teardown
│   └── quickstart.resource   # build, health-wait, HTTP + log assertions
├── variables/
│   └── quickstarts.py        # per-(api, language) matrix and log markers
└── ci/
    ├── setup-project.sh      # login, create ephemeral project, create `statestore` KV
    ├── teardown-project.sh   # delete the ephemeral project
    └── reap-orphans.sh       # delete stale qs-ci-* projects from cancelled runs

workflow/tests/quickstart.robot     # 4 tests, tagged csharp|java|javascript|python
state/tests/quickstart.robot
pubsub/tests/quickstart.robot
invocation/tests/quickstart.robot
```

16 tests total: 4 suites x 4 language-tagged tests, selected with `--include <lang>`.

Co-location (rather than `tools/qs-tester/suites/`) matches track-tester and puts the suite
next to the code and the future README it verifies.

### Why one suite per API rather than per language

The HTTP contract of a given API is identical across its four languages — verified, not
assumed (see the assertion matrix). One shared test body per API with a language tag keeps
the four implementations honest about staying in agreement, and any divergence has to be
declared explicitly as a per-language variable, where it is visible and reviewable.

### Process teardown

`resources/catalyst.resource` ports the `Stop Process With SIGINT` keyword from
track-tester's `dapr.resource` unchanged in substance: SIGINT to the process group, wait,
and on timeout walk the real OS parent/child PID tree and `kill -9` every descendant.
`diagrid dev run` detaches children into new process groups exactly as `dapr run -f` does,
so a group-targeted signal alone leaves orphans squatting ports 5001/5002 and corrupting the
next suite in the leg. This is the single most important piece of reused code.

## Suite anatomy

Every one of the 16 tests follows the same five steps:

1. **Build** — the language's documented install command (table below).
2. **Start** — `diagrid dev run` as a background process, stdout+stderr to a per-suite log
   file. The log file is truncated first so a stale file cannot satisfy an assertion.
3. **Wait until healthy** — poll `GET http://localhost:<port>/` until 200, per app. Timeout
   180s: JVM and .NET cold starts on a CI runner are slow, and `diagrid dev run` also has to
   provision appIDs and establish tunnels.
4. **Assert** — the HTTP contract, then the log markers.
5. **Teardown** — stop the process tree, then `diagrid dev stop`, unconditionally.

### Build and run commands per language

Taken from the README design spec so the tests execute the documented commands rather than
invented equivalents.

| Language | Build | Run |
|---|---|---|
| Python | `uv sync` (per app dir for two-app quickstarts) | `uv run diagrid dev run -f <api>-quickstart.yaml --project $PROJECT --approve` |
| .NET | `dotnet build` / `dotnet restore ./<app>` | `diagrid dev run -f <api>-quickstart.yaml --project $PROJECT --approve` |
| JavaScript | `npm install [--prefix ./<app>]` | `diagrid dev run -f <api>-quickstart.yaml --project $PROJECT --approve` |
| Java | `mvn clean install [-f ./<app>]` | `diagrid dev run -f <api>-quickstart.yaml --project $PROJECT --approve` |

One exception, matching the documented command: `workflow/java` has no dev config file, so
it runs

```
diagrid dev run --project $PROJECT --app-id order-workflow --approve -- mvn spring-boot:run
```

This asymmetry is deliberate — the test mirrors the repository and the docs as they stand.
It does not add a `workflow-quickstart.yaml` to fix the inconsistency, because that would
change a file users read as part of a test-only change.

The `--project` value is a harness variable rather than the documented per-API name
(`state-quickstart` and friends), because parallel language legs need distinct projects.

## Assertion matrix

Each test asserts the HTTP contract **and** the application log output. Two independent
signals: HTTP proves the endpoint answers correctly, logs prove the work actually happened
inside the app and, for pubsub, that the message reached the other process at all.

Log assertions use `Wait Until Log Contains` (poll the captured `diagrid dev run` stream
every 2s until the marker appears or the timeout expires), because app logging is
asynchronous with respect to the HTTP response.

### state — one app on port 5001

| Step | HTTP | Log marker |
|---|---|---|
| `POST /order {"orderId":4}` | 201, body contains `Order created successfully` | `Save state item successful.` |
| `GET /order/4` | 200, body contains `4` | `Get state item successful. Order retrieved` |
| `DELETE /order/4` | 204 | `Delete state item successful. Order deleted` |
| `GET /order/4` | 404, body contains `ORDER_NOT_FOUND` | `State item with key` |

All four markers are language-invariant substrings. `Save state item successful.` stops at
the period because python continues `Order saved with key: 4 and value: ...` where the other
three continue `Order saved: 4`. The final marker is deliberately weak — python and csharp
log `State item with key 4 does not exist` while javascript and java log `State item with key
does not exist: 4` — so the invariant part is the prefix.

### invocation — client on 5001, server on 5002

| Step | HTTP | Log marker |
|---|---|---|
| both apps healthy | 200 on `GET /` for each | — |
| `POST /order {"orderId":1}` on client | 200, body contains `Invocation successful` | server: `Invocation received with data` |
| | | client: per-language, see below |

The server marker is invariant as a prefix only: java logs `Invocation received with data 1`
with no colon, the other three use `with data: `.

The client marker diverges completely and needs a per-language entry:

| Language | Client marker |
|---|---|
| Python | `Invocation successful with status code: 200` |
| JavaScript | `Invocation successful with status code: 200` |
| .NET | `Invocation successful with status code 200` (no colon) |
| Java | `Invoke Successful. Response received: 1` |

### pubsub — publisher on 5001, subscriber on 5002

| Step | HTTP | Log marker |
|---|---|---|
| both apps healthy | 200 on `GET /` for each | — |
| `POST /order {"orderId":1}` on publisher | 201, body contains `Message published successfully` | publisher: `Order published: 1` |
| message delivered to subscriber | — (no HTTP surface) | subscriber: per-language, see below |

`Order published: 1` rather than the fuller sentence because csharp logs `Publish
Successful.` with a capital S where the other three use lowercase.

Subscriber marker, per language:

| Language | Subscriber marker |
|---|---|
| Python | `Order received: 1` |
| .NET | `Order received: 1` |
| Java | `Order received: 1` |
| JavaScript | `Order received: {"orderId":1}` |

**This row is the reason log assertions matter.** The publisher returns 201 as soon as the
broker accepts the message; whether the subscriber ever received it is invisible to that
response, and the subscriber exposes no queryable endpoint. Without the subscriber log
marker, a broken subscription or a mis-scoped `subscription.yaml` would pass a green test.

### workflow — one app on port 5001

| Step | HTTP | Log marker |
|---|---|---|
| `POST /workflow/start {"name":"Car","quantity":2}` | 200, extract instance id | `Received order <instanceId> for 2 Car` |
| workflow runs to completion | — | `Order <instanceId> has completed!` |
| `GET /workflow/status/<id>` | 200, body contains `COMPLETED`, case-insensitive | — |
| `POST /workflow/terminate/<id>` | 200 | — |

The two workflow markers interpolate the **actual instance ID** returned by the start call,
so they prove that *this* run's workflow executed rather than merely that some workflow did.

Their message text is identical in all four languages — verified against
`OrderProcessingWorkflow` in each — which is not true of the activity log lines. Compare
`reserveInventoryActivity`:

| Language | Activity log line |
|---|---|
| Python | `Verifying inventory for order <id>: 2 Car` |
| Java | `Verifying inventory for order <id>: 2 Car` |
| JavaScript | `Verifying inventory for 2 Car` |
| .NET | `Reserving inventory for order <id> of 2 Car` |

`updateInventoryActivity` diverges further (`Updated Car inventory to N remaining.` versus
.NET's `There are now: N Car left in stock`). Asserting on activity wording would mean four
maintained variants per activity for no added confidence, because the completion
notification already depends on them: `Order <id> has completed!` is only emitted after
reserve-inventory, process-payment, and update-inventory have all succeeded. Asserting the
two invariant notification messages therefore covers the whole activity chain.

Notification messages are emitted through `NotifyActivity`, which logs the bare message in
python and .NET and prefixes `Notification: ` in java and javascript — substring matching
handles both.

**The completion gate is the log marker, not the status JSON.** This is a deliberate choice.
The status responses diverge structurally: python and java expose `runtimeStatus` at the top
level, .NET nests it under `{state, result}`, and javascript returns the raw SDK state
object. Polling any of them for completion would need a per-language JSON path, and the
javascript key cannot be read from source without the SDK installed.

Gating on `Order <instanceId> has completed!` instead is invariant across all four languages,
needs no JSON path, and is a stronger assertion — it proves the activity chain ran, whereas a
status field only reports what the engine recorded. The status endpoint is still called and
still asserted, but with a case-insensitive substring check for `COMPLETED` on the raw
response body, which is oblivious to nesting and to .NET's PascalCase enum serialisation.

That leaves exactly one per-language accessor:

| Language | Start response key |
|---|---|
| Python | `instanceId` |
| Java | `instanceId` |
| .NET | `instanceId` |
| JavaScript | `instance_id` |

`instance_id` in javascript against `instanceId` in the other three is real drift. The test
records it as a variable rather than papering over it, so it shows up in review.

### Marker organisation

`variables/quickstarts.py` exposes a `MARKERS` dict keyed by `(api, language)`. Markers that
are invariant across languages are defined once as module constants and referenced from all
four entries; only genuinely divergent markers get per-language strings. The file is the
single place where cross-language divergence is recorded, and a diff to it is a signal that
the four implementations have drifted further apart or come back together.

Markers are chosen to be unambiguous between the two apps sharing a log stream in the
two-app quickstarts: publisher logs `Order published`, subscriber logs `Order received`;
client logs `Invocation successful`, server logs `Invocation received`. No marker can be
satisfied by the wrong process.

## Catalyst environment lifecycle

One ephemeral project per matrix leg, created at the start and deleted at the end, with the
legs throttled so that no more than two projects exist at the same time.

`ci/setup-project.sh`:

```bash
diagrid login --api-key "$DIAGRID_API_KEY"
diagrid project create "qs-ci-$LANG-$GITHUB_RUN_ID" \
  --deploy-managed-kv --deploy-managed-pubsub --enable-managed-workflow \
  --wait --use
diagrid kv create statestore --wait
```

The second KV store is what lets all four state legs pass unmodified: `--deploy-managed-kv`
provisions `kvstore`, which `state/java` expects, and `diagrid kv create statestore`
provisions the name the other three expect. Both are real stores, so no `STATESTORE_NAME`
override is needed anywhere and each language exercises its own published default.

`ci/teardown-project.sh` deletes the project under `if: always()`.

Ephemeral projects mean zero state carried between nights: no leftover KV keys, no
half-configured appIDs, no subscription left over from a previous schema. The costs are
accepted deliberately:

- **Provisioning time**, a few minutes per leg. Paid once per leg, not per API, because the
  four APIs share the leg's project.
- **Leaked projects when a job is cancelled**, since teardown never runs. `ci/reap-orphans.sh`
  runs on the schedule and deletes any `qs-ci-*` project older than 6 hours.

### At most two projects exist at any moment

The four language legs run **two at a time**, not four, so the run never needs more than two
ephemeral projects concurrently. This is a hard requirement rather than a tuning choice:
each project carries a managed KV store, a pub/sub broker, a workflow engine, and a second
KV store, and four of those at once risks hitting Catalyst account limits — a limit breach
fails the run for a reason that has nothing to do with the quickstarts, which is the worst
kind of test failure.

`max-parallel: 2` on the matrix is the mechanism. Two legs start, and as each finishes the
next starts, so the guarantee is "never more than two", not "two strict waves". That is what
the constraint actually requires, and it wastes no time waiting for a slow partner to finish.

Leg order in the matrix is `[java, javascript, csharp, python]` so the two slow,
build-heavy languages (java, .NET) are not scheduled against each other. Pairing each slow
language with a fast one keeps both concurrency slots doing useful work rather than leaving
one idle while a Maven build finishes.

Each leg gets `timeout-minutes: 60`. With only two slots, a hung leg no longer just delays
its own result — it holds a slot that a queued leg needs, and it holds a project open while
it hangs. The timeout bounds both. It sits above the expected per-leg time with room to
spare; it is a backstop, not a target.

## GitHub Actions workflow

New file `.github/workflows/e2e-quickstarts.yml`. The 16 existing build-and-push workflows
are untouched.

```yaml
on:
  schedule:    [{cron: '0 5 * * *'}]   # daily 05:00 UTC, before the working day in EU
  workflow_dispatch:                    # inputs: language, api (both optional filters)
  pull_request:                         # lint job only — no secrets, fork-safe

concurrency: {group: e2e-quickstarts, cancel-in-progress: false}

jobs:
  lint:    # runs on PRs and on schedule
    uv sync && robot --dryrun (all 4 suites)   # resolves syntax, keywords, variables

  reap:    # schedule only
    delete qs-ci-* projects older than 6h

  e2e:
    if: github.repository_owner == 'diagridio'
    environment: shared-production
    timeout-minutes: 60
    strategy:
      fail-fast: false
      max-parallel: 2                     # never more than 2 Catalyst projects at once
      matrix: {lang: [java, javascript, csharp, python]}   # slow paired with fast
    steps:
      - setup-dotnet 10.0.x | setup-java 17 temurin + ~/.m2 cache | setup-node lts | setup-uv
      - install pinned diagrid CLI
      - ci/setup-project.sh                    # exports PROJECT to $GITHUB_ENV
      - pre-warm deps (mvn dependency:go-offline, dotnet restore, npm ci, uv sync)
      - for api in workflow state pubsub invocation:
          robot --outputdir results/$api --include $lang $api/tests/quickstart.robot
      - rebot --outputdir results --name "quickstarts ($lang)" results/*/output.xml
      - upload-artifact robot-$lang
      - ci/teardown-project.sh                 # if: always()

  report:
    needs: [lint, e2e]
    if: failure() && github.event_name != 'pull_request'
    create-or-comment on the single `e2e-failure` labelled issue
```

Details that matter:

- **Toolchain versions** are verified against the repository, not guessed: `net10.0` in every
  csproj, `<java.version>17</java.version>` in every pom, `requires-python = ">=3.12"` in
  every pyproject, `node index.js` with no engine constraint in every package.json.
- **Dependency pre-warming runs outside the timed Robot keywords.** track-tester learned this
  the hard way: on a cold `~/.m2` the dependency download alone exceeded the build timeout
  and the build was killed mid-download. The timed step should only compile.
- **The per-API loop uses the `if !` guard** so a failure in one API still lets the remaining
  three run. One nightly run then reports every broken API for that language, not just the
  first. The leg fails at the end if any API failed.
- **`pull_request` triggers only `lint`.** The e2e job needs `DIAGRID_API_KEY`, which is not
  available to fork PRs, and 16 real Catalyst projects per PR would be wasteful regardless.
  `--dryrun` still catches broken keyword references and typos in suite files on every PR.
- **`max-parallel: 2` caps concurrent Catalyst projects at two**, as described above. It also
  roughly doubles wall-clock time against an unconstrained matrix — expect somewhere around
  45 to 60 minutes for the whole run rather than 25 to 30. For a nightly schedule that is a
  cheap price for staying inside account limits. Both figures are estimates to be replaced
  with real numbers after the first few runs.
- **`fail-fast: false` matters more with a capped matrix.** With `fail-fast` enabled, one
  failing leg would cancel the queued legs that had not started yet, and a cancelled leg
  leaks its project. It must stay `false`.
- **`concurrency` without `cancel-in-progress`** so a manual dispatch cannot cancel a
  scheduled run mid-flight and leak its project.
- **`report` is skipped on pull requests**, so a `lint` failure on a PR does not open a drift
  issue. Drift issues should come only from real scheduled or dispatched runs.

### Failure reporting

The `report` job follows track-tester's pattern. Each failing leg writes a
`failed-<lang>.txt` naming the APIs that failed; the report job downloads all artifacts,
collects those files, and creates — or comments on, if it already exists — a single open
issue labelled `e2e-failure`. The body names the failing `lang: api` pairs, links the run,
and includes the `gh run download` command per failing leg for fetching the merged
`report.html`.

One issue that accumulates comments, rather than a new issue per night, keeps a recurring
breakage in one place with its history.

## Secrets and configuration

| Name | Kind | Purpose |
|---|---|---|
| `DIAGRID_API_KEY` | secret | `diagrid login --api-key` |
| `DIAGRID_CLI_VERSION` | env in workflow | pin the CLI so a CLI release cannot silently change behaviour |

The existing workflows use `environment: shared-production`; this one does the same. **The
API key secret must be created and its exact name confirmed** — no suitable secret is
currently referenced by any workflow in the repository.

## Verification

The harness is itself testable, and its correctness is established in three layers:

1. **`robot --dryrun` on all four suites** resolves every keyword and variable without
   starting anything. Runs on every PR.
2. **A single leg run locally** against a real Catalyst project, for each of the four
   languages, before the workflow is enabled on a schedule. This is the step that confirms
   every log marker in this spec actually appears in the captured stream — the markers were
   read from source, and reading source is not the same as observing output.
3. **A deliberate-break check**: point one marker at a string the app does not log and
   confirm the suite fails rather than passing vacuously. Log assertions that silently never
   match are the main failure mode of this design, and a green run proves nothing until this
   check has been done once per API.

## Known issues found while designing, not fixed here

These are real and worth separate PRs. They are out of scope; fixing quickstart source in a
test-only change would be the wrong bundle.

- **`invocation/python/venv/`** is a checked-in Python 3.9 virtualenv. It will confuse
  `uv sync` and should be deleted and gitignored. This one may need resolving before the
  python invocation leg can run.
- **`pubsub/python/publisher/main.py`** catches `grpc.RpcError` without importing `grpc`,
  so the error path raises `NameError` instead of returning a 500.
- **`state/java` expects `kvstore` while the other three expect `statestore`.** Worked around
  in CI by provisioning both; the inconsistency remains in the repository.
- **`state/javascript` keys on `order<id>`** (`order4`) where python, java, and .NET key on
  the bare id (`4`). The tests do not notice, because every call goes through the app's own
  API and is self-consistent. A user following the README's console-explorer step will see a
  differently named key in javascript than in the other three languages.
- **`workflow/javascript` returns `instance_id`** where the other three return `instanceId`.
- **`workflow/java` has no `workflow-quickstart.yaml`**, unlike the other three languages.
- **Log wording diverges across languages** for the same operation — capital-S `Publish
  Successful` in .NET, `Invoke Successful. Response received` in java's invocation client, a
  missing colon in java's invocation server. Harmonising these would let the marker table
  collapse to invariants only.

## Deferred: doc-sync

track-tester's `docsync/check_doc_sync.py` asserts that every runnable command in a
challenge's `assignment.md` appears in the neighbouring suite, which is what catches
*documentation* drift rather than runtime drift.

The equivalent here is not yet possible: these four quickstart directories have no READMEs.
The `2026-07-28-quickstart-readmes-design.md` spec adds 16 of them. Once those exist, a
doc-sync job comparing each README's fenced `bash` blocks against its suite is a natural
follow-on and the layout above leaves room for it (`tools/qs-tester/docsync/`). It is
deliberately not built now — there is nothing to check against.

## Open items requiring a decision or access

Three things this design depends on but cannot settle from the repository alone. None blocks
writing the harness; all three block the first green scheduled run.

1. **`DIAGRID_API_KEY` secret.** No workflow in the repository references a Diagrid API key
   today, so the secret has to be created in the `shared-production` environment and its name
   confirmed. A CI-scoped key, not a personal one.
2. **Catalyst quota.** The design holds at two concurrent ephemeral projects, each with a
   managed KV store, a pub/sub broker, a workflow engine, and a second KV store. Confirm that
   two fits inside the account limits. If even two is too many, `max-parallel: 1` serialises
   the legs and changes nothing else in the design, at roughly four times the wall-clock of an
   unconstrained matrix.
3. **`invocation/python/venv/`.** The checked-in Python 3.9 virtualenv likely has to be
   removed before the python invocation leg can build. Confirm whether anything depends on it.

## Implementation order

1. `tools/qs-tester/` skeleton: `pyproject.toml`, `resources/catalyst.resource` with the
   ported teardown keyword, `variables/quickstarts.py` with the matrix and markers.
2. `state/tests/quickstart.robot` — the simplest API, single app, four HTTP steps. Get one
   language green locally end to end, then the other three.
3. `invocation/tests/quickstart.robot`, then `pubsub/tests/quickstart.robot` — two-app
   quickstarts, and pubsub is where the log assertion earns its place.
4. `workflow/tests/quickstart.robot` — the polling status loop and the `--app-id` java
   special case.
5. `ci/*.sh` scripts.
6. `.github/workflows/e2e-quickstarts.yml`, initially `workflow_dispatch` only.
7. Run each language leg by hand, do the deliberate-break check, then enable the schedule.

Steps 2-4 each end with a green local run for all four languages before moving on.

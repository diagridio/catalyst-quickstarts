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
have one. `workflow/java/README.md` therefore documents the `--app-id` form rather than `-f`,
and the suite follows it.

**Application log destination is already correct.** Every `*-quickstart.yaml` sets
`appLogDestination: console`, so application stdout is merged into the `diagrid dev run`
console stream. Capturing that one stream per suite captures every app's log output — which
is what makes log assertions possible without extra plumbing.

## Source of truth: the per-language READMEs

Each of the 16 directories now has a `README.md` with a fixed seven-section structure
(prerequisites, log in, clone, install, run, exercise the API, clean up), added by the work
described in `2026-07-28-quickstart-readmes-design.md`. **Those READMEs define what the tests
do**: the prerequisites determine what CI provisions, and sections 4 through 7 determine the
commands each suite runs and the responses it asserts.

This is the whole point of the exercise. A test that runs commands nobody documented proves
only that some code path works; a test that runs the documented commands and asserts the
documented responses proves that a user following the README will succeed.

Consequences worth stating up front, because they change the earlier draft of this design:

- **The order ID is `1`, not `4`.** Every README uses `{"orderId":1}`. The `test.rest` files
  use `4` for state, and the state README explicitly notes the discrepancy. The suites follow
  the README.
- **Expected response bodies are documented exactly** for state, pubsub, and invocation, and
  they diverge between languages. The suites assert the documented body per language rather
  than a loose substring.
- **Install commands are per-(API, language), not per-language.** `workflow/csharp` documents
  `dotnet build` while `state/csharp` documents `dotnet restore`.
- **Readiness has a documented signal.** The pubsub and invocation READMEs tell the user to
  wait for `Connected App ID "<appID>" to localhost:<port>` in the `diagrid dev run` output.
- **The documented flow is narrower than the API surface, and the suites stop where the docs
  stop.** No state README documents `DELETE /order/{id}`, and no workflow README documents
  `POST /workflow/terminate/{id}`, so neither is tested even though both exist in every
  implementation and every `test.rest`. See "The suites test the documented flow and nothing
  more" below.

`test.rest` remains a secondary reference — useful for confirming an endpoint exists, not for
deciding what a test asserts.

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
│   └── quickstarts.py        # per-(api, language) matrix, expected bodies, log markers
├── docsync/
│   └── check_readme_sync.py  # assert each README's commands match its suite
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

1. **Build** — the README's section 4 install command for that directory (matrix below).
2. **Start** — the README's section 5 run command, as a background process, stdout+stderr to a
   per-suite log file. The log file is truncated first so a stale file cannot satisfy an
   assertion.
3. **Wait until ready** — the documented readiness signal, then an HTTP health check
   (below).
4. **Assert** — the documented HTTP responses, then the log markers.
5. **Teardown** — stop the process tree (the README's CTRL+C), then `diagrid dev stop`,
   unconditionally.

### Install commands, verbatim from README section 4

These are per-(API, language), not per-language — `workflow/csharp` documents `dotnet build`
where `state/csharp` documents `dotnet restore`, and the python variants differ in all three
respects. Reading them off a per-language rule would silently run something the docs never
told a user to run.

| Directory | Documented install command |
|---|---|
| `workflow/csharp` | `dotnet build` |
| `workflow/java` | `mvn clean install` |
| `workflow/javascript` | `npm install` |
| `workflow/python` | `uv sync` |
| `state/csharp` | `dotnet restore` |
| `state/java` | `mvn clean install` |
| `state/javascript` | `npm install` |
| `state/python` | `uv venv` + activate, then `uv sync` |
| `pubsub/csharp` | `dotnet restore ./publisher && dotnet restore ./subscriber` |
| `pubsub/java` | `mvn clean install -f ./publisher && mvn clean install -f ./subscriber` |
| `pubsub/javascript` | `npm install --prefix ./publisher && npm install --prefix ./subscriber` |
| `pubsub/python` | `uv venv` + activate, then `uv sync --active --directory publisher && uv sync --active --directory subscriber` |
| `invocation/csharp` | `dotnet restore ./client && dotnet restore ./server` |
| `invocation/java` | `mvn clean install -f ./client && mvn clean install -f ./server` |
| `invocation/javascript` | `npm install --prefix ./client && npm install --prefix ./server` |
| `invocation/python` | `uv venv` + activate, then `uv sync --active --directory client && uv sync --active --directory server` |

### Run commands, verbatim from README section 5

Fourteen of the sixteen are the same shape:

```
diagrid dev run -f <api>-quickstart.yaml --project $PROJECT --approve
```

Two documented exceptions:

```
# workflow/python — README prefixes uv run
uv run diagrid dev run -f workflow-quickstart.yaml --project $PROJECT --approve

# workflow/java — no dev config file exists, so the README uses the --app-id form
diagrid dev run --project $PROJECT --app-id order-workflow --approve -- mvn spring-boot:run
```

The `--project` value is the one deliberate substitution: the READMEs document
`--project workflow-quickstart` and friends, but parallel language legs need distinct
projects, so the harness passes its ephemeral project name. Nothing else about the command
is rewritten.

**The three python `uv venv` + activate cases matter more than they look.** `state/python`,
`pubsub/python`, and `invocation/python` document activating a virtual environment and then
running a bare `diagrid dev run` — no `uv run` prefix. The harness therefore has to launch
these through a shell wrapper (`bash -c 'source .venv/bin/activate && diagrid dev run …'`).
That wrapper is exactly the situation track-tester's teardown comments describe, where
`diagrid`, its sidecar, and the app land in process groups the wrapper's own group signal
cannot reach. It is the concrete reason the PID-tree kill fallback is not optional.

### Readiness

The pubsub and invocation READMEs give a precise signal, and the suites use it:

| README | Documented readiness log |
|---|---|
| pubsub (all 4) | `Connected App ID "publisher" to localhost:5001` and `Connected App ID "subscriber" to localhost:5002` |
| invocation (all 4) | `Connected App ID "server" to localhost:5002` |
| workflow, state (all 8) | prose only — "wait a few seconds until you see application logs" |

Waiting on `Connected App ID "<appID>" to localhost:<port>` is better than an HTTP health
poll alone, because it confirms the Catalyst side of the connection is established and not
merely that a local port is listening. It is also a line `diagrid dev run` emits for every
app, so the suites use it for all four APIs — including the eight whose READMEs only say
"wait a few seconds", which is not something a test can act on.

After the readiness marker, each suite still polls `GET http://localhost:<port>/` until 200
per app, with a 180s timeout. Two gates rather than one: the marker proves Catalyst
connected the appID, the health check proves the app itself is serving. JVM and .NET cold
starts on a CI runner are slow enough that the gap between the two is real.

## Assertion matrix

Each test asserts the HTTP contract **and** the application log output. Two independent
signals: HTTP proves the endpoint answers correctly, logs prove the work actually happened
inside the app and, for pubsub, that the message reached the other process at all.

Log assertions use `Wait Until Log Contains` (poll the captured `diagrid dev run` stream
every 2s until the marker appears or the timeout expires), because app logging is
asynchronous with respect to the HTTP response.

### state — one app on port 5001

README section 6 documents two steps, 6.1 store and 6.2 retrieve, both with exact expected
bodies.

| Step | HTTP | Log marker |
|---|---|---|
| `POST /order {"orderId":1}` | 201, body per language below | `Save state item successful.` |
| `GET /order/1` | 200, body per language below | `Get state item successful. Order retrieved` |

The documented bodies diverge across languages in both steps:

| Language | 6.1 store response | 6.2 retrieve response |
|---|---|---|
| Python | `{"id":1,"message":"Order created successfully"}` | `{"data":"orderId=1"}` |
| .NET | `{"id":1,"message":"Order created successfully"}` | `{"data":{"orderId":1}}` |
| JavaScript | `{"id":1,"message":"Order created successfully"}` | `{"data":{"orderId":1}}` |
| Java | `{"orderId":1,"message":"Order created successfully"}` | `{"data":{"orderId":1},"message":""}` |

Java names the store-response id field `orderId` where the other three use `id`, and its
retrieve response carries an extra empty `message`. Python's retrieve response is a *string*
`"orderId=1"` rather than a nested object, because that implementation saves the string form
of its model — the README calls this out explicitly.

Both log markers are language-invariant substrings. `Save state item successful.` stops at
the period because python continues `Order saved with key: 1 and value: ...` where the other
three continue `Order saved: 1`.

### invocation — client on 5001, server on 5002

| Step | HTTP | Log marker |
|---|---|---|
| both apps ready | readiness marker, then 200 on `GET /` for each | — |
| `POST /order {"orderId":1}` on client | 200, body exactly as documented | server: `Invocation received with data` |
| | | client: per-language, see below |

The documented response body is identical in all four languages — the only API where that is
true:

```json
{"message":"Invocation successful","orderId":1,"targetApp":"server"}
```

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
| both apps ready | readiness marker, then 200 on `GET /` for each | — |
| `POST /order {"orderId":1}` on publisher | 201, body per language below | publisher: `Order published: 1` |
| message delivered to subscriber | — (no HTTP surface) | subscriber: per-language, see below |

The documented publish response differs in one detail — java returns the id as a **string**:

| Language | Documented publish response |
|---|---|
| Python | `{"id":1,"message":"Message published successfully","topic":"orders"}` |
| .NET | `{"id":1,"message":"Message published successfully","topic":"orders"}` |
| JavaScript | `{"id":1,"message":"Message published successfully","topic":"orders"}` |
| Java | `{"id":"1","message":"Message published successfully","topic":"orders"}` |

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

README section 6 documents two steps, 6.1 start and 6.2 get status.

| Step | HTTP | Log marker |
|---|---|---|
| `POST /workflow/start {"name":"Car", "quantity":2}` | 200, extract instance id | `Received order <instanceId> for 2 Car` |
| workflow runs to completion | — | `Order <instanceId> has completed!` |
| `GET /workflow/status/<id>` | 200, non-empty body; python additionally `"isWorkflowCompleted":true` | — |

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

**The completion gate is the log marker, not the status JSON.** This is a deliberate choice,
and the READMEs make the case for it more strongly than the source did.

Only `workflow/python`'s README documents the status response concretely, and what it
documents is:

```json
{"exists":true,"isWorkflowRunning":false,"isWorkflowCompleted":true,
 "createdAt":"<DATE_TIME>","lastUpdatedAt":"<DATE_TIME>",
 "runtimeStatus":1,"failureDetails":null}
```

`"runtimeStatus":1` — a **numeric** enum. The other three READMEs describe the body in prose
only ("the runtime status reads as completed") without showing it. So a substring check for
`COMPLETED` on the status body, which an earlier draft of this design specified, would simply
fail against python, and cannot be confirmed for the other three from any documented source.
Structurally the responses also diverge: python returns a hand-built object, java the
serialized `WorkflowInstanceStatus`, .NET a `{state, result}` pair, javascript the raw SDK
`WorkflowState`.

Gating on `Order <instanceId> has completed!` avoids all of that. It is invariant across all
four languages, needs no JSON path, and is the stronger assertion — it proves the activity
chain ran, whereas a status field only reports what the engine recorded. The status endpoint
is still called and asserted, but only for what is actually documented: HTTP 200 with a
non-empty body, plus `"isWorkflowCompleted":true` for python where the README states it.

Tightening the other three to a specific field is deliberately left for implementation, when
real responses can be observed rather than guessed. This is also a documentation gap worth
fixing separately: three of the four workflow READMEs describe a response body they never
show, and python's shows a numeric status where the prose says "completed".

That leaves exactly one per-language accessor:

| Language | Documented start response |
|---|---|
| Python | `{"instanceId":"<YOUR_INSTANCE_ID>"}` |
| .NET | `{"instanceId":"<YOUR_INSTANCE_ID>"}` |
| Java | `{"instanceId":"<YOUR_INSTANCE_ID>","errorMessage":null}` |
| JavaScript | `{"instance_id":"<YOUR_INSTANCE_ID>"}` |

`instance_id` in javascript against `instanceId` in the other three is real drift, documented
as such in the READMEs — the javascript README even tells the user that `test.rest`'s variable
will not resolve because of it. The test records the key as a variable rather than papering
over it, so it shows up in review.

### The suites test the documented flow and nothing more

Two endpoints exist in every implementation and every `test.rest`, but no README documents
them, and the suites therefore do not touch them:

| Endpoint | Status |
|---|---|
| `DELETE /order/{id}` (state) | Not documented, not tested |
| `POST /workflow/terminate/{id}` (workflow) | Not documented, not tested |

This is a deliberate boundary. The suites exist to prove that a user following a README
succeeds; the README is the specification, and testing past it would mean the suites and the
docs disagree about what the quickstart is.

The tradeoff is real and worth naming: a regression in either endpoint ships silently. Neither
is on the documented path, so no user following the docs would hit it, but both are in code
users read. The fix is to document them — add a delete step to the four state READMEs and a
terminate step to the four workflow READMEs — after which the suites pick them up as
documented steps and this gap closes on its own. Until then it stays open by choice.

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
  pull_request:                         # lint job only — no credentials, fork-safe

concurrency: {group: e2e-quickstarts, cancel-in-progress: false}

env:
  DIAGRID_CLI_VERSION: '<pinned>'      # workflow-wide, not a credential

jobs:
  lint:    # runs on PRs and on schedule — no credentials, fork-safe
    uv sync
    robot --dryrun (all 4 suites)              # resolves syntax, keywords, variables
    check_readme_sync.py (all 16 READMEs)      # README commands match the suites

  reap:    # schedule only
    env: {DIAGRID_API_KEY: ...}
    delete qs-ci-* projects older than 6h

  e2e:
    if: github.repository_owner == 'diagridio'
    environment: shared-production
    timeout-minutes: 60
    env:
      DIAGRID_API_KEY: ...             # job-level, so every step and script sees it
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

- **Toolchain versions come from README section 1**, and agree with the code: the READMEs list
  .NET 10.0, Java 17+ with Maven 3.9.5+, Node.JS LTS, and Python 3.12+ with uv; the repository
  has `net10.0` in every csproj, `<java.version>17</java.version>` in every pom, and
  `requires-python = ">=3.12"` in every pyproject. The prerequisite lists are identical across
  all four APIs for a given language, so the runtime setup is per-matrix-leg, not per-suite.
  `ubuntu-latest` already ships a Maven newer than 3.9.5, so no explicit Maven step is needed.
- **Dependency pre-warming runs outside the timed Robot keywords.** track-tester learned this
  the hard way: on a cold `~/.m2` the dependency download alone exceeded the build timeout
  and the build was killed mid-download. The timed step should only compile.
- **The per-API loop uses the `if !` guard** so a failure in one API still lets the remaining
  three run. One nightly run then reports every broken API for that language, not just the
  first. The leg fails at the end if any API failed.
- **`pull_request` triggers only `lint`.** The e2e job needs `DIAGRID_API_KEY`, which will not
  be populated for fork PRs, and real Catalyst projects per PR would be wasteful regardless.
  `--dryrun` and doc-sync still run on every PR, and between them catch broken keyword
  references, typos in suite files, and README edits that the suites have not followed.
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

## Configuration

Both values reach the harness as **environment variables**, in CI and locally alike:

| Name | Purpose |
|---|---|
| `DIAGRID_API_KEY` | authenticates `diagrid login` |
| `DIAGRID_CLI_VERSION` | pins the CLI so a CLI release cannot silently change behaviour |

`ci/setup-project.sh` reads `DIAGRID_API_KEY` from the environment and passes it to the CLI
explicitly:

```bash
diagrid login --api-key "$DIAGRID_API_KEY"
```

**The CLI does not read `DIAGRID_API_KEY` itself** — `diagrid login` accepts only the
`--api-key` flag, with no documented environment fallback. Exporting the variable without
passing the flag would silently attempt an interactive browser login and hang in CI. The
explicit flag is required.

The script fails fast with a clear message if the variable is unset or empty, rather than
letting the CLI fall through to an interactive login.

Locally the same variable makes a single leg reproducible with no extra setup:

```bash
export DIAGRID_API_KEY=...
bash tools/qs-tester/ci/setup-project.sh
(cd tools/qs-tester && uv run robot --include python ../../state/tests/quickstart.robot)
```

In GitHub Actions the workflow sets it at job level from the repository's configured value.
The job keeps `environment: shared-production`, matching the 16 existing workflows.

## Verification

The harness is itself testable, and its correctness is established in four layers:

1. **`robot --dryrun` on all four suites** resolves every keyword and variable without
   starting anything. Runs on every PR.
2. **`check_readme_sync.py` on all 16 READMEs** confirms the suites still run what the docs
   say. Also on every PR, and it is the layer that catches a README edit.
3. **A single leg run locally** against a real Catalyst project, for each of the four
   languages, before the workflow is enabled on a schedule. This is the step that confirms
   every log marker in this spec actually appears in the captured stream — the markers were
   read from source, and reading source is not the same as observing output. It is also where
   the three undocumented workflow status bodies get observed and, if they turn out stable,
   asserted more tightly.
4. **A deliberate-break check**: point one marker at a string the app does not log and
   confirm the suite fails rather than passing vacuously. Log assertions that silently never
   match are the main failure mode of this design, and a green run proves nothing until this
   check has been done once per API.

## Known issues found while designing, not fixed here

These are real and worth separate PRs. They are out of scope; fixing quickstart source in a
test-only change would be the wrong bundle.

- **`pubsub/python/publisher/main.py`** catches `grpc.RpcError` without importing `grpc`,
  so the error path raises `NameError` instead of returning a 500.
- **`state/java` expects `kvstore` while the other three expect `statestore`.** Worked around
  in CI by provisioning both; the inconsistency remains in the repository.
- **`state/javascript` keys on `order<id>`** (`order1`) where python, java, and .NET key on
  the bare id (`1`). The tests do not notice, because every call goes through the app's own
  API and is self-consistent. A user following the README's console-explorer step will see a
  differently named key in javascript than in the other three languages.
- **`workflow/javascript` returns `instance_id`** where the other three return `instanceId`.
- **`workflow/java` has no `workflow-quickstart.yaml`**, unlike the other three languages.
- **`state/java` names its store-response field `orderId`** where python, javascript, and .NET
  name it `id`, and its retrieve response carries an extra empty `message`. Documented in the
  READMEs, so the tests assert it as-is.
- **`pubsub/java` returns the published id as a string** (`{"id":"1"}`) where the other three
  return a number.
- **Three of four workflow READMEs never show the status response body**, describing it in
  prose as "reads as completed". Python's shows `"runtimeStatus":1` — a numeric enum, so the
  prose and the payload do not visibly agree. This is why the completion gate is a log marker.
- **`test.rest` uses order ID `4` for state while the READMEs use `1`.** Harmless, and the
  state README calls it out, but the two would ideally agree.
- **`DELETE /order/{id}` and `POST /workflow/terminate/{id}` are undocumented** though present
  in every implementation and every `test.rest`, and are consequently untested. Documenting
  them in the eight relevant READMEs is what brings them under test.
- **Log wording diverges across languages** for the same operation — capital-S `Publish
  Successful` in .NET, `Invoke Successful. Response received` in java's invocation client, a
  missing colon in java's invocation server. Harmonising these would let the marker table
  collapse to invariants only.

## doc-sync

Now that the READMEs exist, the check that catches *documentation* drift rather than runtime
drift is in scope. This is track-tester's `docsync/check_doc_sync.py` idea applied to READMEs:
assert that what a README tells a user to do is what the suite actually does.

`tools/qs-tester/docsync/check_readme_sync.py` takes a README and its suite's variables entry
and asserts four things for that directory:

| Extracted from README | Compared against |
|---|---|
| section 4 fenced `bash` block(s) | the install command in `variables/quickstarts.py` |
| section 5 fenced `bash` block | the run command, modulo the `--project` substitution |
| section 6 `curl` URLs, methods, and `-d` payloads | the endpoints and payloads the suite calls |
| section 6 fenced `json` expected bodies | the expected bodies the suite asserts |

It is a **presence and equality check on strings**, not a proof of execution — the same
limitation track-tester documents. Its job is catching the day someone edits a README command
or an expected body without touching the suite, which is the most likely way these two drift
apart.

Three deliberate exclusions:

- **PowerShell blocks are ignored.** Every request in every README is given three ways
  (curl, PowerShell, REST Client). The suites use one. Requiring coverage of all three would
  mean asserting the same call three times.
- **The `--project` value is normalised before comparison**, since the harness substitutes its
  ephemeral project name for the documented `<api>-quickstart`. This is the one sanctioned
  divergence and the checker knows about it explicitly rather than by fuzzy matching.
- **The check runs one way only:** every documented command must be covered by the suite, not
  the reverse. The suites legitimately do things no README describes — poll a health endpoint,
  wait for the readiness marker, create and delete the ephemeral project — and a bidirectional
  check would flag all of it. Since the suites now assert nothing beyond the documented API
  calls, a reverse check would mostly pass, but it would couple the harness's internal steps to
  the docs for no benefit.

It runs in the `lint` job, so it fires on every PR without needing credentials or a Catalyst
project — cheap, fast, and exactly the check most likely to catch a README edit.

## Settled prerequisites

The three items this design was blocked on are resolved. Recorded here so the implementation
does not have to re-ask.

1. **`DIAGRID_API_KEY` is supplied as an environment variable**, locally and in GitHub Actions.
   No `secrets.*` plumbing in the harness; the scripts read the variable and pass
   `--api-key "$DIAGRID_API_KEY"` to the CLI, which has no environment fallback of its own.
2. **Two concurrent Catalyst projects is within limits**, so `max-parallel: 2` stands as
   designed. No fallback to serial execution needed.
3. **`invocation/python/venv/` is already removed on `main`.** Verified against `origin/main`;
   the directory is gone and `.gitignore` covers `.venv`, which is the directory name
   `uv venv` actually creates. That matters for the three python legs that create a virtual
   environment during the run — they cannot dirty the working tree or leak into an artifact.

## Implementation order

1. `tools/qs-tester/` skeleton: `pyproject.toml`, `resources/catalyst.resource` with the
   ported teardown keyword, `variables/quickstarts.py` populated **by reading all 16 READMEs**
   — install command, run command, endpoints, payloads, expected bodies, markers.
2. `state/tests/quickstart.robot` — the simplest API, single app, two documented steps. Get one
   language green locally end to end, then the other three.
3. `invocation/tests/quickstart.robot`, then `pubsub/tests/quickstart.robot` — two-app
   quickstarts, and pubsub is where the log assertion earns its place.
4. `workflow/tests/quickstart.robot` — the log-marker completion gate, the per-language start
   response key, and the `--app-id` java special case.
5. `docsync/check_readme_sync.py`, written after the variables file exists so it has something
   real to compare against. Run it against all 16 READMEs immediately; any mismatch it reports
   at this point is a bug in step 1's transcription, which is exactly what it is for.
6. `ci/*.sh` scripts.
7. `.github/workflows/e2e-quickstarts.yml`, initially `workflow_dispatch` only.
8. Run each language leg by hand, observe the three undocumented workflow status bodies, do the
   deliberate-break check, then enable the schedule.

Steps 2-4 each end with a green local run for all four languages before moving on.

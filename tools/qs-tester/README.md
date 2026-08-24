# qs-tester

End-to-end tests for the `workflow`, `state`, `pubsub`, and `invocation` quickstarts,
built on [Robot Framework](https://robotframework.org/). The tests run the *actual*
commands each quickstart's README documents and assert the responses and log output
that README promises, so drift between the docs, the code, and Catalyst is caught
automatically.

Design: `docs/superpowers/specs/2026-07-28-quickstart-e2e-tests-design.md`.

## Layout

- `resources/process.resource` — background process lifecycle and PID-tree teardown.
- `resources/catalyst.resource` — `diagrid dev run` launch, stop, readiness markers.
- `resources/quickstart.resource` — build, health polling, HTTP assertions.
- `resources/tests/` — the harness's own tests. `smoke.robot` covers the
  process-teardown keywords, `readiness.robot` covers the readiness gate against
  `flaky_server.py`, `teardown.robot` covers the two Stop Quickstart paths that
  release nothing. None need credentials, they run in seconds, and CI's `lint` job
  runs the whole directory on every PR — run them locally too when you touch
  `process.resource`, `catalyst.resource` or the gate.
- `variables/quickstarts.py` — the per-(API, language) table. **Everything in it is
  transcribed from a README.** Change a README, change this file.
- `docsync/check_readme_sync.py` — asserts the two stay in agreement.
- `ci/` — Catalyst project lifecycle scripts.

Each suite lives next to the quickstarts it tests: `state/tests/quickstart.robot`,
`pubsub/tests/quickstart.robot`, and so on. Each has four tests tagged `csharp`,
`java`, `javascript`, `python`.

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

### Checks that need no Catalyst project

```bash
cd tools/qs-tester

# resolve syntax, keywords and variables without running anything
uv run robot --dryrun --variable PROJECT:dryrun ../../*/tests/quickstart.robot

# assert the READMEs and the harness still agree
uv run python docsync/check_readme_sync.py --all

# unit-test the doc-sync checker itself
uv run pytest docsync/tests -q

# the harness's own keyword tests, no Catalyst project or credentials needed
uv run robot resources/tests
```

The glob in the dryrun command resolves from `tools/qs-tester/` to exactly the four
suites in this repo (`../../workflow/tests/quickstart.robot`, `state`, `pubsub`,
`invocation`) — there is no other `tests/quickstart.robot` anywhere else in the tree.
If a future quickstart directory adds a fifth `tests/quickstart.robot` that is not
meant to be part of this run, switch to the explicit four paths CI's `lint` job
uses instead of the glob.

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
  see the design spec's assertion matrix for why each is truncated where it is.
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
  The other three suites have been verified only with `robot --dryrun` (syntax,
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
- Three things in particular remain unproven and matter most:
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

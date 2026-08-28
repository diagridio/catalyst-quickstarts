# Agent-family quickstarts: `agents/*`, `dapr-agents/*`, `mcp-auth/*`

One language each, a prose README with named sections (not `## 4.`/`## 5.`
numbers), an LLM key requirement, and self-documented provisioning. Everything
below is grounded in the one suite that actually exists,
`tools/qs-tester/variables/agents_langgraph.py` and
`agents/langgraph/tests/quickstart.robot`, plus the READMEs of quickstarts that
have no suite yet but that this reference uses as worked examples of shapes
`langgraph` does not need. Read the real files before copying anything here —
this document describes them, it does not replace them.

## The data module contract

A new agent-family suite gets its own module,
`tools/qs-tester/variables/agents_<name>.py` (or `dapr_agents_<name>.py`,
`mcp_auth_<name>.py` — match the family), holding these names:

| Name | Shape | Meaning |
|---|---|---|
| `DOCUMENTED_PROJECT` | `str` | The project name the README shows, e.g. `"langgraph-quickstart"`. Used to map documented commands onto `{project}` when comparing against the harness. |
| `SETUP` | `tuple[str, ...]` | The README's own provisioning commands, in order, with `{project}` substituted for the documented name. Empty if the README documents none (see "Undocumented provisioning" below). |
| `INSTALL` | `str` or `tuple[str, ...]` | The install command(s) from the README's setup section. |
| `RUN` | `str` | The `dev run` command, verbatim except for `{project}` where the README documents one. Left bare (no `--project`) where the README's `dev run` is bare — see "Documented provisioning differs by family" below. |
| `TEARDOWN` | `tuple[str, ...]` | The README's own cleanup commands. Empty if the README documents none. |
| `READY_MARKERS` | `tuple[str, ...]` | One string per app that announces itself in the `diagrid dev run` output. |
| `HEALTH_PROBES` | `tuple[tuple[int, str], ...]` | `(port, path)` pairs `Wait Until Apps Healthy` polls for a 200 before any assertion runs. The path is per app and must be a route the app actually serves — see "Probe a path the app really serves" below. |
| `CATALYST_PROBE_MARKERS` | `tuple[str, ...]` | Strings that appear in the captured `diagrid dev run` output once Catalyst has attached to the app and probes it back through the tunnel — `Wait Until Catalyst Attached` waits for each before any documented request runs. Guards the window in which a workflow call **hangs unrecoverably**. Like `READY_MARKERS`, this is whatever the app's own logging makes visible for an *inbound* request, so it is a property of the framework, not of Catalyst. Empty is legal and means "not observed for this quickstart"; see "The Catalyst-attach gate" below. |
| `CONNECTED_APPS` | `tuple[tuple[str, int], ...]` | `(appID, port)` pairs `diagrid dev run` reports as `Connected App ID "<id>" to http://localhost:<port>`. Required: `Start Quickstart` records these so `Stop Quickstart` can release each local app connection, and a run that skips this leaves a `trust.diagrid.io` endpoint pointing at a dead tunnel, which makes the next run's 500s ambiguous. See `variables/agents_langgraph.py`'s `CONNECTED_APPS` for the worked example, read from the dev config and confirmed against the 2026-08-27 live run — `diagrid dev run` does print the line for an agent app. Note what it does not prove: the line means the local dev tunnel is up, not that Catalyst can route the app's workflow calls, which is what `CATALYST_PROBE_MARKERS` is for. |
| `SECRETS` | `tuple[str, ...]` | Environment variable names the suite's `Require Env Var` loop checks before doing anything else — the model provider keys. |
| `REQUESTS` | `tuple[dict, ...]` | The documented trigger calls, in documented order. Keys below. |
| `UNCOVERED` | `tuple[tuple[str, str], ...]` | `(documented command, reason)` pairs for commands the suite deliberately does not run. |
| `get_quickstart()` | function | Returns one flat dict: `family`, `name`, `language`, `dir`, `setup`, `install`, `run`, `teardown`, `health_probes`, `connected_apps`, `catalyst_probe_markers`, `secrets`. Not identical to what `quickstarts.get_quickstart(api, language)` returns (that one has `api` instead of `family`/`name`/`setup`/`teardown`/`secrets`) — the two dicts share exactly the five keys the *shared* keywords actually read (`dir`, `install`, `run`, `health_probes`, `connected_apps`), which is what lets `Build Quickstart`, `Start Quickstart` and `Wait Until Apps Healthy` work unchanged against either shape. Both dicts do carry a `language` key of their own (this module's `LANGUAGE` constant; the canonical dict's `language` argument), but no shared keyword reads either one, which is why `language` is not in the shared five — see `agents_langgraph.get_quickstart`'s docstring. |

### What doc-sync actually enforces — and what it does not

`docsync/check_readme_sync.py::check_agent` reads a fixed list of required
attributes, `_REQUIRED_MODULE_ATTRS`:

```
DOCUMENTED_PROJECT, SETUP, INSTALL, RUN, TEARDOWN, READY_MARKERS, REQUESTS,
UNCOVERED, CONNECTED_APPS, HEALTH_PROBES, CATALYST_PROBE_MARKERS
```

If your module is missing one of those eleven names, `check_agent` returns it as a
problem string (`"... is missing required attribute(s): ..."`) — a normal
doc-sync failure, not a crash, so one bad module costs its own row and not the
other suites `--all` also checks in the same run. The list is checked for
agent-family suites only: `check_agent` runs from `--all` over
`suites.agent_suites()`, and the canonical suites are checked against
`variables/quickstarts.py` instead.

The last three are there for a different reason than the first eight.
`check_agent` does not read `CONNECTED_APPS`, `HEALTH_PROBES` or
`CATALYST_PROBE_MARKERS` at all — `get_quickstart()` does, and the `.resource`
files then index `${qs}[connected_apps]` (`Wait Until Apps Connected`),
`${qs}[health_probes]` (`Wait Until Apps Healthy`) and
`${qs}[catalyst_probe_markers]` (`Wait Until Catalyst Attached`). Omit any of them and nothing static complains unless doc-sync requires it;
the failure surfaces as a `NameError` inside `get_quickstart()` itself — the
test's first keyword, before `diagrid project create` runs, so no cloud project
is spent. (The genuine `KeyError` shape — the attribute exists but
`get_quickstart()` drops it from the returned dict — is a different failure
this guard still does not catch.) Empty is legal for all three
(`agents/spring-ai/event-planner` has `HEALTH_PROBES = ()` and
`CATALYST_PROBE_MARKERS = ()`); absent is not.

Note what is still **not** in the list: `SECRETS` and `get_quickstart`. A module
missing either fails at Robot runtime instead (the `Require Env Var` loop has
nothing to iterate, or `Get Quickstart` is not a keyword), so do not skip them
just because doc-sync will not complain. Nothing static can check that a probe
*path* is real either — that one is on you, see below.

Beyond presence, `check_agent` cross-checks values against the README:

- Every command in `SETUP`, every `INSTALL` line, `RUN`, every `TEARDOWN` command,
  and every command inside any `REQUESTS[i]["commands"]` must appear literally in
  the README (modulo the `{project}`/documented-name substitution) — this is the
  `harness -> documented` direction.
- Every bash line the README documents must be either one of those harness
  commands or listed in `UNCOVERED` with a reason — `documented -> harness`. A
  README that grows a new documented step fails this until someone decides
  whether the suite should run it.
- Every `READY_MARKERS` string must appear in the README text.
- Every `REQUESTS[i]["path"]`, assembled into `http://localhost:<port><path>`,
  must appear in the README, and if `payload` is not `None` it must match one of
  the payloads the README's curl blocks document.
- Every `REQUESTS[i]["log_marker"]`, where given, must appear in the README.

`check_agent` reads the whole file for bash blocks (`all_bash_lines`), not
numbered sections — agent-family READMEs have none. Backslash-continued lines
(the documented curl calls) are joined first, so a wrapped call is compared as
one line, not three fragments that would never match.

### Lines the README documents that are never expected to match a harness command

`_NOT_COMMANDS` in `check_readme_sync.py` is a prefix tuple of documented lines
that are legitimately exempt from `documented -> harness`, with the reason each
is not a command the suite runs:

| Prefix | Why it is exempt |
|---|---|
| `cd ` | The harness passes `cwd=` to the process instead of running `cd`. |
| `diagrid login` | One of the two sanctioned exceptions — CI runs `diagrid login --api-key "$DIAGRID_API_KEY"` instead, because the bare documented form blocks on a browser prompt. |
| `export ` | Secrets arrive as environment variables from the CI job's `env` block, so the documented `export FOO=...` has no harness equivalent to match against. |
| `curl` | Checked a different way — as a URL plus a parsed JSON payload (`REQUESTS[i]["path"]`/`["payload"]`), not as a shell string, because the README documents the same call three ways (curl, PowerShell, REST client) and only one of those is a bash line. |

Do not add a new prefix here to make a stubborn mismatch go away. If a documented
line does not fit one of these four reasons, it needs a real harness command or
an `UNCOVERED` entry.

### Why `READY_MARKERS` and `REQUESTS` come from the `Variables` import, not `get_quickstart()`

The suite settings section imports the data module twice:

```robotframework
Variables       ../../../tools/qs-tester/variables/agents_langgraph.py
Library         ../../../tools/qs-tester/variables/agents_langgraph.py
```

`Variables` exposes the module's top-level names directly as Robot variables
(`@{REQUESTS}`, `@{READY_MARKERS}`). `Library` exposes `get_quickstart` as a
keyword. The suite deliberately reads `@{READY_MARKERS}` and `@{REQUESTS}` from
the `Variables` import rather than out of the dict `Get Quickstart` returns —
`get_quickstart()`'s dict has no `ready_markers` or `requests` key at all (it
returns `family`, `name`, `language`, `dir`, `setup`, `install`, `run`,
`teardown`, `health_probes`, `secrets` only, per the contract table above).

The reason is the mutation check (see the harness README's "To prove an
assertion is not vacuous..."): it re-runs the suite with `robot --variablefile`
pointing at a one-line generated file that redefines `READY_MARKERS`. A
`--variablefile` value outranks a suite's own `Variables` import, so this
actually replaces what the suite reads — but it cannot touch anything a Python
keyword computed and returned at run time. If the suite instead read
`${qs}[ready_markers]` from `Get Quickstart`, the mutation check would override
the module-level `READY_MARKERS` tuple, `get_quickstart()` would still return the
real value inside `${qs}`, the suite would wait for the real marker, and the
"broken" run would pass — proving nothing. Keep this split. There is no
`activate_venv` key or anything like it in `get_quickstart()`'s dict; do not add
one on a hunch that a Python-run quickstart needs it — `uv run` puts `.venv/bin`
on `PATH` for the duration of the command, so nothing needs activating.

For the same scalars-only reason, the mutation check's override always goes
through a generated `--variablefile`, never `--variable`: `--variable` can only
set a scalar, and the two things worth breaking, `READY_MARKERS` and `REQUESTS`,
are tuples.

## `REQUESTS`: required and optional keys

Each entry is a dict:

Required: `method`, `port`, `path`, `payload`, and `status` — unless the request
carries `expect`, which replaces it.
Optional: `field` (default `None`), `commands` (default `()`), `log_marker`
(default `None`), `expect` (default `None`).

`expect` is for a documented request that is not supposed to complete. Its only
value today is `"connection-dropped"`, used by `agents/microsoft-dotnet`, whose
README documents the app killing its own process mid-request ("Call
`step_two_compare` — crashes before completing (process exits)"). The suite then
calls `POST And Expect The App To Exit` instead of `POST And Expect Field`, and
carries no `status`, because there is no status code the app can return. Do not
pair `expect` with a `status`: a status the app cannot produce is exactly the
invented assertion this skill forbids.

`log_marker` must appear **inside a fenced block** in the README, and doc-sync
enforces that. A prose mention is not evidence the app prints anything: this
suite shipped `check_availability` as its marker because the README says "Use the
`check_availability` tool" and `main.py` defines that tool — but `call_tools`
invokes it without logging, so the marker could never match and the suite timed
out against real Catalyst. Pick a string the app really prints, and document it
in a block of that app's output (any fence language: `text`, `console` or
untagged). `READY_MARKERS` is deliberately exempt — `agents/langgraph` documents
`Uvicorn running on` as inline code in a sentence, which is a fine way to
document a readiness marker.

The suite reads optional keys with `Get From Dictionary ... default=...` (or, for
`commands`, `Evaluate    $request.get('commands', ())` — the default has to be an
empty *sequence*; a `${EMPTY}` default is an empty *string*, and `Run Documented
Commands` fails iterating a string with "not list or list-like"). This is why a
request that needs none of the optional keys stays a plain five-key dict instead
of carrying explicit nulls.

Write `status` as a number (`200`), matching every existing module. It reaches
RequestsLibrary through `POST And Expect Field`, which converts it to a string
first — RequestsLibrary raises `InvalidExpectedStatus` for a non-string
`expected_status`, and a Python data module naturally holds an int where the
canonical suites pass a Robot literal (already a string). That conversion lives
in the keyword, not in your module, so there is nothing to remember here; it is
called out only because the missing conversion took a live run to surface —
`resources/tests/keywords.robot` now covers the int path explicitly.

`POST And Expect Field` (see `references/harness-keywords.md`) is what consumes a
request: it asserts the status code always, and — only when `field` is not
`None` — that the named JSON field is present *and* non-empty. It does not
support asserting a field's absence or emptiness; if you need that, choose a
different field to check (see the mcp-auth worked example below) rather than
inventing a new keyword.

### Three shapes, worked from real quickstarts

**One app, one request — `agents/langgraph`, the suite that exists today.**

```python
REQUESTS = (
    {
        "method": "POST",
        "port": 8005,
        "path": "/agent/run",
        "payload": {"task": "Check if the Grand Ballroom is available on March 15th"},
        "status": 200,
        "field": None,   # no README documents a response body for /agent/run,
                          # and it's served by an external package's
                          # DaprWorkflowGraphRunner.serve(), so the field name
                          # cannot be read out of this repo
        "log_marker": "check_availability",
    },
)
```

**Several apps, one documented endpoint — `agents/dapr-agents/orchestrator`
(no suite yet; read the README yourself before writing one).** Its
`dev-multi-agent-orchestration.yaml` declares nine apps, one per agent
framework in the shared event-planning scenario, on ports 8001 through 8009:
`entertainment-planner` (ADK), `venue-scout` (CrewAI), `invitations-manager`
(Dapr Agents), `event-coordinator` (Dapr Agents — the orchestrator itself),
`schedule-planner` (LangGraph), `catering-coordinator` (OpenAI Agents),
`decoration-planner` (Pydantic AI), `budget-planner` (Strands),
`photography-planner` (Claude Agents). The orchestrator's own `main.py` calls
`AgentRunner.serve(orchestrator, port=...)` from the `dapr_agents` package,
whose `serve()` auto-starts uvicorn internally when no app loop is already
running; the other eight apps each live in their own quickstart directory and
are not guaranteed to share that mechanism. All nine would therefore be
expected to print their own `Uvicorn running on` line, so `READY_MARKERS`
needs one entry per app and `HEALTH_PROBES` needs all nine ports — but this
has not been confirmed against a captured log, since no suite runs this
quickstart yet; confirm it against the real `diagrid dev run` output before
trusting it in a live suite. The README documents exactly one HTTP call, `POST
http://localhost:8004/agent/run`, against the orchestrator app itself: the
other eight agents are reached only through the shared agent registry and
pub/sub, never directly over HTTP. So `REQUESTS` still has a single entry even
though nine apps have to come up first:

```python
READY_MARKERS = ("Uvicorn running on",) * 9
# Ports from dev-multi-agent-orchestration.yaml: 8001-8009. The probe PATHS are
# left as a question here on purpose: read each app's routes before filling
# them in (see "Probe a path the app really serves" below) — eight different
# quickstart directories, potentially eight different route sets, and only
# event-coordinator's (8004) has been read for this example.
HEALTH_PROBES = (
    (8001, "<read entertainment-planner's routes>"),
    (8002, "<read venue-scout's routes>"),
    (8003, "<read invitations-manager's routes>"),
    (8004, "<read event-coordinator's routes>"),
    (8005, "<read schedule-planner's routes>"),
    (8006, "<read catering-coordinator's routes>"),
    (8007, "<read decoration-planner's routes>"),
    (8008, "<read budget-planner's routes>"),
    (8009, "<read photography-planner's routes>"),
)
REQUESTS = (
    {
        "method": "POST",
        "port": 8004,
        "path": "/agent/run",
        "payload": {"task": "Plan a company offsite in Austin for 50 people"},
        "status": 200,
        "field": None,
    },
)
```

Do not assume "several apps" implies "several requests" — check what the README
actually shows you triggering.

**CLI interleaved with HTTP — `mcp-auth/python` (no suite yet).** Its README
documents calling the same endpoint twice with a CLI command run in between:
`POST http://localhost:5001/run` first fails closed (deny-all access policy,
every tool call comes back as an in-body error, no grants exist yet), then
`diagrid mcpserver access grant mcp-server --caller mcp-client --allow-tools add
--wait` runs, then the identical `POST /run` succeeds for the granted tool. This
cannot be one request dict — the CLI step in the middle needs to run, and a
single request has no field for that. It also cannot be told apart by HTTP
*status*: `mcp_client/main.py`'s `/run` handler always returns `200`, win or
lose, and reports success or failure inside the JSON body instead
(`add_result: null` vs `add_result: "5"`). `commands` is exactly this case, and
the field to assert has to change between the two requests, not the status:

```python
REQUESTS = (
    {
        "method": "POST",
        "port": 5001,
        "path": "/run",
        "payload": None,           # the documented curl has no `-d`
        "status": 200,
        "field": "errors",         # non-empty: every tool call is denied
    },
    {
        "method": "POST",
        "port": 5001,
        "path": "/run",
        "payload": None,
        "status": 200,
        "field": "add_result",     # present and non-empty once granted: "5"
        "commands": (
            "diagrid mcpserver access grant mcp-server --caller mcp-client "
            "--allow-tools add --wait",
        ),
    },
)
```

A request's `commands` are documented commands like any other and go through
`check_agent`'s `harness -> documented` direction the same as `SETUP`: they have
to appear literally in the README (the grant line above does), or the check
fails.

## Documented provisioning differs by family — do not assume a shared pattern

Three documented flows, spread across more quickstarts than three. Follow
whichever one the README you are working from actually shows; do not average
them.

- **`agents/*`** (`agents/langgraph`, `agents/microsoft-dotnet`,
  `agents/dapr-agents/durable-agent`): `diagrid project create <name>
  --enable-managed-workflow --deploy-managed-kv --deploy-managed-pubsub --wait
  --use`, then `diagrid agent create <agent-name> --wait`, then a **bare** `dev
  run` (no `--project`). The bare form works because `--use` on the documented
  `project create` made it the CLI's default project, and reproducing that
  dependency is deliberate — a regression in `--use` should break this suite,
  not be silently worked around by adding an explicit `--project` the README
  never shows. `agents/spring-ai/event-planner` follows the same shape one flag
  lighter: `--enable-managed-workflow --deploy-managed-kv`, no
  `--deploy-managed-pubsub` — a reminder that these flags are per-quickstart
  data transcribed from each README, not a constant this skill can assume.
- **`agents/dapr-agents/orchestrator`**: no `project create` anywhere in the
  README, and no `--project` flag on `dev run` either — past `cd` and `uv sync`
  the documented flow is `diagrid login` then `uv run diagrid dev run -f
  dev-multi-agent-orchestration.yaml`. This is the "documents no project
  creation" case; see below.
- **`mcp-auth/python`**: `diagrid project create mcp-auth --use`, then `diagrid
  app create mcp-client --wait`, then `diagrid apply -f
  resources/mcp-server.yaml`, then a `dev run` that carries **both** an explicit
  `--project mcp-auth` and three `--skip-*` flags: `--skip-managed-kv
  --skip-managed-pubsub --skip-default-resiliency`. (Check the README yourself
  before assuming a specific flag count — READMEs change.)

## Undocumented provisioning: ask, do not guess

`agents/dapr-agents/orchestrator` documents `diagrid login` and then
`uv run diagrid dev run -f dev-multi-agent-orchestration.yaml`, and nothing in
between — no `project create`, and no `--project` flag on `dev run` either. Its
prerequisites list only the CLI, Python, uv and three model API keys (Google,
OpenAI, Anthropic). Under the guiding principle, provisioning here is
infrastructure the harness must supply, the same as `ci/setup-project.sh`
already does for the four canonical APIs.

But `ci/setup-project.sh`'s flags (`--deploy-managed-kv
--deploy-managed-pubsub --enable-managed-workflow`) were chosen for the
canonical APIs, and an agent quickstart's project may need different ones.
Every agent quickstart that *does* document its own provisioning agrees on
`--enable-managed-workflow --deploy-managed-kv`, and all but `spring-ai` add
`--deploy-managed-pubsub` on top — but orchestrator brings up nine apps across
eight frameworks with no documented `project create` of its own, and assuming
its needs match either set is guessing — the one thing this skill must not do,
because a flag that happens to work hides a real documentation gap that a
reader following the README will hit and you will not.

So: leave `SETUP` empty, write a comment in the data module that provisioning is
undocumented, and ask which flags the project actually needs before running
anything against Catalyst. State what you know (the quickstart's `dev run`
passes no `--project` at all; the README documents no command that creates one;
the flags every other agent quickstart documents are these) and what needs a
decision.

## Probe a path the app really serves

`Wait Until Apps Healthy` polls each `(port, path)` in `HEALTH_PROBES` until it
answers 200, and it is the last gate before the suite starts asserting. A probe
path the app does not route is the worst kind of mistake this skill can make:
the quickstart is healthy, the readiness marker has already arrived, and the
suite still burns the full `${READINESS_TIMEOUT}` on a 404 and then fails —
*after* paying for `project create --enable-managed-workflow
--deploy-managed-kv --deploy-managed-pubsub --wait` and `agent create --wait`.
Nothing static catches it. Confirm it yourself:

1. Find where the app starts its HTTP server. For `agents/langgraph` that is
   `main.py`'s `runner.serve(...)`, which is
   `DaprWorkflowGraphRunner.serve()` in the `diagrid` package (version pinned in
   the quickstart's `pyproject.toml`/`uv.lock`).
2. Read the routes it registers. `serve()` creates a **bare `FastAPI()`** and
   registers `POST /agent/run`, `GET /agent/run/{workflow_id}`, and — only when
   `pubsub_name` and `subscribe_topic` are both passed — `GET /dapr/subscribe`
   and `POST /events/{subscribe_topic}`. There is no `/` and no `/health`.
3. Pick a GET route that needs no arguments and answers 200. For
   `agents/langgraph` that is `GET /dapr/subscribe`, which is why its
   `HEALTH_PROBES` is `((8005, "/dapr/subscribe"),)` and not `((8005, "/"),)`.
   `GET /agent/run/{workflow_id}` is a route too, but with a made-up id it
   answers 404 by design, so it is not a 200 probe.
4. Write down in a comment where the answer came from, and say why it differs
   from `/` if it does.

Do not carry another quickstart's probe path over on the assumption that agent
apps look alike. `agents/langgraph` (diagrid SDK) and
`dapr-agents/*` (the `dapr_agents` package) start their servers from different
code, so the route sets are unrelated until you have read both.

The canonical suites are the contrast, and the reason `/` is still the default
for `Health Check Returns 200`: all sixteen canonical implementations really do
route `/` (`state/python/main.py`, `state/csharp/Program.cs`,
`state/javascript/index.js`, `state/java` `Controller.java`, and the same in
`workflow`, `pubsub` and `invocation`), so
`quickstarts.get_quickstart` pairs every port with `/`.

## The Catalyst-attach gate

Every readiness signal above is satisfied by the **local process**. The
`Connected App ID` line means the dev tunnel is up. `Uvicorn running on` means
the app's own server is listening. A 200 from `HEALTH_PROBES` means the app
routes that path. None of them means Catalyst has attached to the app — and
until it has, a workflow call does not fail, it **hangs and never recovers**.

Measured on `agents/langgraph` against a real project, 2026-08-27:

| What was done | Result |
|---|---|
| documented POST at readiness + 25 ms (the suite, twice) | hung the full 120 s; no workflow instance created (`ERR_INSTANCE_ID_NOT_FOUND` afterwards) |
| POST at readiness + 0 s, then 12 retries over 181 s | every attempt hung — **retrying does not recover it** |
| idle 20 s, then one POST | 200 in 1.1 s |
| gated on `GET /dapr/config`, then POST (3 runs) | 200 in ~1 s; marker arrived at t+1 s, t+3 s, t+3 s |

All of it reproduced with an OpenAI-free clone of `main.py`, so the LLM is not
the variable.

Two consequences for the design, both learned the hard way:

**The gate must run before the first request, not around it.** The first call
into the window poisons the app's workflow client permanently, so
`Wait Until Not Server Error`'s shape — poll the real call until it answers —
cannot work here. There is nothing to poll: the first poll is the damage.

**The signal has to be passive.** Two active probes were tried and are
**vacuous**; do not reinvent either:

| Probe | Behaviour at readiness+0 | Why it fails |
|---|---|---|
| app's own `GET /agent/run/{workflow_id}` | 404 in 71 ms, while the POST beside it hung | same gRPC channel, but a different RPC — `GetInstance` (read) is live long before `StartInstance` (write) |
| Catalyst's workflow HTTP API `POST .../start` | 202 in ~100 ms, and the worker executed the instance at t+1 s | the backend's create path and work-item dispatch are both live in the window; neither distinguishes it |

The first of these actually shipped, and the next suite run caught it: the gate
passed in 76 ms and the POST hung anyway. That is what a vacuous gate looks like
in practice — green, fast, and worthless.

What does work is watching for an **inbound** request from Catalyst in the app's
own captured output. Catalyst fetches `/dapr/config` (and probes `/`) through the
tunnel once it attaches, and the app logs those like any other request. That is
`CATALYST_PROBE_MARKERS`, and like `READY_MARKERS` it is per quickstart: it
depends on what that app's request logging prints, not on Catalyst.

Choosing one for a new quickstart:

1. Run the quickstart by hand and watch the `diagrid dev run` output after the
   readiness marker. Look for a request the app did not make itself.
2. Pick a substring stable across runs. `GET /dapr/config` is good: it is a fixed
   path Catalyst always fetches. A client IP or port is not — those vary.
3. Confirm it lands *after* local readiness and *before* the trigger works. If
   the marker is already present when the readiness marker arrives, it is not
   gating anything.
4. Leave it `()` rather than guess. A marker that never appears makes the gate
   time out — loud, and the suite fails honestly. A marker matched from the wrong
   line lets the suite through early — silent, and the run hangs for the full
   client timeout. `agents/microsoft-dotnet` and `agents/spring-ai/event-planner`
   are both `()` because nobody has watched their logs yet; their suites already
   carry the (no-op) loop, so adding the gate later is a data change only.

`resources/tests/keywords.robot` tests the gate credential-free: that it waits
for a marker that arrives late, and that it fails — naming the gate — when
Catalyst never probes.

## Readiness markers are a framework property, not a language property

Every README that documents a background process tells you, in prose, what to
wait for before triggering it — the exact phrasing varies, but the pattern is
consistent: "Wait until the output shows `Uvicorn running on
<localhost:port>`" (`agents/langgraph`, `agents/dapr-agents/durable-agent`),
"Wait until the output shows `Established gRPC bidirectional stream with Dapr
sidecar`" (`agents/microsoft-dotnet`). Read this line out of the README
itself; do not assume it is `Uvicorn running on` just because the language is
Python — `agents/microsoft-dotnet`'s marker names a Dapr sidecar gRPC stream,
not the app's own HTTP server, even though the app does end up serving HTTP.

`agents/spring-ai/event-planner` is the harder case: its README documents no
readiness marker at all, no "Wait until..." sentence anywhere in it, even
though `diagrid dev run -f dev-spring-ai-event-planner.yaml --approve` is
exactly the same kind of long-running background process as the other two.
Together, `agents/microsoft-dotnet` and `agents/spring-ai/event-planner` are
worth holding side by side: one shows the marker is a property of the agent
framework, not the language; the other shows a quickstart may not give you a
marker at all.

`Wait Until Ready Marker` (`catalyst.resource`) is the keyword this maps to —
see `references/harness-keywords.md`. It exists precisely because agent
quickstarts do not reliably emit the canonical `Connected App ID "<id>" to
http://localhost:<port>` line that `Wait Until Apps Connected` waits for. Where
a README gives you no marker to wait for at all, as for
`agents/spring-ai/event-planner`, that connection line — via
`${qs}[connected_apps]` and `Wait Until Apps Connected` — is the readiness
signal that is left; whether the CLI actually prints it for that app has not
been confirmed by a live run, the same open question `agents_langgraph.py`'s
`CONNECTED_APPS` comment already flags for `agents/langgraph`.

Neither `agents/microsoft-dotnet` nor `agents/spring-ai/event-planner` serves
any GET route at all (confirmed by reading both apps' HTTP setup — the .NET
app maps only its `POST /run` endpoint, and the Spring AI app maps only its own
`POST /run`), so `HEALTH_PROBES` is empty for both. "Probe a path the app
really serves" above is not a hypothetical instruction added for effect: these
are the two real quickstarts that show a suite can have nothing to probe at
all.

## Assertions are structural, on purpose

Agent responses embed live model output, so an exact body comparison
(`Should Be Equal` against a fixed dict, the way `POST And Expect` checks the
canonical quickstarts) cannot work here — the wording changes between runs even
when nothing is broken. What is assertable: a status code, and — only where a
README or the app's own framework tells you the response has a named field —
that the field is present and non-empty, plus a log marker proving the expected
tool or step actually ran. Where no README documents a response shape
at all (as for `/agent/run` in `agents/langgraph`), assert the status code only
and leave `field: None` with a comment saying why. Do not guess a field name to
make the suite look more thorough than it is: a guessed field either matches by
luck (telling you nothing) or fails immediately on first live run for a reason
that has nothing to do with the quickstart being broken.

**The status code is the one value you will almost certainly have to assume.**
Transcribe it when the README states it — but none of the three agent READMEs
shipped today states one anywhere, so `status: 200` in all three data modules is
an assumption, not a transcription. If the README you are working from is the
same, say so in a comment next to the value and add it to the harness README's
Limitations, the way `variables/agents_langgraph.py` and
`tools/qs-tester/README.md` do; do not present an assumed code as documented.
Be especially careful where the README says the app exits mid-request (as
`agents/microsoft-dotnet` and `agents/spring-ai/event-planner` both do for their
crash step): there the live run will most likely see a connection error rather
than any status code at all, and the assumed value is a placeholder that exists
so the first live run fails on a line you already flagged.

## Cleanup: empty vs documented

`TEARDOWN` is empty when the README documents no cleanup command.
`agents/langgraph` has no "Clean Up" section, so `TEARDOWN = ()`, and
`ci/teardown-project.sh` is what actually deletes the ephemeral project — not a
safety net finding nothing already gone. `agents/microsoft-dotnet` is the
contrast: its README has a "Clean Up" section documenting `diagrid project
delete dotnet-quickstart`, so that suite's `TEARDOWN` would carry
`("diagrid project delete {project}",)` and the suite runs it. Do not add a
`project delete` to `TEARDOWN` for a quickstart whose README documents no
cleanup — that is inventing a documented command, and `check_agent`'s
`harness -> documented` direction rejects it (the string would not appear in the
README).

The suite's `Clean Up Quickstart` keyword runs `Stop Quickstart` (which also
calls `diagrid dev stop` to release local app connections) and then whatever
`TEARDOWN` holds, in that order, regardless of whether `TEARDOWN` is empty — it
is the template every agent-family suite's teardown keyword copies, precisely
so a quickstart that does self-delete still gets a net if it dies before
reaching its own teardown.

`Stop Process Tree` (in `process.resource`, called by `Stop Quickstart`) is
**not** idempotent against a process that has already exited — calling it a
second time, or against something already gone, raises rather than doing
nothing. Every call site wraps it in `Run Keyword And Ignore Error` for exactly
this reason (see `Stop Quickstart` in `catalyst.resource`, and `Clean Up
Quickstart` in `agents/langgraph/tests/quickstart.robot`). Do the same in any
new teardown keyword that calls it directly — do not assume the process is
still there.

## The nightly flag: a cost lever, decided with evidence

`nightly` in `tools/qs-tester/variables/suites.py` is read only for agent-family
rows. Every agent leg provisions a project with agent infrastructure and spends
real model tokens, so it is not free the way the canonical dryrun-verified
suites are. `agents/langgraph` is registered `nightly: False` today, and the
reason is concrete, not cautious-by-default: it has never had a green live run
or a mutation check against real Catalyst, so registering it `nightly: True`
would fail the scheduled build every night for everyone (and leak a project
each time, until `reap-orphans.sh` collects it).

Only flip a suite to `nightly: True` in the same commit that records the live-run
evidence — a passing `verify-live.sh` run and a mutation check that failed as
expected. Until then, the suite still runs, just only on `workflow_dispatch`
(`ci/list-suites.py --matrix agent`, unfiltered, is what that path uses; the
scheduled path passes `--nightly` and filters to `True` rows only).

## The manifest rejects duplicate names, not just duplicate paths

`suites.validate()` (`variables/suites.py`) fails a row whose agent `name`
already appears in another row, in addition to failing a duplicate `suite`
path. `name` is not just a label: it keys the CI artifact name, the
failure-summary file (`failed-agents-<name>.txt`), and — by default — the
ephemeral project's leg id (`ci/project-name.sh agents-<name>`). Two suites
sharing a `name` would collide at runtime — the second run's project name, log
upload and failure marker would clobber the first's. Pick a `name` that is
unique across every agent-family row, not just within the family you are
adding to.

`name` is not invented — it is the quickstart's path below `agents/` with every
`/` replaced by `-`, and it is what `suites.leg_id()` defaults to when a row
carries no explicit `leg`. Quickstarts can be nested three levels deep, not
just the two `agents/langgraph` shows: `agents/spring-ai/event-planner` is a
real one, so its suite lives at
`agents/spring-ai/event-planner/tests/quickstart.robot` (`<family>/<group>/
<name>/tests/quickstart.robot`) and its manifest `name` is
`spring-ai-event-planner` — 23 characters, inside the 26-character budget
below, but the tightest real case that exists today. A row whose family is
`agents` but whose quickstart nests even one level deeper than that would need
an explicit, shorter `leg`.

The leg id has its own, tighter limit: `suites.validate()` also rejects a row
whose leg is over `suites.project_name_budget()` characters (26 today), because
the full ephemeral name (`qs-ci-agents-<leg>-<run-id>`) has to fit Catalyst's
55-character ceiling even on a local run, where the run-id fallback is longest.
A deep suite path can produce a `name` over that budget — this is why the row
schema also accepts an explicit `leg`, shorter than `name`, used for the
project's leg id instead. `ci/list-suites.py --matrix agent` and
`scripts/verify-live.sh` both read `leg` (via `suites.leg_id()`), not `name`,
for anything that becomes part of the actual project name; only add a `leg`
when `--validate` tells you `name` is over budget, and keep `name` as the
readable, unique label everything else still uses.

## Where the generic keywords run out: mcp-auth's grant/revoke phases

`mcp-auth/python`'s README goes well past "trigger and grant" once you read past
its main flow: it documents `diagrid mcpserver access revoke`, `access get`,
`access list`, and `access test` (a dry-run policy check that calls no server at
all), plus an entirely separate "Appendix: Run Every Process Manually" flow that
runs `mcp-client` as a plain local process outside `diagrid dev run` altogether.
None of that is expressible through `Run Documented Commands` plus
`POST And Expect Field` plus a `commands` list on a request — those cover "run a
CLI command, then call an HTTP endpoint and check its shape," not "inspect a
policy's current state" or "run a process the harness never launched."

If you reach a phase like this that exceeds what the generic keywords express,
do not stretch an assertion to imply coverage that is not there. Write the
partial suite for the phases that do fit the shapes above, and add an explicit
gap note to `tools/qs-tester/README.md`'s Limitations section naming exactly
which documented phases are untested and why. A gap that is written down is
honest; a green suite that quietly skips half the README is not.

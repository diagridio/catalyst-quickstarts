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
| `SECRETS` | `tuple[str, ...]` | Environment variable names the suite's `Require Env Var` loop checks before doing anything else — the model provider keys. |
| `REQUESTS` | `tuple[dict, ...]` | The documented trigger calls, in documented order. Keys below. |
| `UNCOVERED` | `tuple[tuple[str, str], ...]` | `(documented command, reason)` pairs for commands the suite deliberately does not run. |
| `get_quickstart()` | function | Returns one flat dict: `family`, `name`, `language`, `dir`, `setup`, `install`, `run`, `teardown`, `health_probes`, `secrets`. Not identical to what `quickstarts.get_quickstart(api, language)` returns (that one has `api` and `connected_apps` instead of `family`/`name`/`setup`/`teardown`/`secrets`) — the two dicts share exactly the five keys the *shared* keywords actually read (`dir`, `install`, `run`, `health_probes`, `language`), which is what lets `Build Quickstart`, `Start Quickstart` and `Wait Until Apps Healthy` work unchanged against either shape. |

### What doc-sync actually enforces — and what it does not

`docsync/check_readme_sync.py::check_agent` reads a fixed list of required
attributes, `_REQUIRED_MODULE_ATTRS`:

```
DOCUMENTED_PROJECT, SETUP, INSTALL, RUN, TEARDOWN, READY_MARKERS, REQUESTS, UNCOVERED
```

Note what is **not** in that list: `HEALTH_PROBES`, `SECRETS`, and
`get_quickstart`. If your module is missing one of the eight listed names,
`check_agent` returns it as a problem string (`"... is missing required
attribute(s): ..."`) — a normal doc-sync failure, not a crash, so one bad module
costs its own row and not the other suites `--all` also checks in the same run.
But a missing `HEALTH_PROBES`, `SECRETS`, or `get_quickstart` is not caught here
at all: the suite will fail at Robot runtime instead (a `Wait Until Apps Healthy`
FOR loop with nothing to iterate, or a keyword error), which is a slower and
noisier way to find the same mistake. Do not skip these three just because
doc-sync will not complain about their absence. Nothing static can check that a
probe *path* is real either — that one is on you, see below.

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

Required: `method`, `port`, `path`, `payload`, `status`.
Optional: `field` (default `None`), `commands` (default `()`), `log_marker`
(default `None`).

The suite reads optional keys with `Get From Dictionary ... default=...` (or, for
`commands`, `Evaluate    $request.get('commands', ())` — the default has to be an
empty *sequence*; a `${EMPTY}` default is an empty *string*, and `Run Documented
Commands` fails iterating a string with "not list or list-like"). This is why a
request that needs none of the optional keys stays a plain five-key dict instead
of carrying explicit nulls.

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

**Several apps, one documented endpoint — `dapr-agents/multi-agent-workflow`
(no suite yet; read the README yourself before writing one).** Its `dapr.yaml`
declares three apps — the workflow app on 8001 (`main.py`, a plain
`uvicorn.run(app, ...)`), a triage agent on 8002 and an expert agent on 8003
(`triage_agent.py`/`expert_agent.py`, both calling `AgentRunner.serve(...,
port=...)` from the `dapr_agents` package, whose `serve()` also auto-starts
uvicorn internally when no app loop is already running). All three would
therefore print their own `Uvicorn running on` line, so `READY_MARKERS` needs
one entry per app and `HEALTH_PROBES` needs all three ports — but this has not
been confirmed against a captured log, since no suite runs this quickstart yet;
confirm it against the real `diagrid dev run` output before trusting it in a
live suite. The README documents exactly one HTTP call, `POST
http://localhost:8001/workflow/start`: the triage and expert agents are reached
only as child workflows, never directly over HTTP. So `REQUESTS` still has a
single entry even though three apps have to come up first:

```python
READY_MARKERS = ("Uvicorn running on", "Uvicorn running on", "Uvicorn running on")
# Ports from dapr.yaml. The probe PATHS are left as a question here on purpose:
# read each app's routes before filling them in (see "Probe a path the app really
# serves" below). 8001 is a plain uvicorn app whose own routes you can read in
# main.py; 8002/8003 come from dapr_agents' AgentRunner.serve(), which is a
# different package from the one agents/langgraph uses, so langgraph's
# /dapr/subscribe answer does not carry over.
HEALTH_PROBES = ((8001, "<read main.py>"), (8002, "<read AgentRunner.serve>"), (8003, "<same>"))
REQUESTS = (
    {
        "method": "POST",
        "port": 8001,
        "path": "/workflow/start",
        "payload": {"customer": "Alice", "issue": "My Dapr system fails to start in production."},
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

Three real quickstarts show three different documented flows. Follow whichever
one the README you are working from actually shows; do not average them.

- **`agents/*`** (`agents/langgraph`, `agents/microsoft-dotnet`): `diagrid
  project create <name> --enable-agent-infrastructure --wait --use`, then
  `diagrid agent create <agent-name> --wait`, then a **bare** `dev run` (no
  `--project`). The bare form works because `--use` on the documented `project
  create` made it the CLI's default project, and reproducing that dependency is
  deliberate — a regression in `--use` should break this suite, not be silently
  worked around by adding an explicit `--project` the README never shows.
- **`dapr-agents/durable-agent`**: no `project create` anywhere in the README —
  only `diagrid login` — yet `dev run` passes `--project
  durable-agent-quickstart` explicitly. This is the "documents no project
  creation" case; see below.
- **`mcp-auth/python`**: `diagrid project create mcp-auth --use`, then `diagrid
  app create mcp-client --wait`, then `diagrid apply -f
  resources/mcp-server.yaml`, then a `dev run` that carries **both** an explicit
  `--project mcp-auth` and three `--skip-*` flags: `--skip-managed-kv
  --skip-managed-pubsub --skip-default-resiliency`. (Check the README yourself
  before assuming a specific flag count — READMEs change.)

## Undocumented provisioning: ask, do not guess

`dapr-agents/durable-agent` documents `diagrid login` and a `dev run --project
durable-agent-quickstart`, and nothing in between. Its prerequisites list only
the CLI, Python and an OpenAI key — no `project create` at all. Under the
guiding principle, provisioning here is infrastructure the harness must supply,
the same as `ci/setup-project.sh` already does for the four canonical APIs.

But `ci/setup-project.sh`'s flags (`--deploy-managed-kv
--deploy-managed-pubsub --enable-managed-workflow`) were chosen for the
canonical APIs, and an agent quickstart's project may need
`--enable-agent-infrastructure` on top, or instead. Deciding that from nothing
is guessing — the one thing this skill must not do, because a flag that happens
to work hides a real documentation gap that a reader following the README will
hit and you will not.

So: leave `SETUP` empty, write a comment in the data module that provisioning is
undocumented, and ask which flags the project actually needs before running
anything against Catalyst. State what you know (the quickstart passes `--project
X`; the README documents no command that creates `X`; the canonical flags are
these) and what needs a decision.

## Probe a path the app really serves

`Wait Until Apps Healthy` polls each `(port, path)` in `HEALTH_PROBES` until it
answers 200, and it is the last gate before the suite starts asserting. A probe
path the app does not route is the worst kind of mistake this skill can make:
the quickstart is healthy, the readiness marker has already arrived, and the
suite still burns the full `${READINESS_TIMEOUT}` on a 404 and then fails —
*after* paying for `project create --enable-agent-infrastructure --wait` and
`agent create --wait`. Nothing static catches it. Confirm it yourself:

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

## Readiness markers are a framework property, not a language property

Every README that documents a background process tells you, in prose, what to
wait for before triggering it — the exact phrasing varies, but the pattern is
consistent: "Wait until the output shows `Uvicorn running on
<localhost:port>`" (`agents/langgraph`), "Wait until the output shows
`Established gRPC bidirectional stream with Dapr sidecar`"
(`agents/microsoft-dotnet`), "Confirm from the logs that `Travel Assistant
Agent is running`" (`dapr-agents/durable-agent`). Two Python quickstarts here
(`langgraph`, `durable-agent`) do not share a marker, because the marker comes
from the agent framework each one is built on, not from the language runtime.
Read this line out of the README itself; do not assume it is `Uvicorn running
on` just because the language is Python.

`Wait Until Ready Marker` (`catalyst.resource`) is the keyword this maps to —
see `references/harness-keywords.md`. It exists precisely because agent
quickstarts do not emit the canonical `Connected App ID "<id>" to
http://localhost:<port>` line that `Wait Until Apps Connected` waits for.

## Assertions are structural, on purpose

Agent responses embed live model output, so an exact body comparison
(`Should Be Equal` against a fixed dict, the way `POST And Expect` checks the
canonical quickstarts) cannot work here — the wording changes between runs even
when nothing is broken. What is assertable: the documented status code always,
and — only where a README or the app's own framework tells you the response has
a named field — that the field is present and non-empty, plus a log marker
proving the expected tool or step actually ran. Where no README documents a
response shape at all (as for `/agent/run` in `agents/langgraph`), assert the
status code only and leave `field: None` with a comment saying why. Do not guess
a field name to make the suite look more thorough than it is: a guessed field
either matches by luck (telling you nothing) or fails immediately on first
live run for a reason that has nothing to do with the quickstart being broken.

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
path. `name` is not just a label: it keys the ephemeral project's leg id
(`ci/project-name.sh agents-<name>`), the CI artifact name, and the
failure-summary file (`failed-agents-<name>.txt`). Two suites sharing a `name`
would collide at runtime — the second run's project name, log upload and
failure marker would clobber the first's. Pick a `name` that is unique across
every agent-family row, not just within the family you are adding to.

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

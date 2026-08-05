# Design: a skill that adds a quickstart end-to-end test

Date: 2026-07-31

## Goal

A Claude Code skill that, given the name of a quickstart in this repository, produces a
Robot Framework end-to-end test for it, wires that test into the nightly GitHub
Actions workflow, and proves the test works by running it against a real Catalyst
project before reporting back.

The skill covers both quickstart conventions in this repo, because they are
structurally different:

- **Canonical**: `workflow`, `state`, `pubsub`, `invocation`. An (api × language)
  matrix of 4 × 4. Numbered READMEs (`## 4. Install`, `## 5. Run`, `## 6. Call the
  API`). Already covered by `tools/qs-tester`.
- **Agent-family**: `agents/*`, `dapr-agents/*`, `mcp-auth/*`. A flat list where each
  quickstart has exactly one language (`agents/microsoft-dotnet` is .NET,
  `agents/spring-ai` is Java, the rest are Python). Prose READMEs with named
  sections, an LLM API key requirement, ports other than 5001/5002, and
  framework-specific readiness output. Currently untested.

"Handle multiple languages" therefore means two different things. For canonical
quickstarts a language is a matrix dimension. For agent-family quickstarts it is a
property of the individual quickstart that decides which CI runtime-setup step the
suite needs.

### Two pieces of work

This spec describes both, and they land in that order:

1. **One-time enabling work**: the suite manifest, the four new keywords, the
   agent-family project lifecycle scripts, the doc-sync loose mode, and the CI job that
   runs agent-family suites. Done once, by hand, guided by this spec.
2. **The skill itself**: what runs per invocation, producing one suite plus its data,
   manifest row, and documentation. After the enabling work exists, a normal invocation
   edits no workflow YAML at all.

## Guiding principle

> If a README documents a command, the harness runs that command verbatim, with only
> the project name substituted. Where a README documents nothing, the harness supplies
> its own command and labels it infrastructure.

This sharpens the rule the harness already follows. Canonical READMEs never document
project creation. Section 2 is only `diagrid login` and section 7 is
`diagrid project delete`, which is why `ci/setup-project.sh` has to invent its own
`--deploy-managed-kv --deploy-managed-pubsub --enable-managed-workflow --wait --use`
call. Agent-family READMEs do document provisioning, so their suites run the
documented commands instead of an invented equivalent:

```
diagrid project create langgraph-quickstart --enable-agent-infrastructure --wait --use
diagrid agent create langgraph-agent --wait
uv run diagrid dev run -f dev-python-langgraph.yaml --approve     # bare, as documented
```

The bare `dev run` stays bare. It works because the documented `project create` carries
`--use`, and reproducing that dependency is the point: if `--use` ever stopped setting
the default project, the documented flow would break for readers and this suite would
catch it.

Exactly two exceptions exist, and the skill names both so that nobody later "fixes"
them:

1. `diagrid login` becomes `diagrid login --api-key "$DIAGRID_API_KEY"`. The documented
   bare form blocks on an interactive browser prompt and would hang CI.
2. The documented project name (`langgraph-quickstart`) becomes an ephemeral
   `qs-ci-<suite>-<run-id>`. The `qs-ci-` prefix is load-bearing, not cosmetic:
   `ci/reap-orphans.sh` collects leaked projects by that pattern.

## What the skill produces

For one named quickstart:

1. A Robot suite. Agent-family: a new `<family>/<name>/tests/quickstart.robot`.
   Canonical: a language-tagged test case added to the existing
   `<api>/tests/quickstart.robot`.
2. Test data. Canonical: rows in every dict in
   `tools/qs-tester/variables/quickstarts.py`. Agent-family: a new module
   `tools/qs-tester/variables/<family>_<name>.py`.
3. A row in the new suite manifest, `tools/qs-tester/variables/suites.py`. Each row
   carries the suite path, the family, the api or quickstart name, the language or
   languages, the runtime (which selects the CI setup step), nightly membership, and
   the names of any required secrets. It carries no agent-infrastructure flag and no
   agent name: those live in the documented `SETUP` commands the suite runs, so a
   manifest copy of them would be a second source of truth for the same fact.
4. CI wiring in `.github/workflows/e2e-quickstarts.yml`. Normally no hand-edited YAML,
   because the manifest drives discovery. A genuinely new runtime (a first Go
   quickstart) still needs a setup step, which the skill adds explicitly.
5. Documentation updates: `tools/qs-tester/README.md`, and doc-sync coverage.

### Out of scope, stated inside the skill

- Crash-recovery flows that require editing quickstart source, such as uncommenting
  `os._exit(1)` in `agents/langgraph/crash_test.py`.
- Endpoints no README documents (`DELETE /order/{id}`,
  `POST /workflow/terminate/{id}`). Documenting them brings them under test; the suites
  test the documented flow and nothing more.
- Verification through the Catalyst dashboard.

## Skill anatomy

```
.claude/skills/add-quickstart-e2e-test/
├── SKILL.md                        workflow, gates, the classification decision
├── references/
│   ├── canonical-api.md            numbered-README convention, central table, doc-sync
│   ├── agent-quickstart.md         agent/mcp shape: documented provisioning, secrets,
│   │                               structural assertions, readiness markers
│   └── harness-keywords.md         available keywords with signatures
├── scripts/
│   ├── preflight.sh                credentials, CLI version, uv sync, manifest validity
│   ├── verify-static.sh            dryrun + doc-sync + pytest + manifest lint
│   └── verify-live.sh              provision → run → mutation check → teardown
└── evals/evals.json                test prompts for the skill itself
```

Progressive disclosure earns its keep here because the two families share little.
SKILL.md holds the workflow and the classification decision, and exactly one family
reference loads per run.

The description covers phrasings like "add an e2e test for the langgraph quickstart",
"the microsoft-dotnet quickstart has no CI coverage", and "write a Robot test for
mcp-auth", including requests that say "test" without saying Robot or CI.

## Skill workflow

Seven phases, each gated.

**0. Preflight.** `scripts/preflight.sh` checks `DIAGRID_API_KEY`, `diagrid` on PATH at
the version `DIAGRID_CLI_VERSION` pins, a synced harness, and the LLM key the target
quickstart needs. It runs first so that a credentials problem surfaces in seconds
rather than after twenty minutes of writing files that cannot be verified.

**1. Classify.** Canonical or agent-family, which language, which runtime, where the
quickstart lives. Loads one family reference file.

**2. Extract facts.** Start from the README. Where the README is silent about something
the test needs (app port, appID), read the dev config YAML or the app source, and
record in a comment where the value came from. Nothing is invented: an assertion that
cannot be traced to a source is worse than no assertion, because it looks like
coverage.

**3. Write.** Data module, suite, manifest row, in the conventions the existing files
use. That means a `*** Comments ***` header naming what the suite mirrors, and a
comment on every deliberate truncation or divergence.

**4. Static verify.** `scripts/verify-static.sh` runs the dryrun, doc-sync, the
doc-sync unit tests, and the manifest lint. Loop until green.

**5. Live verify.** `scripts/verify-live.sh` computes the ephemeral name, logs in,
provisions, runs the suite, and tears down on every exit path. Green is required.

**6. Mutation check.** The harness README names vacuous assertions as its largest
unproven risk: an assertion that passes whether or not the thing it checks is working.
So the suite runs a second time inside the same project with one assertion deliberately
broken, and it has to fail. If it passes, that assertion is vacuous and the skill does
not report success.

The mechanism needs no test-only code path. A command-line `--variablefile` outranks a
suite's own `Variables` import, so any module-level name can be replaced at run time by
generating a one-line file:

```bash
printf '%s\n' 'READY_MARKERS = ("__mutation_check__",)' > mutate.py
uv run robot --variablefile mutate.py --variable READINESS_TIMEOUT:20s ...
```

A generated file rather than `--variable`, because `--variable` can only set scalars and
the assertions worth breaking (`READY_MARKERS`, `REQUESTS`) are tuples. One mechanism
covers both.

Suites read their waits from `${MARKER_TIMEOUT}` (default `60s`) and
`${READINESS_TIMEOUT}` (default `180s`), the values those waits used before they were
parameterised, so the failing run gives up in seconds instead of waiting out a
three-minute readiness timeout and no existing suite's timing changes. Reusing the
project means the marginal cost is one application restart, plus one LLM call for
agent-family suites. The skill records in its report which name it overrode.

**7. Wire CI and docs, then report.** The report has exactly two shapes:

- **VERIFIED.** Live run green, mutation check failed as expected. Lists what was
  asserted and which variable was mutated.
- **BLOCKED.** What was missing, what was written anyway, and the exact command that
  finishes the job.

There is deliberately no third "probably fine" shape.

## Harness changes

### Suite manifest: `tools/qs-tester/variables/suites.py`

A Python module, not YAML: PyYAML is not a dependency, the repo already expresses
tables as commented Python modules, and both doc-sync and the CI helper can import it
directly.

```python
SUITES = (
    {
        "suite": "workflow/tests/quickstart.robot",
        "family": "canonical",
        "api": "workflow",
        "languages": ("csharp", "java", "javascript", "python"),
        "nightly": True,
        "secrets": (),
    },
    {
        "suite": "agents/langgraph/tests/quickstart.robot",
        "family": "agent",
        "name": "langgraph",
        "data": "agents_langgraph",      # module in variables/
        "language": "python",
        "runtime": "python",             # selects the CI setup step
        "nightly": True,
        "secrets": ("OPENAI_API_KEY",),
    },
)
```

Each row: suite path, family, api or name, language or languages, runtime, nightly
membership, and required secret names.

`nightly` is the cost lever, and it is read only for agent-family rows: canonical
scheduling stays the business of the existing `e2e` job. Around a dozen agent
quickstarts each consume a project with agent infrastructure plus real model tokens, so
nightly membership is an explicit per-suite decision and the rest run on
`workflow_dispatch`.

A new `ci/list-suites.py` emits either a path list (for the lint dryrun) or matrix JSON
(for the agents job). The manifest drives the lint dryrun and the new agents matrix
only. The existing `e2e` job keeps its hand-written `lang` matrix, because rewriting
working, load-bearing CI is not part of this work.

### Per-quickstart data module

Each agent-family quickstart gets a module holding the documented command sequence. An
ordered list rather than a fixed shape, because the three families genuinely differ:
`agents/*` documents `project create --enable-agent-infrastructure --wait --use` plus
`agent create` then a bare `dev run`; `dapr-agents/durable-agent` documents no project
create and passes `--project` explicitly; `mcp-auth/python` documents
`project create --use`, `app create`, and `apply -f resources/mcp-server.yaml`, then a
`dev run` carrying both `--project` and four `--skip-*` flags.

```python
SETUP = (
    "diagrid project create {project} --enable-agent-infrastructure --wait --use",
    "diagrid agent create langgraph-agent --wait",
)
INSTALL = "uv sync"
RUN = "uv run diagrid dev run -f dev-python-langgraph.yaml --approve"
# Empty because this README documents no cleanup step. Where one is documented
# (agents/microsoft-dotnet documents `diagrid project delete`), it goes here and
# the suite runs it. Otherwise deleting the project is infrastructure and
# ci/teardown-project.sh owns it.
TEARDOWN = ()
# A tuple because multi-app quickstarts announce themselves once per app:
# dapr-agents/multi-agent-workflow runs three.
READY_MARKERS = ("Uvicorn running on",)
HEALTH_PORTS = (8005,)
SECRETS = ("OPENAI_API_KEY",)
# Ordered, because a documented flow can be several calls. Two optional keys make
# the harder shapes expressible: `commands` runs documented commands before a
# request (mcp-auth grants a tool between two calls, which expect different
# statuses), and `log_marker` is waited for afterwards.
REQUESTS = (
    {
        "method": "POST",
        "port": 8005,
        "path": "/agent/run",
        "payload": {"task": "Check if the Grand Ballroom is available on March 15th"},
        "status": 200,
        # No README documents this response body, and /agent/run is served by
        # DaprWorkflowGraphRunner.serve() from an external package, so the field name
        # cannot be read out of this repo. It is discovered during the live run and
        # recorded here with a comment naming the observed response as its source.
        "field": None,
        "log_marker": "check_availability",
    },
)
```

`READY_MARKERS` and `REQUESTS` are read by the suite from its `Variables` import
rather than from `get_quickstart()`. A value a Python keyword returned cannot be
overridden from outside the suite, so a mutation check aimed at one would run
against the real value, pass, and prove nothing. For the same reason the mutation
check overrides through a generated `--variablefile` rather than `--variable`,
which can only set scalars.

No agents README documents a response body today, so until the live run reveals the
actual shape the suite asserts the documented status code and the log marker only. That
is the same weak-assertion tradeoff the harness already accepts for the
`GET /workflow/status/{id}` bodies in csharp, java, and javascript, where no README
documents a shape either. Guessing a field name would produce an assertion that looks
like coverage and fails for the wrong reason.

`get_quickstart()` returns the same flat-dict shape as `variables/quickstarts.py`, so
the existing keywords keep working unchanged.

Response bodies are LLM output and cannot be compared exactly, so agent-family
assertions are structural: the documented status code, a named field present and
non-empty, and a log marker showing the expected tool was called.

### Four new keywords

No new resource files. The additions go where the related keywords already live.

| Keyword | File | Purpose |
|---|---|---|
| `Run Documented Commands` | `catalyst.resource` | Run an ordered list, expect rc 0, substitute the project name, log each command as executed. |
| `Wait Until Ready Marker` | `catalyst.resource` | Wait for a per-quickstart readiness string. `Wait Until Apps Connected` encodes the canonical `Connected App ID` line and does not apply. |
| `Require Env Var` | `quickstart.resource` | Fail immediately naming the missing secret and the quickstart needing it, so a revoked key reads as a configuration error rather than a mysterious model failure. |
| `POST And Expect Field` | `quickstart.resource` | Assert the status code plus a named JSON field present and non-empty. |

One further change to existing keywords: the readiness and log-marker timeouts currently
hardcode `180s` in `quickstart.resource` and `catalyst.resource`. They become
`${MARKER_TIMEOUT}`, defaulting to `180s`, so the mutation check can pass a short
timeout and fail in seconds instead of waiting out three minutes. Default behaviour is
unchanged for every existing suite.

### Project lifecycle for agent-family suites

The suite provisions through its documented `SETUP`, but CI still computes the ephemeral
name before anything can fail (new `ci/project-name.sh`, name computation only, no CLI
calls) and still runs `ci/teardown-project.sh` under `if: always()`. A suite that dies
partway through `SETUP` would otherwise leak a project until the nightly reap. A small
`ci/login.sh` performs the API-key login before the suite starts.

`--use` mutates the local default project. That is pre-existing behaviour, since
`ci/setup-project.sh` already does it, and the skill calls it out so nobody is surprised
locally.

### doc-sync

`docsync/check_readme_sync.py` gains a loose mode for agent-family READMEs, which have
no numbered sections. It checks that `SETUP`, `RUN`, and `TEARDOWN` appear as literal
strings anywhere in the README modulo the project name, and likewise the install
command, the trigger URL and payload, and the readiness marker. Under the guiding
principle this is a stronger check than the canonical one, because it verifies the whole
documented command sequence rather than only the run line.

## CI changes

In `.github/workflows/e2e-quickstarts.yml`:

- **`lint`**: dryrun paths come from `ci/list-suites.py --paths` instead of four
  hardcoded ones. A new step validates the manifest: every suite path exists, every
  referenced data module imports, every secret is named, fields are consistent for the
  declared family.
- **New `e2e-agents` job** with `needs: [e2e]`. The ordering is load-bearing, because
  `max-parallel` is per-job: two jobs at 2 would allow four concurrent Catalyst projects
  and break the cap the existing `concurrency` comment relies on. Serialising the jobs
  keeps the cap at two, at the cost of a longer nightly run. Its matrix comes from
  `ci/list-suites.py --matrix agent`, filtered to `nightly: true` for scheduled runs and
  unfiltered for `workflow_dispatch`.
- **LLM secrets** are declared explicitly in that job's `env` block
  (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`) rather than indexed
  dynamically from the matrix. Explicit names are greppable and auditable, and a new
  provider becomes a one-line edit the skill makes deliberately.
- **`report`** gains `e2e-agents` in `needs`, and failure summaries become
  `failed-<suite>.txt` so the issue body names the exact suite.
- **PR `paths`** gains `*/*/tests/quickstart.robot` and the manifest module.

## The skill's own tests

`evals/evals.json` holds three prompts:

1. "add an e2e test for the langgraph quickstart". Python agent, the common case.
2. "the microsoft-dotnet agent quickstart has no CI coverage". A .NET runtime, which
   exercises adding a setup step.
3. "write a Robot test for mcp-auth/python". The hardest case: multi-phase
   authentication and authorization, with `app create` and `apply` in the documented
   sequence.

Assertions: the manifest row exists and validates; the suite is at the expected path;
static checks pass; CI wiring is updated; every command in the data module appears
verbatim in the README modulo the project name; and the final report is honestly
VERIFIED or BLOCKED.

Evals run without Catalyst credentials, so BLOCKED is the correct outcome. That makes
the eval suite a test of whether the skill overclaims, which is the failure mode to
worry about most in a skill whose job is producing trustworthy tests.

## Limitations

- **LLM nondeterminism** limits agent-family assertions to structural ones and adds
  nightly flake risk (a model refusal, a rate limit, a slow completion). No retry logic
  initially. If flake proves real, a single retry on the trigger request is the first
  thing to try.
- **`mcp-auth`'s grant/revoke phases** are expressible through a request's
  `commands` key, which is why that key exists, but the quickstart also runs
  `mcp-client` as a plain local process outside `diagrid dev run` and documents
  revocation and policy-inspection steps. Where a phase exceeds what the generic
  keywords express, the skill produces a partial suite plus an explicit gap note in
  `tools/qs-tester/README.md`, rather than assertions that imply coverage it does not
  have.
- **A quickstart that documents no project creation** (`dapr-agents/durable-agent`
  passes `--project durable-agent-quickstart` but documents nothing that creates it)
  needs a human decision about which `ci/setup-project.sh` flags apply. The skill
  asks rather than guessing, because a flag that works by accident hides the
  documentation gap readers will hit.
- **Cost** scales with `nightly: true` membership: one Catalyst project with agent
  infrastructure plus real model tokens per suite per night, serialised behind the
  four-language canonical matrix.
- **The mutation check proves one assertion per suite**, the one the skill judges most
  important. The others stay unproven in the same sense the current harness admits to
  for its own log markers.

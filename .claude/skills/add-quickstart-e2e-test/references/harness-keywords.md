# Available keywords

Every keyword the harness offers, with its real signature, as of the three
resource files under `tools/qs-tester/resources/`. Check this before writing a
new keyword — the four added for agent-family suites (`Run Documented
Commands`, `Wait Until Ready Marker`, `Require Env Var`, `POST And Expect
Field`) already cover the shapes an agent-family suite needs. If you think you
need a fifth, re-read `references/agent-quickstart.md`'s worked `REQUESTS`
examples first; most apparent gaps turn out to be an existing keyword used with
a different field.

## `resources/process.resource`

Process lifecycle only — knows nothing about Catalyst, HTTP or quickstarts.
Ported from `dapr-university-instruqt`; treat the teardown logic as load-bearing,
not something to simplify.

| Keyword | Signature | Use it for |
|---|---|---|
| `Start Background Process` | `${command}  ${logfile}  ${alias}  ${cwd}=${EMPTY}` | Launch a command without blocking, merging stdout+stderr into `${logfile}`; `${alias}` is how later keywords address the process. Truncates `${logfile}` first. |
| `Wait Until Log Contains` | `${logfile}  ${text}  ${timeout}=${MARKER_TIMEOUT}` | Poll a log file every 2s until it contains `${text}`. App logging is asynchronous relative to the HTTP response, so any log assertion needs a wait, never a single read. |
| `Log Should Contain` | `${logfile}  ${text}` | Internal single-shot check `Wait Until Log Contains` polls with; do not call this directly when you actually need to wait. |
| `Run And Expect RC Zero` | `${command}  ${cwd}=${EMPTY}  ${timeout}=600s` | Run a command to completion and fail unless it exits 0. Used for slow build commands; leaves `stdout=` unset deliberately so Robot manages a temp file (passing `stdout=PIPE` would create a file literally named `PIPE`). |
| `Stop Process Tree` | `${alias}  ${timeout}=15s` | SIGINT the process group (so both the CLI and the app it launched get Ctrl+C), then walk the real OS PID tree and SIGKILL every descendant if anything survives. **Not idempotent** — calling it against a process that has already exited raises. Every call site wraps it in `Run Keyword And Ignore Error`; do the same in anything new that calls it directly. |

### `${MARKER_TIMEOUT}` and `${READINESS_TIMEOUT}`

Defined in `process.resource`'s `*** Variables ***`:

```robotframework
${MARKER_TIMEOUT}       60s
${READINESS_TIMEOUT}    180s
```

These are the exact values the corresponding waits used before they were made
overridable — do not change the defaults, or every existing suite's timing
changes with them. Both are ordinary Robot variables, so `robot --variable
MARKER_TIMEOUT:5s` (or `READINESS_TIMEOUT:...`) overrides them at the command
line, because `--variable` can set a scalar. This is exactly what the mutation
check uses to make a run it expects to fail give up in seconds instead of
minutes — see the harness README's "Running an agent-family suite locally" for
the full mutation-check invocation, and `references/agent-quickstart.md` for why
the *other* half of that check (`READY_MARKERS`, `REQUESTS`) needs a generated
`--variablefile` instead, since those are tuples and `--variable` cannot set one.

## `resources/catalyst.resource`

Launching and stopping the quickstart's own `diagrid dev run` process, plus the
readiness markers it emits. Depends on `process.resource`.

| Keyword | Signature | Use it for |
|---|---|---|
| `Start Quickstart` | `${qs}  ${project}  ${logfile}` | Substitute `{project}` into `${qs}[run]` and launch it in the background under alias `apps`. |
| `Resolve Project In Command` | `${template}  ${project}` | Replace the `{project}` placeholder. Deliberately not named `Format String` — the `String` library already has a keyword by that name, and reusing it would silently collide. |
| `Wait Until Apps Connected` | `${qs}  ${logfile}` | Wait for `Connected App ID "<id>" to http://localhost:<port>` per entry in `${qs}[connected_apps]` — the canonical quickstarts' signal. Does nothing (empty list) for apps with `appPort` 0 or unset. Matches on the full `http://` line; a schemeless match would wait out the whole timeout silently. **Agent-family suites do not use this** — they use `Wait Until Ready Marker` instead, because agent frameworks do not print this line. |
| `Stop Quickstart` | `${project}` | The Ctrl+C equivalent: stops the `apps` process tree, then runs `diagrid dev stop --project ${project}` to release local app connections. Safe to call when the process is already gone (wraps `Stop Process Tree` in `Run Keyword And Ignore Error` itself). |
| `Run Documented Commands` | `${commands}  ${project}  ${cwd}=${EMPTY}  ${timeout}=600s` | Run an ordered list of documented commands (agent-family `SETUP`/`TEARDOWN`, or a request's `commands`), substituting `{project}` in each, stopping at the first non-zero exit so the real failure stays visible. 600s default matches `project create --wait`, which blocks until managed services are ready. |
| `Wait Until Ready Marker` | `${logfile}  ${marker}` | Wait for a per-quickstart readiness string in the captured `diagrid dev run` output — the agent-family equivalent of `Wait Until Apps Connected`. The marker is a property of the agent framework, not the language; read it out of the README's "wait until..." prose (see `references/agent-quickstart.md`). |

## `resources/quickstart.resource`

Building a quickstart, waiting for its apps to serve, and asserting documented
HTTP responses. Response bodies are compared as parsed JSON, never as raw
strings, so key order and whitespace cannot cause a false failure. Depends on
`process.resource`.

| Keyword | Signature | Use it for |
|---|---|---|
| `Build Quickstart` | `${qs}` | Run the install command from README section 4 (canonical) or the documented setup install (agent-family). |
| `Suite Log File` | `${api}  ${language}` | Return the path for one captured `diagrid dev run` stream, under the Robot output dir. The language **must** be part of the name — all four language tests in a canonical suite share one suite, and `Start Background Process` truncates this file, so a per-api-only name would leave only the last language's log on disk and destroy the evidence for whichever earlier language actually failed. |
| `Wait Until Apps Healthy` | `${qs}` | Poll `GET /` on every port in `${qs}[health_ports]` until 200, with `${READINESS_TIMEOUT}` overall and a 3s poll interval. The only readiness gate for quickstarts (like `workflow`, `state`) that emit no connection marker at all. |
| `Health Check Returns 200` | `${port}` | Internal single-shot check `Wait Until Apps Healthy` polls with. |
| `POST And Expect` | `${port}  ${path}  ${payload}  ${status}  ${expected_body}=${NONE}` | POST JSON and assert the status code, plus (if given) the **exact** parsed response body. Canonical-only — response bodies are deterministic there. Do not use this for an agent-family suite; use `POST And Expect Field` instead. |
| `GET And Expect` | `${port}  ${path}  ${status}  ${expected_body}=${NONE}` | Same as `POST And Expect` but for a documented GET. If an agent-family suite ever needs a documented GET trigger, branch on `${request}[method]` in the suite's FOR loop and call this — the shared request loop is POST-only by design (every documented agent trigger so far is a POST). |
| `Require Env Var` | `${name}  ${quickstart}` | Fail immediately, naming both the missing variable and the quickstart that needs it, unless `${name}` is set to a non-empty value. Run this before `Build Quickstart`/`Start Quickstart` for every agent-family secret, so a revoked or unset model key reads as a configuration error rather than an opaque 401 several keywords later. An empty value fails too — a misconfigured CI secret looks empty, not absent, and a bare existence check would wave that through. |
| `POST And Expect Field` | `${port}  ${path}  ${payload}  ${status}  ${field}=${NONE}` | POST JSON, assert the status code always, and — only when `${field}` is given — that the response body contains that key **and** it is non-empty. This is the agent-family equivalent of `POST And Expect`: exact-body comparison is impossible when the body embeds model output, so presence-and-non-emptiness is what remains assertable. 120s timeout (vs 30s elsewhere) because a model call sits inside the request. Cannot assert a field is *absent* or *empty* — pick a different field if that is what you need to prove (see the mcp-auth worked example in `references/agent-quickstart.md`). |

## Response-body comparisons in general

Both `POST And Expect` and `GET And Expect` parse the response as JSON
(`${response}.json()`) before comparing — do not compare `response.text`
against a JSON string; whitespace and key ordering would make an equal body
register as a mismatch.

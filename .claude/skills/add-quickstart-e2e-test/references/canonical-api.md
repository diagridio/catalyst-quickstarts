# Canonical quickstarts: `workflow`, `state`, `pubsub`, `invocation`

An (api × language) matrix: one suite per API
(`<api>/tests/quickstart.robot`), one language-tagged test case per language
inside it, and all the test data for every (api, language) pair in a single
central table, `tools/qs-tester/variables/quickstarts.py`. Read that file and
`state/tests/quickstart.robot` before writing anything — this reference points
at the real conventions, it does not restate them in full.

## README sections map onto the table directly

Every canonical README is numbered, and `docsync/check_readme_sync.py::check`
reads specific sections by number (`_section_span`, `_HEADING`):

| README section | Table entry | Notes |
|---|---|---|
| `## 4. Install Dependencies` | `INSTALL[(api, language)]` | A single command string. `npm install` in the README and `npm ci` in the harness are treated as equivalent by doc-sync (see below) — do not "fix" `INSTALL` to say `npm install`. |
| `## 5. Run the application with Catalyst Cloud` | `RUN[(api, language)]` | `--project <api>-quickstart` in the README becomes `--project {project}` in the harness; `normalise_run_command` collapses both to `--project PROJECT` before comparing, so this is the one substitution doc-sync already tolerates. |
| `## 6. Call the <X> API` (and its `6.1`, `6.2` subsections) | the request/assertion keywords in the suite, plus the `*_BODY` dicts | `extract_curl_calls` parses documented curl invocations for method/URL/payload; `extract_json_blocks` parses the documented expected response bodies. |

`check` also verifies documented payloads are one of the harness's known payload
constants (`ORDER_PAYLOAD`, `WORKFLOW_PAYLOAD`) and that every documented JSON
response body appears among what `_harness_bodies(api, language)` asserts.
`_harness_bodies` is deliberately thin for `workflow`: the start response is
documented only with a placeholder instance id (`extract_json_blocks` skips
blocks containing `<...>` placeholders as illustrative, not assertable), and
only the python README shows a concrete status body — the other three
languages' status assertions stay weak (200 plus non-empty body, no shape
check) because nothing else to compare against exists.

Two equivalences `check()` already treats as "the same," so do not chase these
as mismatches:

- `source .venv/bin/activate` (README) vs `. .venv/bin/activate` (harness) —
  same shell builtin, different spelling.
- `npm install` (README) vs `npm ci` (harness) — deliberately different
  commands. The README's advice is right for a human on a fresh checkout;
  `npm ci` is right for CI because `npm install` rewrites `package-lock.json`
  (it normalises the lockfile's `name` field to the directory name), which
  would dirty the tree on every javascript leg. This is a real, intentional
  divergence, not a doc-sync gap to close.

## Every dict in `quickstarts.py` needs the new key

Adding a language or an API means adding an entry to every one of these, keyed
consistently:

- `INSTALL`, `RUN` — keyed `(api, language)`.
- `HEALTH_PORTS` — keyed by **`api` only**. The apps always listen on
  5001/5002 regardless of `appPort` (`appPort` only controls whether Catalyst
  opens an inbound tunnel to that port, not what the app itself binds to), so
  this stays uniform across languages for a given API. `get_quickstart` turns
  each port into a `(port, "/")` probe for `Wait Until Apps Healthy`, and `/` is
  correct here because every canonical implementation routes it — check that the
  implementation you are adding does too (`app.get('/')`, `app.MapGet("/")`,
  `@GetMapping(path = "/")`, `app.get("/", ...)`) rather than inheriting the
  assumption. An app that serves no `/` makes the health gate a guaranteed
  timeout; that is exactly the trap `agents/langgraph` fell into.
- `CONNECTED_APPS` — keyed `(api, language)`, **not** `api` alone, because the
  divergence here is real: pubsub's `publisher` has a non-zero `appPort` in
  csharp and python but not in java or javascript (verified against each
  language's dev config), so `diagrid dev run` only emits `Connected App ID
  "publisher" to http://localhost:5001` for two of the four languages. Do not
  collapse this back into a per-API dict on the assumption it is a typo — it
  was checked, and the four language dev configs genuinely differ.
- The response-body dicts relevant to the API (`STATE_STORE_BODY`,
  `STATE_RETRIEVE_BODY`, `PUBSUB_PUBLISH_BODY`, `WORKFLOW_INSTANCE_KEY`, or a
  new one for a new API), each keyed by language where the body diverges.
- Any log-marker dict that diverges by language (see the worked examples
  below).
- `LANGUAGES` / `APIS` in the same file, if you are adding a genuinely new
  language or API rather than filling in an existing one.

## Divergence is a fact to transcribe, not a shape to guess

These three are real, already-transcribed divergences in `quickstarts.py` —
study them as the model for what "read the README/app, don't guess" produces,
not as a checklist to copy elsewhere:

```python
# state 6.1 store, 201 Created — java names the id field `orderId`, not `id`
STATE_STORE_BODY = {
    "csharp": {"id": 1, "message": "Order created successfully"},
    "javascript": {"id": 1, "message": "Order created successfully"},
    "python": {"id": 1, "message": "Order created successfully"},
    "java": {"orderId": 1, "message": "Order created successfully"},
}

# state 6.2 retrieve, 200 OK — python stores the STRING form of its model
STATE_RETRIEVE_BODY = {
    "csharp": {"data": {"orderId": 1}},
    "javascript": {"data": {"orderId": 1}},
    "java": {"data": {"orderId": 1}, "message": ""},
    "python": {"data": "orderId=1"},
}

# workflow 6.1 start — the key holding the instance id; javascript returns
# snake_case where the other three return camelCase
WORKFLOW_INSTANCE_KEY = {
    "csharp": "instanceId",
    "java": "instanceId",
    "python": "instanceId",
    "javascript": "instance_id",
}
```

Each of these came from reading the actual README (or the app source where the
README does not show a concrete body) for that specific language — never from
assuming one language's shape generalises to the others. When you add a
language, read its README (and its app source, where the README is silent) the
same way; do not fill in a new column by copying an existing one's shape.

## Adding a language or an API

1. Add the new `(api, language)` (or new `api`) entries to every dict listed
   above, transcribed from the new README (and app source/dev config where the
   README is silent about a port or field name — record in a comment where the
   value came from).
2. Add a language-tagged test case to the relevant `<api>/tests/quickstart.robot`
   calling the suite's existing shared keyword (see `state/tests/quickstart.robot`
   for the pattern: one `[Tags] <language>` test case per language, all calling
   `Run <Api> Quickstart    <language>`).
3. Run `uv run python docsync/check_readme_sync.py --all` from
   `tools/qs-tester` — it tells you what you missed.
4. Add the language to the CI matrix in `.github/workflows/e2e-quickstarts.yml`
   (the `e2e` job's hand-written `lang` matrix — this job is intentionally not
   driven by the suite manifest, unlike `e2e-agents`), and a runtime-setup step
   for it if the language is new to that job (see the `if: matrix.lang ==
   '...'` / `actions/setup-*` steps already there for the pattern).

## The manifest row is a pointer, not a second copy of the table

A canonical row in `tools/qs-tester/variables/suites.py` carries `suite`,
`family: "canonical"`, `api`, `languages` (the tuple of all four), `nightly`,
and `secrets` (empty for every canonical row today — no canonical quickstart
needs a model key). It does **not** duplicate ports, bodies, or markers — those
stay solely in `quickstarts.py`, read only through `get_quickstart(api,
language)`. `nightly` is present on a canonical row only because
`_REQUIRED["canonical"]` in `suites.py` demands the key for every row regardless
of family — nothing ever reads its value for a canonical row. The only code
that reads `nightly` anywhere is `suites.agent_suites(nightly_only=...)`, and
that function filters to `family == "agent"` before it ever looks at the field,
so a canonical row's `nightly` is inert: set it to whatever you like and
nothing downstream changes. Canonical scheduling is entirely the hand-written
`e2e` job's own `lang` matrix, unrelated to this manifest. Contrast
`references/agent-quickstart.md`, where `nightly` on an *agent* row really does
gate the `e2e-agents` CI matrix.

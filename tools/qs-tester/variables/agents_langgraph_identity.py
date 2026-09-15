"""Data for the agents/langgraph-identity end-to-end suite.

Every command here is transcribed verbatim from
agents/langgraph-identity/README.md, with one substitution: the documented
project name becomes `{project}`. The README is the source of truth. Change the
README, change this file, and `docsync/check_readme_sync.py --all` will tell you
if you changed only one.

WHAT THIS SUITE COVERS. The quickstart demonstrates INBOUND end-user identity:
Catalyst verifies the caller's identity-provider token at the edge, exchanges it
with dataplane Sentry, and passes a Catalyst-signed identity to the app in
`X-Diagrid-User-Token`, where `OAuthMiddleware` verifies it and puts a
`VerifiedUser` on `request.state.diagrid_user`. The suite asserts the plumbing (install,
documented provisioning, dev tunnel, uvicorn serving) plus the one HTTP outcome
that is deterministic without a credential: an unauthenticated request is
rejected 401 with the exact body the middleware returns, on both documented
routes.

WHAT IT DOES NOT COVER. Any request that carries a credential. Nothing in this
harness can mint a token dataplane Sentry has signed, and `POST And Expect
Field` / `POST And Expect` / `GET And Expect` take no headers argument, so the
200 and the 403 the README documents are unreachable from here. Both documented
`diagrid call invoke` forms are in UNCOVERED with that reason, and the gap is
recorded in the harness README's Limitations. So this suite proves the middleware
REFUSES correctly; it does not prove a verified identity reaches the handler --
and, measured rather than assumed, it cannot even tell a project with inbound
identity enabled from one without it, because the missing-token 401 is returned
before the verifier is ever built. See REQUESTS.

The OUTBOUND leg (an agent's on-behalf-of token reaching a downstream MCP tool)
is absent from the quickstart on purpose, not by omission: it does not work in
any environment today. Nothing here may imply a downstream MCP server receives a
delegated JWT.
"""

from pathlib import Path

# This module lives flat in variables/, like every other data module, so this is
# parents[3] regardless of how deep the quickstart itself sits.
REPO_ROOT = Path(__file__).resolve().parents[3]

FAMILY = "agents"
NAME = "langgraph-identity"
LANGUAGE = "python"

# README "## Run with Catalyst", step 2. Replaced by an ephemeral qs-ci-* name at
# run time; also what doc-sync maps onto `{project}` when comparing.
DOCUMENTED_PROJECT = "langgraph-identity-quickstart"

QUICKSTART_DIR = str(REPO_ROOT / "agents" / "langgraph-identity")

# appID and appPort from dev-python-langgraph-identity.yaml, which is also what
# the documented curls target and what the documented readiness line prints.
# Single-sourced because each value appears in three places below, and a run
# against a port one of them disagreed about fails in a way that looks like a
# broken quickstart rather than a broken data module.
APP_ID = "identity-agent"
APP_PORT = 8006

# README "## Run with Catalyst", step 2. One command, and no `agent create`: this
# is a plain FastAPI app with no Diagrid agent runner and no Dapr Workflow, so
# `dev run` creates the App ID itself. The three managed-service skips live on
# RUN, where the README puts them, not here.
SETUP = ("diagrid project create {project} --use --wait",)

# README "## Setup". The documented `cd agents/langgraph-identity` is expressed as
# the working directory instead of a command.
INSTALL = "uv sync"

# README "## Run with Catalyst", step 3. Bare of `--project` on purpose: the
# documented `project create` carries `--use`, and reproducing that dependency is
# deliberate, so a regression in `--use` breaks this suite instead of silently
# breaking readers.
#
# The three `--skip-managed-*` flags are transcribed, not chosen. This app calls
# no Dapr building block, and without them `dev run` provisions a KV store, a
# broker and a workflow store the first time it creates the App ID -- minutes of
# a CI leg spent on infrastructure nothing here touches.
RUN = (
    "uv run diagrid dev run -f dev-python-langgraph-identity.yaml --approve "
    "--skip-managed-kv --skip-managed-pubsub --skip-managed-workflow"
)

# Empty on purpose: this README documents no cleanup command. It has no
# "## Clean Up" section and no `diagrid project delete`, so deleting the project
# is infrastructure here and `ci/teardown-project.sh` owns it. Same shape as
# agents/langgraph. Adding a plausible-looking delete would be inventing a
# documented command, and doc-sync would correctly reject it.
TEARDOWN = ()

# README "## Run with Catalyst", step 3: "Wait until the output shows
# `Uvicorn running on http://0.0.0.0:8006`". Transcribed complete rather than
# truncated at `Uvicorn running on` (which is what agents/langgraph does, because
# its README writes the address as a `<localhost:port>` placeholder): this README
# documents the concrete line, and main.py really binds host 0.0.0.0 on APP_PORT,
# which dev-python-langgraph-identity.yaml sets to 8006. The stronger form also
# fails loudly if the dev config's port and this module's ever diverge.
#
# ONE marker, and there is no second one to add. main.py logs
# `[IDENTITY] verified caller subject=...` and `[IDENTITY] tool call for
# subject=...`, but both are on the AUTHENTICATED path -- the first inside
# `POST /agent/run` after the middleware has admitted the request, the second in
# the `tools` node one step later. Neither can appear in a run this suite can
# produce. It prints nothing at all when the middleware is installed, so "the
# middleware is loaded" is not separately assertable: the 401 in REQUESTS is the
# evidence for that, and it is evidence produced by the shipped middleware.
READY_MARKERS = (f"Uvicorn running on http://0.0.0.0:{APP_PORT}",)

# EMPTY, and the reason is specific to this quickstart rather than to agent apps
# in general. `Wait Until Apps Healthy` polls for a 200. `require_auth` defaults
# to True -- the whole point of the demo -- and OAuthMiddleware is a
# BaseHTTPMiddleware wrapping EVERY route, so every path answers
# 401 oauth.missing_token until a verified credential arrives. The shipped
# OAuthConfig (diagrid 0.4.4) has exactly five fields --
# scopes/issuer/audience/jwks_uri/require_auth -- and no exclude_paths, so no
# probe path can be exempted, which is also why the quickstart exposes no health
# route and why dev-python-langgraph-identity.yaml sets
# `enableAppHealthCheck: false`. There is nothing here that can answer 200, so
# there is nothing to probe: readiness rests on `Wait Until Apps Connected` plus
# the READY_MARKERS line above.
HEALTH_PROBES = ()

# (appID, port) pairs `diagrid dev run` reports as
# `Connected App ID "<id>" to http://localhost:<port>`. Read from
# dev-python-langgraph-identity.yaml, whose single app has appID identity-agent on
# appPort 8006.
#
# Required, not optional: `Start Quickstart` records these so `Stop Quickstart`
# can release each local app connection, and a run that skips that leaves a
# trust.diagrid.io endpoint pointing at a dead tunnel, which makes the next run's
# 500s ambiguous. That an agent app emits this line at all is observed -- the other
# four registered agent suites have seen it live -- but not yet for THIS app.
CONNECTED_APPS = ((APP_ID, APP_PORT),)

# EMPTY, and unlike the other agent suites this is a decision rather than a gap.
# `Wait Until Catalyst Attached` guards the window in which a WORKFLOW call hangs
# unrecoverably (measured on agents/langgraph, 2026-08-27: a POST at readiness+0
# hung for the full 120s client timeout and twelve retries over 181s never
# recovered it). This quickstart starts no workflow -- it is a plain FastAPI app
# with no Diagrid runner and no Dapr building block, and both requests below are
# refused by the middleware before any Dapr call is made. The window this gate
# exists for is not one this suite enters.
#
# Left empty rather than guessed for the ordinary reason too: the marker is
# whatever THIS app's logging makes visible for an inbound request from Catalyst,
# and nobody has watched this app's dev-run output yet. uvicorn's access log would
# show Catalyst's `GET /dapr/config` probe -- now answering 401 rather than
# agents/langgraph's 404, since the middleware wraps that path too -- but that is
# inference, not observation. A marker that never appears makes the gate time out
# loudly; a marker matched from the wrong line lets the suite through early and
# silently. Fill it in from a real run, or leave it empty and say why.
CATALYST_PROBE_MARKERS = ()

# Empty. The quickstart ships a canned offline model (fake_model.py) and reaches a
# real provider only when DIAGRID_QUICKSTART_MODEL=openai, which this suite does
# not set -- and `build_model()` imports langchain_openai lazily, inside that
# branch, so the app starts with no key at all. Both requests below are refused
# before the graph runs anyway. Keep in step with the `secrets` entry in
# suites.py: one without the other is a declaration that lies.
SECRETS = ()

# The documented calls, in documented order. README "### 4. See It Fail Closed".
#
# TWO requests, and both are the negative case. That is not a thin suite by
# accident -- it is the only HTTP outcome assertable here, and it is asserted on
# both documented routes:
#
#   * With no `X-Diagrid-User-Token` header and require_auth=True, the middleware
#     returns 401 with body exactly {"error": "oauth.missing_token"} (diagrid
#     0.4.4, `_error_response` in identity/asgi.py). No verifier is built, no JWKS
#     is fetched, no sidecar and no model is touched on that path, so it is
#     byte-identical run to run -- which is why these assert the EXACT body
#     (`GET And Expect` / `POST And Expect`) rather than settling for the
#     field-presence check `POST And Expect Field` performs. There is no model
#     output in a 401 to make an exact comparison impossible.
#   * The AUTHENTICATED calls cannot be expressed: no keyword here takes headers,
#     and nothing here can mint a token dataplane Sentry signed. See UNCOVERED.
#   * A MALFORMED-token case is deliberately absent, because which rejection you
#     get depends on state this suite does not control. With a verifier built it
#     is 401 oauth.decode_error; with no discoverable issuer `build_verifier`
#     raises RuntimeError and the middleware answers 503 oauth.not_configured
#     first, never reaching the token at all. Asserting either would encode the
#     environment rather than the behaviour. test_identity.py pins the 401 with
#     the offline issuer, where the verifier is guaranteed to exist.
#
# All four outcomes above were MEASURED, not reasoned, against diagrid 0.4.5 in
# the quickstart's own venv -- OAuthMiddleware over a two-route FastAPI app under
# starlette's TestClient, no Catalyst and no network:
#
#     GET  /whoami    no header             -> 401 {"error": "oauth.missing_token"}
#                                              cache-control: no-store
#     POST /agent/run no header             -> 401 {"error": "oauth.missing_token"}
#     GET  /whoami    malformed token       -> 401 {"error": "oauth.decode_error"}
#     GET  /whoami    no issuer discoverable-> 503 {"error": "oauth.not_configured"}
#
# One result from that probe is a LIMITATION of this suite rather than a
# reassurance, and it is the one worth carrying forward: the missing-token branch
# runs BEFORE `_get_verifier()`, so with no issuer discoverable at all -- no
# `identity` block in the sidecar's /v1.0/metadata, nothing federated on the
# project -- the unauthenticated request still answers exactly
# `401 oauth.missing_token` (measured: last line of the probe). Both assertions
# below therefore pass unchanged against a project on which inbound identity was
# never enabled, while every credential-bearing request to that same app would
# answer 503. This suite cannot tell those two projects apart. That is the
# sharpest edge of "proves the middleware refuses, not that identity works", and
# it is why the 403 and 200 live in a test that can present a credential:
# agents/langgraph-identity/test_identity.py, which mints one offline. That test
# cannot substitute for this suite either -- it exercises no Catalyst at all --
# so the two are complements, and neither alone proves the live inbound path.
#
# The status is a TRANSCRIPTION here, unlike every other agent suite: the README
# prints `HTTP/1.1 401 Unauthorized` and the body beneath the first curl. Keep it
# that way -- if the README stops showing it, this becomes an assumption and this
# comment has to say so.
#
# `log_marker` deliberately absent on both. uvicorn's access log does print
# `"GET /whoami HTTP/1.1" 401 Unauthorized`, but asserting it adds nothing the
# body comparison has not already asserted, and doc-sync would then require that
# line inside a fenced block in the README.
#
# Optional keys a request may carry, of which these use one:
#   body        the exact expected response body, compared as parsed JSON
#   field       a field that must be present and non-empty, for a response whose
#               body varies (model output); no request here needs it
#   commands    documented commands to run before this request
#   log_marker  a string to wait for in the dev-run output afterwards
_MISSING_TOKEN_BODY = {"error": "oauth.missing_token"}

REQUESTS = (
    # README's first fail-closed curl, and the one whose response it prints in
    # full. `GET /whoami` runs no model turn and no tool, so this is the cheapest
    # place in the quickstart to see the middleware's verdict on its own.
    {
        "method": "GET",
        "port": APP_PORT,
        "path": "/whoami",
        # A GET carries none. The key must exist regardless: doc-sync reads
        # `request["payload"]` directly and skips the check only when it is None.
        "payload": None,
        "status": 401,
        "body": _MISSING_TOKEN_BODY,
    },
    # README's second fail-closed curl, under "Every route answers the same way".
    # The README prints the response block only once, above, so the body here is
    # transcribed from test.http (`### Run the agent with no credential: 401
    # {"error": "oauth.missing_token"}`) -- and then measured, in the offline
    # probe recorded above, on this exact route. Worth asserting separately rather
    # than trusting the prose: this is the route that would matter, and
    # "require_auth is app-wide, not per-path" is precisely the claim it checks.
    {
        "method": "POST",
        "port": APP_PORT,
        "path": "/agent/run",
        "payload": {"task": "What bookings do I have?"},
        "status": 401,
        "body": _MISSING_TOKEN_BODY,
    },
)

# Documented commands this suite deliberately does not run, each with its reason.
# doc-sync fails if a documented command is in neither this tuple nor the suite,
# so a new documented step forces a decision instead of being quietly ignored.
# Each line is transcribed EXACTLY as the README's bash block writes it
# (backslash continuations joined, whitespace collapsed), or the
# harness -> documented direction rejects it.
UNCOVERED = (
    (
        "diagrid call invoke get identity-agent.whoami --id identity-agent --verbose",
        "the authenticated path, and the one the whole quickstart is about. It "
        "needs a credential this harness cannot produce: no keyword here takes "
        "headers, and the middleware verifies the signature against a dataplane "
        "Sentry JWKS. Running the CLI form would assert rc==0 and nothing about "
        "the body -- and the README itself says a plain Diagrid login carries "
        "`openid profile email offline_access` and so answers 403 "
        "oauth.missing_scope here, which is not a documented failure but the "
        "documented outcome without a federated identity provider",
    ),
    (
        "diagrid call invoke post identity-agent.agent/run --id identity-agent "
        "--verbose -d '{\"task\": \"What bookings do I have?\"}'",
        "same reason as the whoami call above: it is the authenticated path. This "
        "is the one whose answer names the verified caller, so it is the assertion "
        "worth having and the one this harness cannot make",
    ),
    (
        "DIAGRID_QUICKSTART_IDENTITY=local APP_PORT=8006 uv run python main.py",
        "README '## Run Offline Without a Catalyst Project'. It replaces Catalyst "
        "with a throwaway in-process issuer to make the 200, 403 and 401 reachable "
        "with no project at all, and it binds the same port 8006 as `dev run`. That "
        "makes it an alternative to this suite's entire flow rather than a step "
        "inside it: it exercises no Catalyst, and running it here would collide "
        "with the app this suite already has serving. The 200 and 403 paths this "
        "suite cannot reach are covered instead by "
        "agents/langgraph-identity/test_identity.py, which drives the same offline "
        "issuer under starlette's TestClient and runs in "
        ".github/workflows/agents_langgraph_identity_python.yaml",
    ),
)


def get_quickstart():
    """Everything the suite needs, in one flat dict.

    Robot calls this as a keyword: `${qs}=  Get Quickstart`.

    NOT the same dict `quickstarts.get_quickstart(api, language)` returns. The two
    share exactly the five keys the *shared* keywords read -- `dir`, `install`,
    `run`, `health_probes` and `connected_apps` -- which is what lets
    `Build Quickstart`, `Start Quickstart`, `Wait Until Apps Connected` and
    `Wait Until Apps Healthy` work against either shape unchanged. Beyond those,
    this dict adds `family`, `name`, `language`, `setup`, `teardown`, `secrets`
    and `catalyst_probe_markers`.

    READY_MARKERS and REQUESTS are deliberately NOT here: the suite reads them
    from its `Variables` import so the mutation check's --variablefile can
    actually replace them. A value returned by a Python keyword cannot be
    overridden that way, and a mutation run that silently used the real markers
    would pass and prove nothing.
    """
    return {
        "family": FAMILY,
        "name": NAME,
        "language": LANGUAGE,
        "dir": QUICKSTART_DIR,
        "setup": list(SETUP),
        "install": INSTALL,
        "run": RUN,
        "teardown": list(TEARDOWN),
        "health_probes": [list(probe) for probe in HEALTH_PROBES],
        "catalyst_probe_markers": list(CATALYST_PROBE_MARKERS),
        "connected_apps": [list(pair) for pair in CONNECTED_APPS],
        "secrets": list(SECRETS),
    }

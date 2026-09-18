"""Data for the agents/langgraphjs/enterprise-identity end-to-end suite.

The TypeScript sibling of agents_enterprise_identity.py, which carries the
Python quickstart at agents/langgraph/enterprise-identity. The two are separate
quickstarts with separate READMEs, so they get separate modules rather than a
language dimension: doc-sync reads one README per data module.

Every command here is transcribed verbatim from
agents/langgraphjs/enterprise-identity/README.md, with one substitution: the
documented project name becomes `{project}`. The README is the source of truth.
Change the README, change this file, and `docsync/check_readme_sync.py --all`
will tell you if you changed only one.

WHAT THIS SUITE COVERS. The quickstart demonstrates INBOUND end-user identity:
Catalyst verifies the caller's identity-provider token at the edge, exchanges it
with dataplane Sentry, and passes a Catalyst-signed identity to the app in
`X-Diagrid-User-Token`, where `oauthMiddleware` verifies it and attaches a
`VerifiedUser` that `getVerifiedUser(req)` returns. The suite asserts the
plumbing (install, documented provisioning, dev tunnel, express serving) plus
the one HTTP outcome that is deterministic without a credential: an
unauthenticated request is rejected 401 with the exact body the middleware
returns, on both documented routes.

WHAT IT DOES NOT COVER. Any request that carries a credential. Nothing in this
harness can mint a token dataplane Sentry has signed, and `POST And Expect
Field` / `POST And Expect` / `GET And Expect` take no headers argument, so the
200 and the 403 the README documents are unreachable from here. Both documented
`diagrid call invoke` forms are in UNCOVERED with that reason, and the gap is
recorded in the harness README's Limitations. So this suite proves the
middleware REFUSES correctly; it does not prove a verified identity reaches the
handler -- and, measured rather than assumed, it cannot even tell a project with
inbound identity enabled from one without it, because the missing-token 401 is
returned before the verifier is ever built. See REQUESTS.

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
NAME = "enterprise-identity-js"
LANGUAGE = "javascript"

# README "## Run with Catalyst", step 1. Replaced by an ephemeral qs-ci-* name at
# run time; also what doc-sync maps onto `{project}` when comparing.
#
# Deliberately NOT the Python quickstart's `enterprise-identity-quickstart`: the
# two quickstarts ship in the same repository, and a reader who runs both in
# order would otherwise hit "project already exists" on the second.
DOCUMENTED_PROJECT = "enterprise-identity-js-quickstart"

# Three segments, and all three are load-bearing: `langgraphjs` is a framework
# directory beside `langgraph`, so a two-segment path would point at nothing.
# `Build Quickstart` and `Run Documented Commands` both cd into this, so a wrong
# path fails at install in a way that reads like a broken quickstart.
QUICKSTART_DIR = str(REPO_ROOT / "agents" / "langgraphjs" / "enterprise-identity")

# appID and appPort from dev-enterprise-identity.yaml, which is also what the
# documented curls target and what the documented readiness line prints.
# Single-sourced because each value appears in three places below, and a run
# against a port one of them disagreed about fails in a way that looks like a
# broken quickstart rather than a broken data module.
APP_ID = "identity-agent"
APP_PORT = 8006

# `identity-agent` is created before the MCPServer on purpose: crm-mcp.yaml
# scopes the CRM to that App ID, and Catalyst rejects a scope naming an App ID
# that does not exist yet. The CRM's own App ID must NOT be created here --
# registering the MCP server creates it, and a hand-made one collides by name.

#
# The two `apply` commands register the CRM and its access policy. The policy is
# what carries `requireUser: true`, so without it the outbound leg the README
# walks through would silently downgrade to no user identity at all.
SETUP = (
    "diagrid project create {project} --use --wait",
    "diagrid agent create identity-agent --wait",
    "diagrid apply -f resources/crm-mcp.yaml",
    "diagrid apply -f resources/crm-mcp-access.yaml",
)

# README "## Setup". The documented `cd agents/langgraphjs/enterprise-identity`
# is expressed as the working directory instead of a command.
#
# `npm install` and not `npm ci`, unlike the canonical javascript quickstarts in
# quickstarts.py: an agent row's INSTALL is compared against the README's own
# bash lines in both directions, so substituting `npm ci` here would fail
# doc-sync. It is safe to run in CI for the ordinary reason `npm ci` was
# introduced to avoid -- a rewritten lockfile `name` field -- because
# package.json's `name` and package-lock.json's already agree, so the install is
# a no-op on the lockfile.
INSTALL = "npm install"

# README "## Run with Catalyst", step 1, item 4. Bare of `--project` on purpose:
# the documented `project create` carries `--use`, and reproducing that
# dependency is deliberate, so a regression in `--use` breaks this suite instead
# of silently breaking readers.
#
# No `uv run` prefix, unlike the Python sibling: the Diagrid CLI is on PATH and
# nothing here runs inside a Python environment.
#
# The three `--skip-managed-*` flags are transcribed, not chosen. This app calls
# no Dapr building block, and without them `dev run` provisions a KV store, a
# broker and a workflow store the first time it creates the App ID -- minutes of
# a CI leg spent on infrastructure nothing here touches.
RUN = (
    "diagrid dev run -f dev-enterprise-identity.yaml --approve "
    "--skip-managed-kv --skip-managed-pubsub --skip-managed-workflow"
)

# Empty on purpose: this README documents no cleanup command. It has no
# "## Clean Up" section and no `diagrid project delete`, so deleting the project
# is infrastructure here and `ci/teardown-project.sh` owns it. Same shape as the
# Python sibling. Adding a plausible-looking delete would be inventing a
# documented command, and doc-sync would correctly reject it.
TEARDOWN = ()

# README "## Run with Catalyst", step 1, item 4: "Wait until the output shows
# `Listening on http://0.0.0.0:8006`". Transcribed complete rather than
# truncated at `Listening on`: main.ts really binds host 0.0.0.0 on APP_PORT,
# which dev-enterprise-identity.yaml sets to 8006, and the README prints the
# concrete line in the offline section's output block too. The stronger form
# also fails loudly if the dev config's port and this module's ever diverge.
#
# ONE marker, and there is no second one to add. main.ts logs
# `[IDENTITY] verified caller subject=...` and `[IDENTITY] tool call for
# subject=...`, but both are on the AUTHENTICATED path -- the first inside
# `POST /agent/run` after the middleware has admitted the request, the second in
# the `tools` node one step later. Neither can appear in a run this suite can
# produce. The middleware prints nothing at all when it is installed, so "the
# middleware is loaded" is not separately assertable: the 401 in REQUESTS is the
# evidence for that, and it is evidence produced by the shipped middleware.
READY_MARKERS = (f"Listening on http://0.0.0.0:{APP_PORT}",)

# EMPTY, and the reason is specific to this quickstart rather than to agent apps
# in general. `Wait Until Apps Healthy` polls for a 200. `requireAuth` defaults
# to True -- the whole point of the demo -- and `oauthMiddleware` is installed
# with `app.use`, ahead of every route, so every path answers
# 401 oauth.missing_token until a verified credential arrives. The shipped
# `OAuthConfig` (@diagrid/agent-core 0.2.0) has exactly six fields --
# scopes/issuer/audience/jwksUri/requireAuth/allowInsecureJwks -- and no
# per-path exclusion, so no probe path can be exempted, which is also why the
# quickstart exposes no health route and why dev-enterprise-identity.yaml sets
# `enableAppHealthCheck: false`. There is nothing here that can answer 200, so
# there is nothing to probe: readiness rests on `Wait Until Apps Connected` plus
# the READY_MARKERS line above.
HEALTH_PROBES = ()

# (appID, port) pairs `diagrid dev run` reports as
# `Connected App ID "<id>" to http://localhost:<port>`. Read from
# dev-enterprise-identity.yaml, whose agent app has appID identity-agent on
# appPort 8006. The second app (crm-mcp on 8007) is deliberately absent: the
# suite never reaches it, since both documented requests are refused before any
# tool call, and listing it would make readiness wait on a connection this run
# does not need.
#
# Required, not optional: `Start Quickstart` records these so `Stop Quickstart`
# can release each local app connection, and a run that skips that leaves a
# trust.diagrid.io endpoint pointing at a dead tunnel, which makes the next
# run's 500s ambiguous. That an agent app emits this line at all is observed --
# the agent suites already registered have seen it live -- but not yet for THIS
# app, and not yet for any app this repository starts with `npm`.
CONNECTED_APPS = ((APP_ID, APP_PORT),)

# EMPTY, and unlike the other agent suites this is a decision rather than a gap.
# `Wait Until Catalyst Attached` guards the window in which a WORKFLOW call hangs
# unrecoverably (measured on agents/langgraph, 2026-08-27: a POST at readiness+0
# hung for the full 120s client timeout and twelve retries over 181s never
# recovered it). This quickstart starts no workflow -- it is a plain express app
# with no Diagrid runner and no Dapr building block, and both requests below are
# refused by the middleware before any Dapr call is made. The window this gate
# exists for is not one this suite enters.
#
# Left empty rather than guessed for the ordinary reason too: the marker is
# whatever THIS app's logging makes visible for an inbound request from Catalyst,
# and nobody has watched this app's dev-run output yet. express has no access log
# at all by default -- unlike uvicorn in the Python sibling, where Catalyst's
# `GET /dapr/config` probe would at least appear -- so there may be no candidate
# line to fill in. A marker that never appears makes the gate time out loudly; a
# marker matched from the wrong line lets the suite through early and silently.
# Fill it in from a real run, or leave it empty and say why.
CATALYST_PROBE_MARKERS = ()

# Empty. The quickstart ships a canned offline model (model.ts) and reaches a
# real provider only when DIAGRID_QUICKSTART_MODEL=openai, which this suite does
# not set -- and `buildModel()` imports `@langchain/openai` dynamically, inside
# that branch, so the app starts with no key at all. Both requests below are
# refused before the graph runs anyway. Keep in step with the `secrets` entry in
# suites.py: one without the other is a declaration that lies.
SECRETS = ()

# The documented calls, in documented order. README "### 4. See It Fail Closed".
#
# TWO requests, and both are the negative case. That is not a thin suite by
# accident -- it is the only HTTP outcome assertable here, and it is asserted on
# both documented routes:
#
#   * With no `X-Diagrid-User-Token` header and requireAuth defaulting to true,
#     the middleware returns 401 with body exactly
#     {"error": "oauth.missing_token"} (@diagrid/agent-core 0.2.0,
#     `oauthMiddleware` in identity/express.ts over the `rejected` outcome in
#     identity/authenticate.ts). No verifier is built, no JWKS is fetched, no
#     sidecar and no model is touched on that path, so it is byte-identical run
#     to run -- which is why these assert the EXACT body (`GET And Expect` /
#     `POST And Expect`) rather than settling for the field-presence check
#     `POST And Expect Field` performs. There is no model output in a 401 to
#     make an exact comparison impossible.
#   * The AUTHENTICATED calls cannot be expressed: no keyword here takes headers,
#     and nothing here can mint a token dataplane Sentry signed. See UNCOVERED.
#   * A MALFORMED-token case is deliberately absent, because which rejection you
#     get depends on state this suite does not control. With a verifier built it
#     is 401 oauth.decode_error; with no discoverable issuer `buildVerifier`
#     throws IdentityNotConfiguredError and the middleware answers
#     503 oauth.not_configured first, never reaching the token at all. Asserting
#     either would encode the environment rather than the behaviour.
#     identity.test.ts pins the 401 with the offline issuer, where the verifier
#     is guaranteed to exist.
#
# The four outcomes below were MEASURED, not reasoned, against
# @diagrid/agent-core 0.2.0 in this quickstart's own node_modules -- main.ts's
# `buildApp` over its two real routes, with the offline issuer and no Catalyst:
#
#     GET  /whoami    no header             -> 401 {"error": "oauth.missing_token"}
#                                              Cache-Control: no-store
#     POST /agent/run no header             -> 401 {"error": "oauth.missing_token"}
#     GET  /whoami    malformed token       -> 401 {"error": "oauth.decode_error"}
#     GET  /whoami    wrong scope           -> 403 {"error": "oauth.missing_scope"}
#
# One property of the middleware is a LIMITATION of this suite rather than a
# reassurance, and it is the one worth carrying forward: the missing-token branch
# runs BEFORE the lazy verifier is built (identity/authenticate.ts refuses on an
# empty token before it awaits `getVerifier()`), so with no issuer discoverable
# at all -- no `identity` block in the sidecar's /v1.0/metadata, nothing
# federated on the project -- the unauthenticated request still answers exactly
# `401 oauth.missing_token`. Both assertions below therefore pass unchanged
# against a project on which inbound identity was never enabled, while every
# credential-bearing request to that same app would answer 503. This suite
# cannot tell those two projects apart. That is the sharpest edge of "proves the
# middleware refuses, not that identity works", and it is why the 403 and 200
# live in a test that can present a credential:
# agents/langgraphjs/enterprise-identity/identity.test.ts, which mints one
# offline. That test cannot substitute for this suite either -- it exercises no
# Catalyst at all -- so the two are complements, and neither alone proves the
# live inbound path.
#
# The status is a TRANSCRIPTION here, unlike most agent suites: the README prints
# `HTTP/1.1 401 Unauthorized` and the body beneath the first curl. Keep it that
# way -- if the README stops showing it, this becomes an assumption and this
# comment has to say so.
#
# `log_marker` deliberately absent on both. express logs nothing for a request
# the middleware refused, so there is no line to wait for, and adding one would
# also require that line inside a fenced block in the README.
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
    # probe recorded above, on this exact route. Worth asserting separately
    # rather than trusting the prose: this is the route that would matter, and
    # "requireAuth is app-wide, not per-path" is precisely the claim it checks.
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
        "--verbose -d '{\"task\": \"How is ACME doing?\"}'",
        "same reason as the whoami call above: it is the authenticated path. This "
        "is the one that exercises both legs -- the caller reaching the agent and "
        "the agent carrying them onward to the CRM -- so it is the assertion worth "
        "having and the one this harness cannot make",
    ),
    (
        "DIAGRID_QUICKSTART_IDENTITY=local APP_PORT=8006 npm start",
        "README '## Run Offline Without a Catalyst Project'. It replaces Catalyst "
        "with a throwaway in-process issuer to make the 200, 403 and 401 reachable "
        "with no project at all, and it binds the same port 8006 as `dev run`. That "
        "makes it an alternative to this suite's entire flow rather than a step "
        "inside it: it exercises no Catalyst, and running it here would collide "
        "with the app this suite already has serving. The 200 and 403 paths this "
        "suite cannot reach are covered instead by "
        "agents/langgraphjs/enterprise-identity/identity.test.ts, which drives the "
        "same offline issuer against main.ts's own `buildApp` and runs in "
        ".github/workflows/agents_enterprise_identity_javascript.yaml",
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

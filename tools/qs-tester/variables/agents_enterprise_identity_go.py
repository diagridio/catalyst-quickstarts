"""Data for the agents/langchaingo/enterprise-identity end-to-end suite.

Every command here is transcribed verbatim from
agents/langchaingo/enterprise-identity/README.md, with one substitution: the
documented project name becomes `{project}`. The README is the source of truth.
Change the README, change this file, and `docsync/check_readme_sync.py --all`
will tell you if you changed only one.

A separate module from `agents_enterprise_identity`, which is the PYTHON
quickstart's data. The two suites are siblings, not languages of one suite: they
have different directories, different install and run commands and different
readiness markers, so they cannot share a module the way the canonical suites
share `quickstarts.py`.

WHAT THIS SUITE COVERS. The quickstart demonstrates INBOUND end-user identity:
Catalyst verifies the caller's identity-provider token at the edge, exchanges it
with dataplane Sentry, and passes a Catalyst-signed identity to the app in
`X-Diagrid-User-Token`, where `identity.Middleware` verifies it and puts a
`*identity.VerifiedUser` in the request context. The suite asserts the plumbing
(build, documented provisioning, dev tunnel, the app serving) plus the one HTTP
outcome that is deterministic without a credential: an unauthenticated request
is rejected 401 with the exact body the middleware returns, on both documented
routes.

WHAT IT DOES NOT COVER. Any request that carries a credential. Nothing in this
harness can mint a token dataplane Sentry has signed, and `POST And Expect
Field` / `POST And Expect` / `GET And Expect` take no headers argument, so the
200 and the 403 the README documents are unreachable from here. Both documented
`diagrid call invoke` forms are in UNCOVERED with that reason, and the gap is
recorded in the harness README's Limitations. So this suite proves the
middleware REFUSES correctly; it does not prove a verified identity reaches the
handler -- and, reasoning from the SDK source rather than measuring, it cannot
even tell a project with inbound identity enabled from one without it, because
the missing-token 401 is returned before the verifier is ever built. See
REQUESTS.

The OUTBOUND leg (an agent's on-behalf-of token reaching a downstream MCP tool)
is covered by the README walkthrough, which can present a credential, and
offline by the quickstart's own Go test driving the real tool against a stand-in
MCP server. Nothing here observes it, so nothing here may imply a downstream MCP
server received a delegated JWT in a run of THIS suite.
"""

from pathlib import Path

# This module lives flat in variables/, like every other data module, so this is
# parents[3] regardless of how deep the quickstart itself sits.
REPO_ROOT = Path(__file__).resolve().parents[3]

FAMILY = "agents"
NAME = "enterprise-identity-go"
LANGUAGE = "go"

# README "## Run with Catalyst", step 1. Replaced by an ephemeral qs-ci-* name at
# run time; also what doc-sync maps onto `{project}` when comparing.
DOCUMENTED_PROJECT = "enterprise-identity-quickstart"

# The full path, langchaingo segment included. Note that the python sibling's
# module has `agents/enterprise-identity` here, missing its `langgraph`
# segment -- that looks like a real bug in it rather than a convention, so it is
# deliberately not mirrored.
QUICKSTART_DIR = str(REPO_ROOT / "agents" / "langchaingo" / "enterprise-identity")

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

# README "## Setup". The documented `cd agents/langchaingo/enterprise-identity`
# is expressed as the working directory instead of a command.
#
# `go build ./...` is not a formality here the way `uv sync` is next door. It
# downloads the module graph, warms the build cache, and -- on a runner whose Go
# is older than the 1.26.4 go.mod asks for -- fetches the toolchain. Without it
# all of that happens inside `go run` while `Wait Until Ready Marker` is already
# counting down.
INSTALL = "go build ./..."

# README "## Run with Catalyst", step 1, item 4. Bare of `--project` on purpose:
# the documented `project create` carries `--use`, and reproducing that
# dependency is deliberate, so a regression in `--use` breaks this suite instead
# of silently breaking readers.
#
# No `uv run` prefix, unlike the python sibling: the diagrid CLI is on PATH and
# there is no Python environment to enter.
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
# is infrastructure here and `ci/teardown-project.sh` owns it. Same shape as
# the python enterprise-identity suite. Adding a plausible-looking delete would
# be inventing a documented command, and doc-sync would correctly reject it.
TEARDOWN = ()

# README "## Run with Catalyst", step 1, item 4: "Wait until the output shows
# `listening on http://0.0.0.0:8006`". Transcribed complete rather than
# truncated at `listening on`: this README documents the concrete line, main.go
# really binds host 0.0.0.0 on APP_PORT, and dev-enterprise-identity.yaml sets
# that to 8006. The stronger form also fails loudly if the dev config's port and
# this module's ever diverge.
#
# ONE marker, and there is no second one to add. main.go logs
# `[IDENTITY] verified caller subject=...` and `[IDENTITY] tool call for
# subject=...`, but both are on the AUTHENTICATED path -- the first inside
# `POST /agent/run` after the middleware has admitted the request, the second in
# the tool call one step later. Neither can appear in a run this suite can
# produce.
#
# The app's other unconditional startup line ("Using the canned offline
# model: ...") is deliberately NOT a second marker: it is printed before the
# listener is bound, so matching it would let the request loop start against a
# port nothing is answering on yet.
READY_MARKERS = (f"listening on http://0.0.0.0:{APP_PORT}",)

# EMPTY, and the reason is specific to this quickstart rather than to agent apps
# in general. `Wait Until Apps Healthy` polls for a 200. `RequireAuth` resolves
# to true on the zero `OAuthConfig` -- the whole point of the demo -- and
# `identity.Middleware` wraps EVERY route, so every path answers
# 401 oauth.missing_token until a verified credential arrives. The shipped
# OAuthConfig (go-ai v0.2.0) has exactly five fields --
# Scopes/Issuer/Audience/JWKSURI/RequireAuth, plus AllowInsecureJWKS -- and no
# path exclusions, so no probe path can be exempted, which is also why the
# quickstart exposes no health route and why dev-enterprise-identity.yaml sets
# `enableAppHealthCheck: false`. There is nothing here that can answer 200, so
# there is nothing to probe: readiness rests on `Wait Until Apps Connected` plus
# the READY_MARKERS line above.
HEALTH_PROBES = ()

# (appID, port) pairs `diagrid dev run` reports as
# `Connected App ID "<id>" to http://localhost:<port>`. Read from
# dev-enterprise-identity.yaml, whose agent app has appID identity-agent on
# appPort 8006.
#
# Required, not optional: `Start Quickstart` records these so `Stop Quickstart`
# can release each local app connection, and a run that skips that leaves a
# trust.diagrid.io endpoint pointing at a dead tunnel, which makes the next
# run's 500s ambiguous.
#
# Only the agent app, not crm-mcp. The suite never reaches the CRM: both
# documented requests are refused by the agent's middleware, so the CRM's
# connection is not part of what readiness means here, and listing it would make
# the connection gate wait on a tunnel this run has no use for.
CONNECTED_APPS = ((APP_ID, APP_PORT),)

# EMPTY, and unlike the other agent suites this is a decision rather than a gap.
# `Wait Until Catalyst Attached` guards the window in which a WORKFLOW call hangs
# unrecoverably (measured on agents/langgraph, 2026-08-27: a POST at readiness+0
# hung for the full 120s client timeout and twelve retries over 181s never
# recovered it). This quickstart starts no workflow -- it is a plain net/http app
# with no Diagrid runner and no Dapr building block, and both requests below are
# refused by the middleware before any Dapr call is made. The window this gate
# exists for is not one this suite enters.
#
# Left empty rather than guessed for the ordinary reason too: the marker is
# whatever THIS app's logging makes visible for an inbound request from Catalyst,
# and nobody has watched this app's dev-run output yet. It writes no access log
# at all -- net/http has none and this app adds none -- so unlike the python
# sibling there is not even a uvicorn line to infer from. A marker that never
# appears makes the gate time out loudly; a marker matched from the wrong line
# lets the suite through early and silently. Fill it in from a real run, or
# leave it empty and say why.
CATALYST_PROBE_MARKERS = ()

# Empty. The quickstart ships a canned offline model (fake_model.go) and reaches
# a real provider only when DIAGRID_QUICKSTART_MODEL=openai, which this suite
# does not set -- and `buildModel` constructs the OpenAI client only inside that
# branch, so the app starts with no key at all. Both requests below are refused
# before the agent runs anyway. Keep in step with the `secrets` entry in
# suites.py: one without the other is a declaration that lies.
SECRETS = ()

# The documented calls, in documented order. README "### 4. See It Fail Closed".
#
# TWO requests, and both are the negative case. That is not a thin suite by
# accident -- it is the only HTTP outcome assertable here, and it is asserted on
# both documented routes:
#
#   * With no `X-Diagrid-User-Token` header and RequireAuth resolving to true,
#     the middleware returns 401 with body exactly
#     {"error": "oauth.missing_token"} (go-ai v0.2.0, `writeError` in
#     identity/middleware.go). No verifier is built, no JWKS is fetched, no
#     sidecar and no model is touched on that path, so it is byte-identical run
#     to run -- which is why these assert the EXACT body (`GET And Expect` /
#     `POST And Expect`) rather than settling for the field-presence check
#     `POST And Expect Field` performs. There is no model output in a 401 to make
#     an exact comparison impossible.
#   * The AUTHENTICATED calls cannot be expressed: no keyword here takes headers,
#     and nothing here can mint a token dataplane Sentry signed. See UNCOVERED.
#   * A MALFORMED-token case is deliberately absent, because which rejection you
#     get depends on state this suite does not control. With a verifier built it
#     is 401 oauth.decode_error; with no discoverable issuer `BuildVerifier`
#     returns an error and the middleware answers 503 oauth.not_configured
#     first, never reaching the token at all. Asserting either would encode the
#     environment rather than the behaviour. identity_test.go pins the 401 with
#     the offline issuer, where the verifier is guaranteed to exist.
#
# The four outcomes above were measured on the quickstart's own offline build
# (`go run -tags offline .`, no Catalyst and no network off loopback) for the two
# below plus the decode_error; the 503 is read from the SDK's
# `oauthGate.serve`/`getVerifier` rather than observed, since the offline build
# always has coordinates.
#
# One property of the missing-token branch is a LIMITATION of this suite rather
# than a reassurance, and it is the one worth carrying forward: in
# `oauthGate.serve` the empty-token check runs BEFORE `getVerifier()`, so with no
# issuer discoverable at all -- no `identity` block in the sidecar's
# /v1.0/metadata, nothing federated on the project -- the unauthenticated request
# still answers exactly `401 oauth.missing_token`. Both assertions below
# therefore pass unchanged against a project on which inbound identity was never
# enabled, while every credential-bearing request to that same app would answer
# 503. This suite cannot tell those two projects apart. That is the sharpest edge
# of "proves the middleware refuses, not that identity works", and it is why the
# 403 and 200 live in a test that can present a credential:
# agents/langchaingo/enterprise-identity/identity_test.go, which mints one
# offline. That test cannot substitute for this suite either -- it exercises no
# Catalyst at all -- so the two are complements, and neither alone proves the
# live inbound path.
#
# The status is a TRANSCRIPTION here, as in the python sibling: the README prints
# `HTTP/1.1 401 Unauthorized` and the body beneath the first curl. Keep it that
# way -- if the README stops showing it, this becomes an assumption and this
# comment has to say so.
#
# `log_marker` deliberately absent on both, and for a stronger reason than next
# door: this app writes no access log, so a refused request leaves NOTHING in the
# dev-run output. There is no line to wait for, and doc-sync would in any case
# require one inside a fenced block in the README.
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
    # {"error": "oauth.missing_token"}`) -- and then measured, in the offline run
    # recorded above, on this exact route. Worth asserting separately rather than
    # trusting the prose: this is the route that would matter, and "RequireAuth is
    # app-wide, not per-path" is precisely the claim it checks.
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
        "`openid profile email offline_access`, so against an issuer that "
        "required a scope it would answer 403 oauth.missing_scope, which is not "
        "a documented failure but the documented outcome without a federated "
        "identity provider",
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
        "DIAGRID_QUICKSTART_IDENTITY=local APP_PORT=8006 go run -tags offline .",
        "README '## Run Offline Without a Catalyst Project'. It replaces Catalyst "
        "with a throwaway in-process issuer to make the 200, 403 and 401 reachable "
        "with no project at all, and it binds the same port 8006 as `dev run`. That "
        "makes it an alternative to this suite's entire flow rather than a step "
        "inside it: it exercises no Catalyst, and running it here would collide "
        "with the app this suite already has serving. The 200 and 403 paths this "
        "suite cannot reach are covered instead by "
        "agents/langchaingo/enterprise-identity/identity_test.go, which drives "
        "the same offline issuer through the app's real handlers and runs in "
        ".github/workflows/agents_enterprise_identity_go.yaml",
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

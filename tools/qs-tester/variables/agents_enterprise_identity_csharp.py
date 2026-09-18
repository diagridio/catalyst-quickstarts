"""Data for the agents/microsoft-dotnet/enterprise-identity end-to-end suite.

Every command here is transcribed verbatim from
agents/microsoft-dotnet/enterprise-identity/README.md, with one substitution: the
documented project name becomes `{project}`. The README is the source of truth.
Change the README, change this file, and `docsync/check_readme_sync.py --all`
will tell you if you changed only one.

WHY THE MODULE NAME CARRIES `_csharp` WHEN NO OTHER AGENT MODULE NAMES A
LANGUAGE. This quickstart is the C# port of agents/langgraph/enterprise-identity,
whose data module is `agents_enterprise_identity`. Two quickstarts of the same
name need two modules, and the python one was named first. The asymmetry is
therefore deliberate rather than a convention this file invented.

What this suite covers. The quickstart demonstrates inbound end-user identity:
Catalyst verifies the caller and passes a verified identity to the app in
`X-Diagrid-User-Token`. The suite asserts the plumbing -- build, documented
provisioning, the app serving -- plus the one HTTP outcome that is deterministic
without a credential: an unauthenticated request is refused 401 on both
documented routes.

Requests that carry a credential are out of scope here, because this harness
cannot mint one and the request keywords take no headers. Both documented
`diagrid call invoke` forms are listed in UNCOVERED with that reason.
"""

from pathlib import Path

# This module lives flat in variables/, like every other data module, so this is
# parents[3] regardless of how deep the quickstart itself sits.
REPO_ROOT = Path(__file__).resolve().parents[3]

FAMILY = "agents"
NAME = "enterprise-identity-csharp"
LANGUAGE = "csharp"

# README "## Run with Catalyst", step 2. Replaced by an ephemeral qs-ci-* name at
# run time; also what doc-sync maps onto `{project}` when comparing.
#
# Deliberately NOT the python sibling's `enterprise-identity-quickstart`: the two
# quickstarts are run side by side by anyone comparing them, and reusing one
# project name would have the second `project create` collide with the first.
DOCUMENTED_PROJECT = "enterprise-identity-dotnet-quickstart"

# Written from the real path on disk, and worth saying why that is worth saying:
# the python sibling's module has this wrong (`agents/enterprise-identity`, where
# the quickstart is at `agents/langgraph/enterprise-identity`), and every suite
# keyword takes its cwd from this value. Copying it would have installed and run
# in a directory that does not exist.
QUICKSTART_DIR = str(REPO_ROOT / "agents" / "microsoft-dotnet" / "enterprise-identity")

# appID and appPort from dev-enterprise-identity.yaml, which is also what the
# documented curls target and what the documented readiness line prints.
# Single-sourced because each value appears in three places below, and a run
# against a port one of them disagreed about fails in a way that looks like a
# broken quickstart rather than a broken data module.
APP_ID = "identity-agent"
APP_PORT = 8006
CRM_APP_ID = "crm-mcp"
CRM_APP_PORT = 8007

# `identity-agent` is created before the MCPServer on purpose: crm-mcp.yaml
# scopes the CRM to that App ID, and Catalyst rejects a scope naming an App ID
# that does not exist yet. The CRM's own App ID must NOT be created here --
# registering the MCP server creates it, and a hand-made one collides by name.

#
# The two `apply` commands register the CRM and its access policy. The policy is
# what carries `requireUser: true`, so without it the outbound leg would silently
# downgrade to no user identity at all.
SETUP = (
    "diagrid project create {project} --use --wait",
    "diagrid appid create identity-agent --wait",
    "diagrid apply -f resources/crm-mcp.yaml",
    "diagrid apply -f resources/crm-mcp-access.yaml",
)

# README "## Setup". The documented `cd agents/microsoft-dotnet/enterprise-identity`
# is expressed as the working directory instead of a command.
#
# Two builds joined by `&&`, and not a bare `dotnet build`: this quickstart has no
# solution file, because the repository's .gitignore excludes `*.sln` and no
# quickstart here ships one. A bare `dotnet build` in a directory holding two
# sibling projects and no project file of its own fails with "could not find a
# project", so the shape is the one every multi-project quickstart in this repo
# already uses -- compare `dotnet restore ./client && dotnet restore ./server` for
# invocation/csharp. `unit-tests` is absent on purpose: this suite does not run it,
# and `dotnet test unit-tests` builds it anyway.
INSTALL = "dotnet build ./agent && dotnet build ./crm-mcp"

# README "## Run with Catalyst", step 1, item 4. Bare of `--project` on purpose:
# the documented `project create` carries `--use`, and reproducing that
# dependency is deliberate, so a regression in `--use` breaks this suite instead
# of silently breaking readers.
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
# python sibling. Adding a plausible-looking delete would be inventing a
# documented command, and doc-sync would correctly reject it.
TEARDOWN = ()

# README "## Run with Catalyst", step 1, item 4: "Wait until the output shows
# `Now listening on: http://localhost:8006`".
#
# KESTREL'S LINE, AND NEITHER SIBLING'S. The python quickstart's marker is a
# uvicorn line, which does not apply. The agents/microsoft-dotnet marker is
# `Established gRPC bidirectional stream with Dapr sidecar`, which this app will
# NEVER print: it registers no Dapr client at all -- no DaprClient, no workflow
# runtime, no agent runner -- so nothing opens that stream. Kestrel's own line is
# the only honest marker here, and unlike the sibling's it is also a genuine
# serving gate rather than a connectivity one, which is why this module needs no
# separate SERVING_MARKER: the marker the README documents and the moment the
# port opens are the same event.
#
# ONE marker, and there is no second one to add. The app logs
# `[IDENTITY] verified caller subject=...` and `[IDENTITY] tool call for
# subject=...`, but both are on the AUTHENTICATED path -- the first inside
# `POST /agent/run` after the middleware has admitted the request, the second one
# step later. Neither can appear in a run this suite can produce. The middleware
# prints nothing at all when it is merely installed, so "the middleware is
# loaded" is not separately assertable: the 401 in REQUESTS is the evidence for
# that, and it is evidence produced by the shipped middleware.
READY_MARKERS = (f"Now listening on: http://localhost:{APP_PORT}",)

# EMPTY, and the reason is specific to this quickstart rather than to agent apps
# in general. `Wait Until Apps Healthy` polls for a 200. `RequireAuth` defaults
# to True -- the whole point of the demo -- and `OAuthMiddleware` sits ahead of
# EVERY route, so every path answers 401 oauth.missing_token until a verified
# credential arrives. `OAuthConfig` (Diagrid.AI.Identity 1.2.0) has exactly five
# properties -- Scopes/Issuer/Audience/JwksUri/RequireAuth, plus
# AllowInsecureJwks -- and no path exclusion, so no probe path can be exempted,
# which is also why the quickstart exposes no health route and why
# dev-enterprise-identity.yaml sets `enableAppHealthCheck: false`. There is
# nothing here that can answer 200, so there is nothing to probe: readiness rests
# on `Wait Until Apps Connected` plus the READY_MARKERS line above.
HEALTH_PROBES = ()

# (appID, port) pairs `diagrid dev run` reports as
# `Connected App ID "<id>" to http://localhost:<port>`. Read from
# dev-enterprise-identity.yaml, which has two apps.
#
# Required, not optional: `Start Quickstart` records these so `Stop Quickstart`
# can release each local app connection, and a run that skips that leaves a
# trust.diagrid.io endpoint pointing at a dead tunnel, which makes the next run's
# 500s ambiguous. That an agent app emits this line at all is observed on the
# other registered agent suites, but not yet for THESE two apps.
CONNECTED_APPS = ((APP_ID, APP_PORT), (CRM_APP_ID, CRM_APP_PORT))

# EMPTY, and unlike the other agent suites this is a decision rather than a gap.
# `Wait Until Catalyst Attached` guards the window in which a WORKFLOW call hangs
# unrecoverably (measured on agents/langgraph, 2026-08-27: a POST at readiness+0
# hung for the full 120s client timeout and twelve retries over 181s never
# recovered it). This quickstart starts no workflow -- it is a plain ASP.NET app
# with no Diagrid runner and no Dapr building block, and both requests below are
# refused by the middleware before any Dapr call is made. The window this gate
# exists for is not one this suite enters.
#
# Left empty rather than guessed for the ordinary reason too: the marker is
# whatever THIS app's logging makes visible for an inbound request from Catalyst,
# and nobody has watched this app's dev-run output yet. A marker that never
# appears makes the gate time out loudly; a marker matched from the wrong line
# lets the suite through early and silently. Fill it in from a real run, or leave
# it empty and say why.
CATALYST_PROBE_MARKERS = ()

# Empty. The quickstart ships a canned offline model (agent/CannedChatClient.cs)
# and reaches a real provider only when DIAGRID_QUICKSTART_MODEL=openai, which
# this suite does not set. Both requests below are refused before the agent runs
# anyway. Keep in step with the `secrets` entry in suites.py: one without the
# other is a declaration that lies.
SECRETS = ()

# The documented calls, in documented order. README "### 4. See It Fail Closed".
#
# TWO requests, and both are the negative case. That is not a thin suite by
# accident -- it is the only HTTP outcome assertable here, and it is asserted on
# both documented routes:
#
#   * With no `X-Diagrid-User-Token` header and RequireAuth=true, the middleware
#     returns 401 with body exactly {"error": "oauth.missing_token"}
#     (Diagrid.AI.Identity 1.2.0, `WriteErrorAsync` in OAuthMiddleware.cs). No
#     verifier is built, no JWKS is fetched, no sidecar and no model is touched on
#     that path, so it is byte-identical run to run -- which is why these assert
#     the EXACT body (`GET And Expect` / `POST And Expect`) rather than settling
#     for the field-presence check `POST And Expect Field` performs. There is no
#     model output in a 401 to make an exact comparison impossible.
#   * The AUTHENTICATED calls cannot be expressed: no keyword here takes headers,
#     and this harness cannot mint a credential. See UNCOVERED.
#   * A MALFORMED-token case is deliberately absent, because which rejection you
#     get depends on state this suite does not control. With a verifier built it
#     is 401 oauth.decode_error; with no discoverable issuer the verifier cannot
#     be built and the middleware answers 503 oauth.not_configured first, never
#     reaching the token at all. Asserting either would encode the environment
#     rather than the behaviour. unit-tests/IdentityTests.cs pins the 401 with the
#     offline issuer, where the verifier is guaranteed to exist.
#
# BOTH OUTCOMES BELOW WERE MEASURED, not reasoned, against Diagrid.AI.Identity
# 1.2.0 in this quickstart's own offline mode on 2026-09-17 -- the shipped
# middleware over the shipped two-route app, no Catalyst and no network:
#
#     GET  /whoami    no header  -> 401 {"error":"oauth.missing_token"}
#                                   Cache-Control: no-store
#     POST /agent/run no header  -> 401 {"error":"oauth.missing_token"}
#
# One property of that branch is a LIMITATION of this suite rather than a
# reassurance, and it is the one worth carrying forward: the missing-token check
# runs BEFORE the verifier is built, so with no issuer discoverable at all the
# unauthenticated request still answers exactly 401 oauth.missing_token. Both
# assertions below therefore pass unchanged against a project on which inbound
# identity was never enabled, while every credential-bearing request to that same
# app would answer 503. This suite cannot tell those two projects apart. That is
# the sharpest edge of "proves the middleware refuses, not that identity works",
# and it is why the 403 and 200 live in a test that can present a credential.
#
# The status is a TRANSCRIPTION here, like the python sibling's: the README prints
# `HTTP/1.1 401 Unauthorized` and the body beneath the first curl. Keep it that
# way -- if the README stops showing it, this becomes an assumption and this
# comment has to say so.
#
# `log_marker` deliberately absent on both. Kestrel's request log is off at the
# default `Microsoft.AspNetCore: Warning` level this quickstart's appsettings.json
# sets, so there is no per-request line to wait for; and even with it on, the
# assertion would add nothing the body comparison has not already made.
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
    # Worth asserting separately rather than trusting the prose: this is the route
    # that would matter, and "RequireAuth is app-wide, not per-path" is precisely
    # the claim it checks.
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
        "`openid profile email offline_access`, so against a project with a "
        "required scope it would answer 403 oauth.missing_scope, which is not a "
        "documented failure but the documented outcome without a federated "
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
        "DIAGRID_QUICKSTART_IDENTITY=local dotnet run --project agent "
        "--urls http://localhost:8006",
        "README '## Run Offline Without a Catalyst Project'. It replaces Catalyst "
        "with a throwaway in-process issuer to make the 200, 403 and 401 reachable "
        "with no project at all, and it binds the same port 8006 as `dev run`. That "
        "makes it an alternative to this suite's entire flow rather than a step "
        "inside it: it exercises no Catalyst, and running it here would collide "
        "with the app this suite already has serving. The 200, 403 and "
        "substitution paths this suite cannot reach are covered instead by "
        "agents/microsoft-dotnet/enterprise-identity/unit-tests, which drives the "
        "same offline issuer under Microsoft.AspNetCore.TestHost and runs in "
        ".github/workflows/agents_enterprise_identity_csharp.yaml",
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

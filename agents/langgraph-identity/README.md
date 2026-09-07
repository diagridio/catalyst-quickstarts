# LangGraph Quickstart - Inbound End-User Identity

This quickstart demonstrates how a vanilla LangGraph agent running on **Diagrid Catalyst** learns *who is calling it*. The caller presents a credential from an identity provider, Catalyst verifies it and exchanges it for a Catalyst-signed identity, and the agent is handed a verified user. The agent's tool then answers for that user and for nobody else.

Two lines of application code buy this, and they sit in the ASGI layer. Look at `main.py` and note what is absent: no graph node imports anything from Diagrid, and no node reads a header or a credential.

```python
app = FastAPI()
app.add_middleware(OAuthMiddleware, config=OAuthConfig(scopes={"agent.invoke"}))
```

## What This Quickstart Demonstrates

- **Verified inbound identity**: `OAuthMiddleware` verifies the `X-Diagrid-User-Token` header on every request and puts a `VerifiedUser` on `request.state.user`, carrying `subject`, `tenant`, `scopes`, `claims` and `issuer_id`
- **Nothing to configure**: `OAuthConfig` discovers the issuer, audience and JWKS URI from the sidecar's `/v1.0/metadata` endpoint, so the app hardcodes no identity coordinates and no provider URLs
- **Fail closed, before your code**: a missing credential is a `401` and an insufficient one is a `403`, decided in the middleware before the graph, the model, or any application code runs
- **A plain LangGraph graph**: a `StateGraph` with an `agent` node and a `tools` node, compiled and invoked directly. No Diagrid agent runner and no Dapr Workflow, so you can see exactly where identity enters and how little of the graph knows about it
- **The verified subject, not the model's guess**: the canned model asks for `someone@example.com`, who is nobody. The `tools` node substitutes the verified subject over it, so the answer names the real caller
- **Direct LLM integration**: runs on a deterministic canned model by default, so no API key is needed; a real provider is opt-in via `langchain-openai`

## Current Scope

This quickstart covers the **inbound** leg, and stops there: the end user's verified identity arriving at the agent, and the agent acting on it.

It does not cover propagating that identity onward to a downstream MCP tool. Nothing here registers an MCP server or an MCP access policy, and no request leaves the agent at all: the graph's one tool, `my_bookings` in `tools.py`, runs in-process and touches neither the network nor the Dapr sidecar. Everything you see below is Catalyst establishing *who the caller is* and the agent honoring that.

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/references/catalyst/catalyst-cli-intro/) installed
2. [Python 3.11-3.13](https://www.python.org/downloads/)
3. [uv](https://docs.astral.sh/uv/getting-started/installation/) installed

No LLM API key, and no identity provider of your own. The model is canned by default, and the last section runs the whole thing offline against a throwaway issuer.

## Setup

Navigate to the `langgraph-identity` directory and install the dependencies using `uv`:

```bash
cd agents/langgraph-identity
uv sync
```

### Using a real LLM provider

This quickstart runs offline by default. It uses a canned model, needs no API key, and returns the same tool call and the same answer on every run, whatever task you send. To use a real model instead, set `DIAGRID_QUICKSTART_MODEL` to `openai` and export your key. The example below uses OpenAI, but you can use any LLM provider supported by LangGraph.

**macOS/Linux (bash/zsh):**

```bash
export DIAGRID_QUICKSTART_MODEL="openai"
export OPENAI_API_KEY="your-key-here"
```

**Windows (PowerShell):**

```powershell
$env:DIAGRID_QUICKSTART_MODEL = "openai"
$env:OPENAI_API_KEY = "your-key-here"
```

The identity behavior is identical either way. A real model, like the canned one, does not know who is calling and is not consulted on the question.

## Run with Catalyst

### 1. Login and Run

1. Login to Catalyst using the Diagrid CLI:

```bash
diagrid login
```

2. Create a new Catalyst project for the quickstart and use it as the default project for the current session:

```bash
diagrid project create langgraph-identity-quickstart --use --wait
```

3. Run the agent with Catalyst:

```bash
uv run diagrid dev run -f dev-python-langgraph-identity.yaml --approve --skip-managed-kv --skip-managed-pubsub --skip-managed-workflow
```

The three `--skip-*` flags are worth understanding rather than copying. This agent calls no Dapr building block at all: no state, no pub/sub, no workflow. There is nothing for a managed KV store, a managed broker or a managed workflow store to serve, and without these flags `dev run` provisions all three the first time it creates the App ID. Identity needs none of them, because it is served by the sidecar itself.

Wait until the output shows `Uvicorn running on http://0.0.0.0:8006`.

### 2. Ask the Agent Who You Are

From another terminal.

`diagrid call invoke` sends your Diagrid login with the request as the `X-Diagrid-User-Token` header, so that the agent can act on your behalf. That header is the whole subject of this quickstart:

```bash
diagrid call invoke get identity-agent.whoami --id identity-agent --verbose
```

`--verbose` is what prints the response body. It also echoes the request that was sent, so treat that output as you would treat the credential itself.

`GET /whoami` runs no model turn and no tool, which makes it the cheapest place to see identity on its own. It returns the four fields `main.py` chooses to expose from the `VerifiedUser`:

```text
subject     the token's `sub` claim: who the caller is
tenant      the token's `tid` claim: which tenant they belong to
issuer_id   the `iss` value on the verified token
scopes      the scopes the verified credential carried
```

The full decoded credential is available to the handler as `user.claims`, and `main.py` deliberately does not return it. Claim *names* are safe to echo; claim *values* are a real person's identity data, and whatever the provider chose to put there would leak with them.

> **The app requires the `agent.invoke` scope.** `main.py` sets `REQUIRED_SCOPES = frozenset({"agent.invoke"})`, and the middleware answers `403 {"error": "oauth.missing_scope"}` for any verified credential that does not carry it. A Diagrid login carries the OIDC scopes `openid profile email offline_access` and nothing else, so a `403` at this step is not identity failing: the credential was verified, the caller was established, and only the authorization check turned the request away. For a `200` here, the caller's credential has to carry `agent.invoke`, which means federating an identity provider that issues it (`diagrid idp create`, whose `--claim-scopes` and `--required-scope` flags decide how scopes are read off the inbound token). To see all three responses with no identity provider at all, use [Run Offline Without a Catalyst Project](#run-offline-without-a-catalyst-project) below.

### 3. Run the Agent as Yourself

Same scope requirement as step 2: without a federated identity provider issuing `agent.invoke` this answers `403 {"error": "oauth.missing_scope"}` too, and the two log lines below appear only once a credential carrying that scope arrives. That is the documented outcome, not a failure — see the blockquote above. [Run Offline Without a Catalyst Project](#run-offline-without-a-catalyst-project) reaches the `200` with no identity provider at all.

```bash
diagrid call invoke post identity-agent.agent/run --id identity-agent --verbose -d '{"task": "What bookings do I have?"}'
```

The payoff is inside the agent's own answer, not in a header echoed back. The model asks the `my_bookings` tool for `someone@example.com`; `call_tools` in `main.py` replaces that argument with the subject the middleware verified, so the bookings that come back are yours. Substituting beats validating here, because there is no version of this where the model's opinion of who is calling matters.

The verified subject travels to the tool as ordinary graph config, never as a message the model could rewrite. You can watch both halves in the terminal running `diagrid dev run`:

```text
== APP - identity-agent == INFO:root:[IDENTITY] verified caller subject=... issuer=...
== APP - identity-agent == INFO:root:[IDENTITY] tool call for subject=...
```

The two lines are the point of the demo. The first is the middleware's verdict on your credential; the second is the tool being called for that same subject, one graph node later.

### 4. See It Fail Closed

`diagrid dev run` connects Catalyst to `localhost:8006`, so you can also reach the app directly. Doing so bypasses Catalyst, which means the request arrives with no credential attached at all:

```bash
curl -i http://localhost:8006/whoami
```

```text
HTTP/1.1 401 Unauthorized
cache-control: no-store
content-type: application/json

{"error":"oauth.missing_token"}
```

The `cache-control: no-store` is the middleware's, not FastAPI's: an authorization verdict is not a cacheable response.

Every route answers the same way. `require_auth` defaults to `True` and applies to the whole app, with no per-path exclusion:

```bash
curl -i -X POST http://localhost:8006/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "What bookings do I have?"}'
```

That app-wide rule is also why this quickstart exposes no health endpoint and why `dev-python-langgraph-identity.yaml` sets `enableAppHealthCheck: false`. An unauthenticated probe could only ever see the `401`, so a health check would report a perfectly healthy app as down.

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above either of the two requests that send no credential. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension. Its other two requests need a credential the app will accept, and these requests reach port 8006 directly — bypassing Catalyst — so a token from your own identity provider is refused `401 oauth.invalid_signature` here. Fill in `@token` from the offline section below, which is the only mode that mints a credential this app verifies.

To stop, press CTRL+C in the terminal running `diagrid dev run`.

## Run Offline Without a Catalyst Project

One response is hard to reach against real Catalyst: the `403`. It needs a credential that genuinely verifies but is missing a scope, and you cannot mint a scope-less token for yourself. With no issuer configured at all the middleware answers `503 {"error": "oauth.not_configured"}` instead, because there is nothing to verify against.

So the quickstart ships an opt-in throwaway issuer, `local_identity.py`. It is the same trade `fake_model.py` makes for the model: free, offline, and identical on every run. It changes no command in the section above and is never part of a real deployment.

### 1. Start the Local Issuer

Stop the `diagrid dev run` from the previous section first, since both bind port 8006.

```bash
DIAGRID_QUICKSTART_IDENTITY=local APP_PORT=8006 uv run python main.py
```

This generates a throwaway RSA key, serves the public half as JWKS on a loopback port the OS picks, and logs three ready-to-paste credentials:

```text
WARNING:root:LOCAL IDENTITY MODE - throwaway keys, never a real deployment
INFO:root:JWKS served at http://127.0.0.1:62751/jwks.json
INFO:root:200 (verified, has agent.invoke):
INFO:root:  eyJhbGciOiJSUzI1NiIsImtpZCI6ImxvY2FsLXF1aWNrc3RhcnQta2V5...
INFO:root:403 (verifies, wrong scope) oauth.missing_scope:
INFO:root:  eyJhbGciOiJSUzI1NiIsImtpZCI6ImxvY2FsLXF1aWNrc3RhcnQta2V5...
INFO:root:401 (expired 5 minutes ago) oauth.expired:
INFO:root:  eyJhbGciOiJSUzI1NiIsImtpZCI6ImxvY2FsLXF1aWNrc3RhcnQta2V5...
INFO:     Uvicorn running on http://0.0.0.0:8006 (Press CTRL+C to quit)
```

Read the warning literally. The private key lives in this process's memory, and the credentials it signs are printed in plain text. Nothing here has a counterpart in a deployed app.

### 2. A Verified Caller (200)

From another terminal, using the credential logged under `200`:

```bash
export TOKEN="<the credential logged under 200>"
curl -i -H "X-Diagrid-User-Token: Bearer $TOKEN" http://localhost:8006/whoami
```

```json
{
  "subject": "alice@example.com",
  "tenant": "local-tenant",
  "issuer_id": "https://local-identity.invalid",
  "scopes": ["agent.invoke"]
}
```

Now run the agent as that caller:

```bash
curl -i -X POST -H "X-Diagrid-User-Token: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task": "What bookings do I have?"}' \
  http://localhost:8006/agent/run
```

```json
{
  "user": {
    "subject": "alice@example.com",
    "tenant": "local-tenant",
    "issuer_id": "https://local-identity.invalid",
    "scopes": ["agent.invoke"]
  },
  "messages": [
    "What bookings do I have?",
    "Bookings for alice@example.com: Grand Ballroom on March 15th, 9AM-1PM; Rooftop Terrace on March 22nd, 6PM-11PM.",
    "You have two bookings: the Grand Ballroom on March 15th (9AM-1PM) and the Rooftop Terrace on March 22nd (6PM-11PM)."
  ]
}
```

Look at the second message. The tool was asked for `someone@example.com` and answered for `alice@example.com`, because `call_tools` overrode the model's argument with the verified subject. The identity is visible *inside the agent's own conversation*, which is the difference between propagating identity and echoing a header back.

### 3. A Credential Without the Scope (403)

The credential logged under `403` verifies perfectly. It is signed by the same issuer, it has not expired, and its subject is `bob@example.com`. It simply carries `reports.read` instead of `agent.invoke`:

```bash
export TOKEN="<the credential logged under 403>"
curl -i -H "X-Diagrid-User-Token: Bearer $TOKEN" http://localhost:8006/whoami
```

```text
HTTP/1.1 403 Forbidden

{"error":"oauth.missing_scope"}
```

`403`, not `401`, and the distinction is deliberate: authentication succeeded and authorization failed. The middleware knows exactly who `bob@example.com` is and is refusing him anyway.

### 4. An Expired Credential (401)

The credential logged under `401` is the `200` credential, five minutes stale:

```bash
export TOKEN="<the credential logged under 401>"
curl -i -H "X-Diagrid-User-Token: Bearer $TOKEN" http://localhost:8006/whoami
```

```text
HTTP/1.1 401 Unauthorized

{"error":"oauth.expired"}
```

Five minutes, not one. The verifier allows 120 seconds of clock skew, so a credential that expired a minute ago still returns `200`. Anything demonstrating expiry has to be older than the skew window.

## How It Works

The credential the app verifies is **not** the one the caller sent. Catalyst verifies the caller's upstream identity-provider token at the edge, exchanges it with dataplane Sentry, and passes a Catalyst-signed identity to the app in `X-Diagrid-User-Token`. Your application never sees the original token and never talks to your identity provider.

That is what makes the app's configuration so small. `OAuthConfig(scopes={"agent.invoke"})` names a policy and nothing else; the issuer, audience and JWKS URI are read from the sidecar's `/v1.0/metadata` at first use. Change identity providers and the app does not change.

The middleware then does four things in order, and stops at the first failure:

1. No `X-Diagrid-User-Token` header, or an empty one: `401 oauth.missing_token`
2. Signature or claims fail against the discovered JWKS: `401`, with a code naming the reason, such as `oauth.expired`
3. The verified scopes do not include every required scope: `403 oauth.missing_scope`
4. Otherwise it builds a `VerifiedUser` and puts it on `request.state.user`

Only after step 4 does any of this repository's code run. Both handlers in `main.py` read `request.state.user` and can treat it as trustworthy, because an untrustworthy request never reached them.

Inside the graph, identity is deliberately ordinary. `POST /agent/run` passes the verified subject as `config={"configurable": {"user_subject": user.subject}}`, and the `tools` node reads it from there. Nothing about the graph is Diagrid-specific, which is the point: the same graph runs unchanged off Catalyst, just without a verified caller to run it for.

## Files

| File | Purpose |
|------|---------|
| `main.py` | The FastAPI app, the two-line middleware install, the LangGraph graph, `GET /whoami` and `POST /agent/run` |
| `tools.py` | The single in-process tool, `my_bookings(subject)`. No network, no sidecar |
| `fake_model.py` | The deterministic canned model, so the quickstart needs no API key |
| `local_identity.py` | The opt-in throwaway issuer used by the offline section and by `test_identity.py`. Never part of a deployment — `.dockerignore` keeps it out of the image, so setting `DIAGRID_QUICKSTART_IDENTITY=local` on a container fails to start rather than disabling authentication |
| `dev-python-langgraph-identity.yaml` | The `diagrid dev run` file: App ID `identity-agent` on port 8006 |
| `test_identity.py` | The offline tests: `401`, `403`, `200`, and the verified subject reaching the tool. `uv run --with pytest pytest` |
| `test.http` | The same four requests, for the VS Code REST Client. Its credential-bearing pair needs the offline issuer |

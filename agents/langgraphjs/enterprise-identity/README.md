# LangGraph.js Quickstart - End-User Identity, End to End

This quickstart demonstrates a LangGraph.js agent running on **Diagrid Catalyst** that knows *who is calling it* and calls its tools as that person. The caller presents a credential from an identity provider; Catalyst verifies it, hands the agent a verified user, and mints a fresh token for each tool call so the tool can see the caller too. The agent handles no password, API key or token of its own.

Two lines of application code do both:

```ts
app.use(oauthMiddleware(config));          // who is calling
const identityFetch = createIdentityFetch(); // carry them onward
```

## What This Quickstart Demonstrates

- **Verified inbound identity**: `oauthMiddleware` verifies the `X-Diagrid-User-Token` header on every request, and `getVerifiedUser(req)` returns a `VerifiedUser` carrying `subject`, `tenant`, `scopes`, `claims` and `issuerId`
- **Nothing to configure**: an empty `OAuthConfig` discovers the issuer, audience and JWKS URI from Catalyst, so the app hardcodes no identity coordinates and no provider URLs
- **The caller reaches the tool too**: the agent's outbound call goes through Catalyst's MCP proxy over a `fetch` from `createIdentityFetch()`, and Catalyst mints a token naming both the user and the agent acting for them, so the CRM establishes who is asking rather than trusting the agent
- **Fail closed, before your code**: a missing credential is a `401` and an insufficient one is a `403`, decided in the middleware before the graph, the model, or any application code runs
- **A plain LangGraph.js graph**: a `StateGraph` with an `agent` node and a `tools` node, compiled and invoked directly
- **The verified subject, not the model's guess**: the canned model asks for `someone@example.com`, who is nobody. The `tools` node substitutes the verified subject over it, so the answer names the real caller
- **Direct LLM integration**: a deterministic canned model by default; a real provider is opt-in via `@langchain/openai`

## Current Scope

**Inbound** is the end user's verified identity arriving at the agent: Catalyst checks the caller's credential, exchanges it for a Catalyst-signed identity, and hands the agent a `VerifiedUser`.

**Outbound**, also called on-behalf-of, is the agent carrying that caller onward to a tool. When the agent calls the CRM through Catalyst's MCP proxy, Catalyst mints a *second* token, scoped to that one tool and naming two parties: the user it is for, and the agent acting for them. The CRM establishes who is asking for itself rather than taking the agent's word for it.

With inbound alone the CRM cannot tell Alice from Bob, so it cannot apply Alice's permissions. Outbound is what lets the downstream system enforce them.

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/references/catalyst/catalyst-cli-intro/) installed
2. [Node.js 22.13 or newer](https://nodejs.org/en/download)

No LLM API key or identity provider needed. The last section runs the whole thing offline against a throwaway issuer.

## Setup

Navigate to the `enterprise-identity` directory and install the dependencies:

```bash
cd agents/langgraphjs/enterprise-identity
npm install
```

### Using a real LLM provider

To use a real model, set `DIAGRID_QUICKSTART_MODEL` to `openai` and export your key. The example below uses OpenAI, but you can use any LLM provider supported by LangGraph.js.

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

Identity behaves the same either way: the model is never consulted on who is calling.

## Run with Catalyst

### 1. Login and Run

1. Login to Catalyst using the Diagrid CLI:

```bash
diagrid login
```

2. Create a new Catalyst project for the quickstart and use it as the default project for the current session:

```bash
diagrid project create enterprise-identity-js-quickstart --use --wait
```

3. Register the CRM and say who may use it:

```bash
diagrid appid create identity-agent --wait
diagrid apply -f resources/crm-mcp.yaml
diagrid apply -f resources/crm-mcp-access.yaml
```

`crm-mcp.yaml` scopes the CRM to `identity-agent`, so create that App ID first. It registers the CRM as an MCP server, so the agent reaches it through Catalyst rather than calling it directly. `crm-mcp-access.yaml` says who may call it:

```yaml
rules:
  - callers:
      - appID: identity-agent
    grants:
      - capability: tools
        names: ["*"]
auth:
  spiffeJWT:
    requireUser: true
```

`requireUser: true` is what turns on on-behalf-of. With it set, Catalyst mints a token carrying the calling user before forwarding to the CRM, and refuses the call outright when there is no user to act for. Leave it off and the CRM is reached by the agent alone, with no user attached.

4. Run the agent with Catalyst:

```bash
diagrid dev run -f dev-enterprise-identity.yaml --approve --skip-managed-kv --skip-managed-pubsub --skip-managed-workflow
```

This agent uses no state, pub/sub or workflow, so the three `--skip-*` flags skip provisioning managed resources it does not need.

Wait until the output shows `Listening on http://0.0.0.0:8006`.

### 2. Ask the Agent Who You Are

From another terminal.

`diagrid call invoke` sends your Diagrid login with the request as the `X-Diagrid-User-Token` header, so that the agent can act on your behalf. That header is the whole subject of this quickstart:

```bash
diagrid call invoke get identity-agent.whoami --id identity-agent --verbose
```

`--verbose` is what prints the response body. It also echoes the request that was sent, so treat that output as you would treat the credential itself.

`GET /whoami` runs no model turn and no tool, which makes it the cheapest place to see identity on its own. It returns the four fields `main.ts` chooses to expose from the `VerifiedUser`:

```text
subject     the token's `sub` claim: who the caller is
tenant      the token's `tid` claim: which tenant they belong to
issuerId    the `iss` value on the verified token
scopes      the scopes the verified credential carried
```

The full decoded credential is available to the handler as `user.claims`, and `main.ts` deliberately does not return it. Claim *names* are safe to echo; claim *values* are a real person's identity data, and whatever the provider chose to put there would leak with them.

> **On scopes.** The empty `OAuthConfig` here requires a *verified* caller and nothing more. You can also demand a scope -- `{ scopes: ['reports.read'] }` answers `403 {"error": "oauth.missing_scope"}` for any verified caller without it. Scopes come from your identity provider, and a Diagrid login carries `openid profile email offline_access`, so this walkthrough requires none. [Run Offline Without a Catalyst Project](#run-offline-without-a-catalyst-project) demonstrates the 403 against an issuer that does mint the scope.

### 3. Run the Agent as Yourself

This is the call that exercises both legs: your identity reaches the agent, and the agent carries it onward to the CRM.

```bash
diagrid call invoke post identity-agent.agent/run --id identity-agent --verbose -d '{"task": "How is ACME doing?"}'
```

The payoff is inside the CRM's answer, not in a header echoed back:

```text
Account ACME-1: 3 open opportunities, $120k pipeline.
Served to user=...oidc-user/auth0-...  via agent=...ns/prj-.../identity-agent
```

Two identities in one call. `user` is you; `agent` is the thing that asked on your behalf. `accountSummary` in `tools.ts` takes no subject argument -- the CRM reads both identities off the token Catalyst minted for this call.

You can watch both hops in the terminal running `diagrid dev run`:

```text
== APP - identity-agent == [IDENTITY] verified caller subject=... issuer=...
== APP - crm-mcp        == account_summary(ACME-1) for user=... via agent=...
```

### 4. See It Fail Closed

`diagrid dev run` connects Catalyst to `localhost:8006`, so you can also reach the app directly. Doing so bypasses Catalyst, which means the request arrives with no credential attached at all:

```bash
curl -i http://localhost:8006/whoami
```

```text
HTTP/1.1 401 Unauthorized
Cache-Control: no-store
Content-Type: application/json; charset=utf-8

{"error":"oauth.missing_token"}
```

`Cache-Control: no-store` -- an authorization verdict is not cacheable.

Every route answers the same way. `requireAuth` defaults to `true` and applies to the whole app, with no per-path exclusion:

```bash
curl -i -X POST http://localhost:8006/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "What bookings do I have?"}'
```

That app-wide rule is also why this quickstart exposes no health endpoint and why `dev-enterprise-identity.yaml` sets `enableAppHealthCheck: false`.

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above either of the two requests that send no credential. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension. Its other two requests need a credential the app will accept, and these requests reach port 8006 directly — bypassing Catalyst — so a token from your own identity provider is refused `401 oauth.invalid_signature` here. Fill in `@token` with the credential the offline section below logs under `200`.

To stop, press CTRL+C in the terminal running `diagrid dev run`.

## Run Offline Without a Catalyst Project

This mode is opt-in, and it is good for two things:

1. **Trying the quickstart with no Catalyst project at all** -- no login, no project, no identity provider.
2. **Seeing the `403`.** That needs a credential that verifies but lacks a required scope. Scopes come from your identity provider, and here the issuer is yours, so it can mint a credential deliberately missing one.

`local_identity.ts` generates a throwaway key at startup, serves the public half on a loopback port, and signs three credentials: valid, wrong-scope, and expired.

This mode shows the **inbound** half only: with no Catalyst project there is no MCP server to reach, so the graph calls the in-process tool and the on-behalf-of leg does not appear. It is never part of a deployment -- `.dockerignore` keeps `local_identity.ts` out of the image, so setting `DIAGRID_QUICKSTART_IDENTITY=local` on a container fails to start rather than disabling authentication.

### 1. Start the Local Issuer

Stop the `diagrid dev run` from the previous section first, since both bind port 8006.

```bash
DIAGRID_QUICKSTART_IDENTITY=local APP_PORT=8006 npm start
```

This generates a throwaway RSA key, serves the public half as JWKS on a loopback port the OS picks, and logs three ready-to-paste credentials:

```text
Using the canned offline model: no API key needed and the answer is always the same. Set DIAGRID_QUICKSTART_MODEL=openai for a real provider.
LOCAL IDENTITY MODE - throwaway keys, never a real deployment
JWKS served at http://127.0.0.1:56746/jwks.json
200 (verified, has agent.invoke):
  eyJhbGciOiJSUzI1NiIsImtpZCI6ImxvY2FsLXF1aWNrc3RhcnQta2V5...
403 (verifies, wrong scope) oauth.missing_scope:
  eyJhbGciOiJSUzI1NiIsImtpZCI6ImxvY2FsLXF1aWNrc3RhcnQta2V5...
401 (expired 5 minutes ago) oauth.expired:
  eyJhbGciOiJSUzI1NiIsImtpZCI6ImxvY2FsLXF1aWNrc3RhcnQta2V5...
Listening on http://0.0.0.0:8006
```

The private key lives in this process's memory and the credentials are printed in plain text. Never do this in a deployment.

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
  "issuerId": "https://local-identity.invalid",
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
    "issuerId": "https://local-identity.invalid",
    "scopes": ["agent.invoke"]
  },
  "messages": [
    "What bookings do I have?",
    "Bookings for alice@example.com: Grand Ballroom on March 15th, 9AM-1PM; Rooftop Terrace on March 22nd, 6PM-11PM.",
    "You have two bookings: the Grand Ballroom on March 15th (9AM-1PM) and the Rooftop Terrace on March 22nd (6PM-11PM)."
  ]
}
```

Look at the second message. The tool was asked for `someone@example.com` and answered for `alice@example.com`, because `callTools` overrode the model's argument with the verified subject.

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

The credential the app verifies is **not** the one the caller sent. Catalyst verifies the caller's token and passes a Catalyst-signed identity to the app in `X-Diagrid-User-Token`. Your application never sees the original token and never talks to your identity provider.

That is what makes the app's configuration so small. The `OAuthConfig` here names a policy and nothing else -- "a verified caller is required". The issuer, audience and JWKS URI are read from Catalyst at first use, so changing identity providers changes nothing in the app.

The middleware then does five things in order, and stops at the first failure:

1. No `X-Diagrid-User-Token` header, or an empty one: `401 oauth.missing_token`
2. The credential is not a well-formed JWT: `401 oauth.decode_error`
3. Signature or claims fail against the discovered JWKS: `401`, with a code naming the reason, such as `oauth.expired`
4. The verified scopes do not include every required scope: `403 oauth.missing_scope`
5. Otherwise it builds a `VerifiedUser` and attaches it to the request

Only after step 5 does any of this repository's code run. Both handlers in `main.ts` read `getVerifiedUser(req)` and can treat the result as trustworthy, because an untrustworthy request never reached them.

Inside the graph, identity is deliberately ordinary. `POST /agent/run` passes the verified subject as `{ configurable: { user_subject: user.subject } }`, and the `tools` node reads it from there. Nothing in the graph is Diagrid-specific.

## Files

| File | Purpose |
|------|---------|
| `main.ts` | The express app, the middleware install, the LangGraph.js graph, `GET /whoami` and `POST /agent/run` |
| `tools.ts` | Both tools: `myBookings(subject)` runs in-process, `accountSummary(account_id)` goes out through Catalyst's MCP proxy on the `createIdentityFetch()` client and carries the caller with it |
| `crm_server.ts` | The stand-in CRM behind MCP. Its one tool reports the user and the agent it was called for |
| `resources/` | The `MCPServer` registration and the access policy whose `requireUser: true` turns on on-behalf-of |
| `model.ts` | The deterministic canned model, so the quickstart needs no API key |
| `local_identity.ts` | The opt-in throwaway issuer used by the offline section and the tests. Never part of a deployment |
| `dev-enterprise-identity.yaml` | The `diagrid dev run` file: `identity-agent` on port 8006, `crm-mcp` on 8007 |
| `identity.test.ts` | The offline tests: `401`, `403`, `200`, and the verified subject reaching the tool. `npm test` |
| `test.http` | The same four requests, for the VS Code REST Client. Its credential-bearing pair needs the offline issuer |

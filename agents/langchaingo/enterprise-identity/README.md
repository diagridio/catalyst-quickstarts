# langchaingo Quickstart - End-User Identity, End to End

This quickstart demonstrates a [langchaingo](https://github.com/tmc/langchaingo) agent running on **Diagrid Catalyst** that knows *who is calling it* and calls its tools as that person. The caller presents a credential from an identity provider; Catalyst verifies it, hands the agent a verified user, and mints a fresh token for each tool call so the tool can see the caller too. The agent handles no password, API key or token of its own.

Two lines of application code buy both halves. Look at `main.go` and `tools.go` and note what is absent: `agent.go` imports nothing from Diagrid, and no tool reads a header or a credential.

```go
handler := identity.Middleware(identity.OAuthConfig{})(mux)  // who is calling
client := identity.NewHTTPClient(nil)                        // carry them onward
```

## What This Quickstart Demonstrates

- **Verified inbound identity**: `identity.Middleware` verifies the `X-Diagrid-User-Token` header on every request and puts a `*identity.VerifiedUser` in the request context, carrying `Subject`, `Tenant`, `Scopes`, `Claims` and `IssuerID`
- **Nothing to configure**: the zero `identity.OAuthConfig` discovers the issuer, audience and JWKS URI from Catalyst, so the app hardcodes no identity coordinates and no provider URLs
- **The caller reaches the tool too**: the agent's outbound call goes through Catalyst's MCP proxy over `identity.NewHTTPClient`, which mints a token naming both the user and the agent acting for them, so the CRM establishes who is asking rather than trusting the agent
- **Fail closed, before your code**: a missing credential is a `401` and an insufficient one is a `403`, decided in the middleware before the agent, the model, or any application code runs
- **A plain agent loop**: call the model, run the tools it asks for, feed the results back, answer. No Diagrid agent runner and no Dapr Workflow, so you can see exactly where identity enters and how little of the agent knows about it
- **The verified subject, not the model's guess**: the canned model asks for `someone@example.com`, who is nobody. `callTool` substitutes the verified subject over it, so the answer names the real caller
- **Direct LLM integration**: runs on a deterministic canned model by default, so no API key is needed; a real provider is opt-in via `langchaingo/llms/openai`

## Current Scope

**Inbound** is the end user's verified identity arriving at the agent: Catalyst checks the caller's credential, exchanges it for a Catalyst-signed identity, and hands the agent a `VerifiedUser`.

**Outbound**, also called on-behalf-of, is the agent carrying that caller onward to a tool. When the agent calls the CRM through Catalyst's MCP proxy, Catalyst mints a *second* token, scoped to that one tool and naming two parties: the user it is for, and the agent acting for them. The CRM establishes who is asking for itself rather than taking the agent's word for it.

The difference matters. With inbound alone, the agent knows you are Alice and then calls every tool as one shared service account -- the CRM cannot tell Alice from Bob, so it cannot apply Alice's permissions. Outbound is what lets the downstream system enforce them.

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/references/catalyst/catalyst-cli-intro/) installed
2. [Go 1.26.4 or newer](https://go.dev/dl/)

No LLM API key, and no identity provider of your own. The model is canned by default, and the last section runs the whole thing offline against a throwaway issuer.

## Setup

Navigate to the `enterprise-identity` directory and build both binaries:

```bash
cd agents/langchaingo/enterprise-identity
go build ./...
```

Building now warms the build cache so the app starts quickly below.

### Using a real LLM provider

The canned model returns the same tool call and answer on every run. To use a real model, set `DIAGRID_QUICKSTART_MODEL` to `openai` and export your key. The example below uses OpenAI, but you can use any LLM provider langchaingo supports.

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
diagrid project create enterprise-identity-quickstart --use --wait
```

3. Register the CRM and say who may use it:

```bash
diagrid appid create identity-agent --wait
diagrid apply -f resources/crm-mcp.yaml
diagrid apply -f resources/crm-mcp-access.yaml
```

`crm-mcp.yaml` scopes the CRM to `identity-agent`, so that App ID is created first; registering the MCP server creates the CRM's own App ID.

The first registers the CRM as an MCP server. The second grants access:

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

This agent uses no state, pub/sub or workflow, so the `--skip-*` flags avoid provisioning managed resources it will never use.

Wait until the output shows `listening on http://0.0.0.0:8006`:

```text
== APP - identity-agent == 2026/09/17 18:14:56 Using the canned offline model: no API key needed and the answer is always the same. Set DIAGRID_QUICKSTART_MODEL=openai for a real provider.
== APP - identity-agent == 2026/09/17 18:14:56 listening on http://0.0.0.0:8006
```

### 2. Ask the Agent Who You Are

From another terminal.

`diagrid call invoke` sends your Diagrid login with the request as the `X-Diagrid-User-Token` header, so that the agent can act on your behalf. That header is the whole subject of this quickstart:

```bash
diagrid call invoke get identity-agent.whoami --id identity-agent --verbose
```

`--verbose` is what prints the response body. It also echoes the request that was sent, so treat that output as you would treat the credential itself.

`GET /whoami` runs no model turn and no tool, which makes it the cheapest place to see identity on its own. It returns the four fields `main.go` chooses to expose from the `VerifiedUser`:

```text
subject     the token's `sub` claim: who the caller is
tenant      the token's `tid` claim: which tenant they belong to
issuer_id   the `iss` value on the verified token
scopes      the scopes the verified credential carried
```

The full decoded credential is available to the handler as `user.Claims`, and `main.go` deliberately does not return it. Claim *names* are safe to echo; claim *values* are a real person's identity data, and whatever the provider chose to put there would leak with them.

> **On scopes.** The zero `OAuthConfig` here requires a *verified* caller and nothing more. You can also demand a scope: `identity.OAuthConfig{Scopes: []string{"reports.read"}}` answers `403 {"error": "oauth.missing_scope"}` for any verified caller without it. Scopes come from your identity provider. A Diagrid login carries `openid profile email offline_access`, so the walkthrough requires none; [Run Offline Without a Catalyst Project](#run-offline-without-a-catalyst-project) shows the 403 against an issuer that mints a scope.

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

Two identities in one call. `user` is you; `agent` is the thing that asked on your behalf. The CRM was never told who you are -- it read both off the token Catalyst minted for that single call, which is why it could also apply your permissions if it had any.

Note what `accountSummary` in `tools.go` does *not* take: a subject argument. It cannot be told who is calling, so it cannot be lied to.

`identity.NewHTTPClient` reads the caller's token off the **request context** at send time, so build the MCP session per request from the inbound `r.Context()`. A request built from `context.Background()`, or a session connected once at startup, sends no user and the CRM reports `<no user identity>`.

You can watch both hops in the terminal running `diagrid dev run`:

```text
== APP - identity-agent == 2026/09/17 18:15:10 [IDENTITY] verified caller subject=... issuer=...
== APP - crm-mcp        == 2026/09/17 18:15:10 account_summary(ACME-1) for user=... via agent=...
```

The first line is Catalyst's verdict on your credential. The second is the CRM, one network hop later, independently establishing the same person.

### 4. See It Fail Closed

`diagrid dev run` connects Catalyst to `localhost:8006`, so you can also reach the app directly. Doing so bypasses Catalyst, which means the request arrives with no credential attached at all:

```bash
curl -i http://localhost:8006/whoami
```

```text
HTTP/1.1 401 Unauthorized
Cache-Control: no-store
Content-Type: application/json

{"error":"oauth.missing_token"}
```

`Cache-Control: no-store`: an authorization verdict is never cached.

Every route answers the same way. `RequireAuth` resolves to true on the zero `OAuthConfig` and applies to the whole app, with no per-path exclusion:

```bash
curl -i -X POST http://localhost:8006/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "What bookings do I have?"}'
```

Because authentication is app-wide, this quickstart exposes no health route and `dev-enterprise-identity.yaml` sets `enableAppHealthCheck: false`.

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above either of the two requests that send no credential. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension. The two credential-bearing requests need a token the app verifies; fill in `@token` from the offline section below. A token from your own provider is refused `401 oauth.invalid_signature`, because these requests bypass Catalyst.

To stop, press CTRL+C in the terminal running `diagrid dev run`.

## Run Offline Without a Catalyst Project

**What this is for.** Two things, and it is opt-in for both:

1. **Try the quickstart with no Catalyst project at all** -- no login, no project, no identity provider.
2. **See the `403`**, which needs a credential that verifies but lacks a required scope. Here the issuer is yours, so it can mint one deliberately missing a scope.

`local_identity.go` generates a throwaway key at startup, serves the public half on a loopback port, and signs three credentials: valid, wrong-scope, and expired.

Two limits worth knowing. It shows the **inbound** half only: with no Catalyst project there is no MCP server to reach, so the agent calls the in-process tool and the on-behalf-of leg does not appear. And it is never part of a deployment -- the offline issuer is behind the `offline` build tag, the `Dockerfile` builds without it, so setting the variable on a container fails to start rather than quietly turning authentication off.

### 1. Start the Local Issuer

Stop the `diagrid dev run` from the previous section first, since both bind port 8006.

```bash
DIAGRID_QUICKSTART_IDENTITY=local APP_PORT=8006 go run -tags offline .
```

This generates a throwaway RSA key, serves the public half as JWKS on a loopback port the OS picks, and logs three ready-to-paste credentials:

```text
2026/09/17 18:14:56 LOCAL IDENTITY MODE - throwaway keys, never a real deployment
2026/09/17 18:14:56 JWKS served at http://127.0.0.1:56421/jwks.json
2026/09/17 18:14:56 200 (verified, has agent.invoke):
2026/09/17 18:14:56   eyJhbGciOiJSUzI1NiIsImtpZCI6ImxvY2FsLXF1aWNrc3RhcnQta2V5...
2026/09/17 18:14:56 403 (verifies, wrong scope) oauth.missing_scope:
2026/09/17 18:14:56   eyJhbGciOiJSUzI1NiIsImtpZCI6ImxvY2FsLXF1aWNrc3RhcnQta2V5...
2026/09/17 18:14:56 401 (expired 5 minutes ago) oauth.expired:
2026/09/17 18:14:56   eyJhbGciOiJSUzI1NiIsImtpZCI6ImxvY2FsLXF1aWNrc3RhcnQta2V5...
2026/09/17 18:14:56 Using the canned offline model: no API key needed and the answer is always the same. Set DIAGRID_QUICKSTART_MODEL=openai for a real provider.
2026/09/17 18:14:56 listening on http://0.0.0.0:8006
```

The private key lives in this process's memory and the credentials it signs are printed in plain text. Never deploy this mode.

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

Look at the second message. The tool was asked for `someone@example.com` and answered for `alice@example.com`, because `callTool` overrode the model's argument with the verified subject.

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

`403`, not `401`: authentication succeeded and authorization failed. The middleware knows who `bob@example.com` is and refuses him anyway.

### 4. An Expired Credential (401)

The credential logged under `401` is the `200` credential, expired:

```bash
export TOKEN="<the credential logged under 401>"
curl -i -H "X-Diagrid-User-Token: Bearer $TOKEN" http://localhost:8006/whoami
```

```text
HTTP/1.1 401 Unauthorized

{"error":"oauth.expired"}
```

The verifier allows 120 seconds of clock skew, so this credential is five minutes stale rather than one.

## How It Works

The credential the app verifies is **not** the one the caller sent. Catalyst verifies the caller's token and passes a Catalyst-signed identity to the app in `X-Diagrid-User-Token`. Your application never sees the original token and never talks to your identity provider.

That is what makes the app's configuration so small. The zero `identity.OAuthConfig` names a policy and nothing else -- here, "a verified caller is required". The issuer, audience and JWKS URI are read from Catalyst at first use, so changing identity providers changes nothing in the app.

The middleware then does five things in order, and stops at the first failure:

1. No `X-Diagrid-User-Token` header, or an empty one: `401 oauth.missing_token`
2. The credential is not a well-formed JWT: `401 oauth.decode_error`
3. Signature or claims fail against the discovered JWKS: `401`, with a code naming the reason, such as `oauth.expired`
4. The verified scopes do not include every required scope: `403 oauth.missing_scope`
5. Otherwise it builds a `VerifiedUser` and puts it in the request context

Only after step 5 does any of this repository's code run. Both handlers in `main.go` read the caller with `identity.UserFromContext(r.Context())` and can treat it as trustworthy, because an untrustworthy request never reached them.

Inside the agent, identity is deliberately ordinary. `POST /agent/run` passes the verified subject to `agent.run` as an argument, and `callTool` substitutes it over whatever subject the model asked for. Nothing about the loop is Diagrid-specific.

`identity.NewHTTPClient` returns a plain `*http.Client` that reads the caller's token off each request's context when the request is sent. That is what makes one shared client safe under concurrency, and what makes the inbound `r.Context()` load-bearing all the way to the MCP call.

## Files

| File | Purpose |
|------|---------|
| `main.go` | The `net/http` app, the two-line middleware install, `GET /whoami` and `POST /agent/run` |
| `agent.go` | The agent loop: model, tools, model. This is where the verified subject is substituted over the model's guess |
| `tools.go` | Both tools: `myBookings(subject)` runs in-process, `accountSummary(account_id)` goes out through Catalyst's MCP proxy and carries the caller with it |
| `crm/main.go` | The stand-in CRM behind MCP. Its one tool reports the user and the agent it was called for |
| `resources/` | The `MCPServer` registration and the access policy whose `requireUser: true` turns on on-behalf-of |
| `fake_model.go` | The deterministic canned model, so the quickstart needs no API key |
| `local_identity.go` | The opt-in throwaway issuer, behind the `offline` build tag. Never part of a deployment |
| `local_identity_disabled.go` | The `!offline` half of that guard: the stub that refuses to start |
| `dev-enterprise-identity.yaml` | The `diagrid dev run` file: `identity-agent` on port 8006, `crm-mcp` on 8007 |
| `identity_test.go` | The offline tests covering `401`, `403` and `200`. Needs the `offline` tag: `go test -tags offline ./...` |
| `tools_test.go` | Asserts the verified subject is substituted into the right tool |
| `crm/crm_test.go` | The CRM's half: both identities read off the user token, and what it reports when the call carries none |
| `test.http` | The same four requests, for the VS Code REST Client. Its credential-bearing pair needs the offline issuer |

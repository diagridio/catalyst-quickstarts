# Microsoft Agent Framework Quickstart - End-User Identity, End to End

This quickstart demonstrates a [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/) agent running on **Diagrid Catalyst** that knows *who is calling it* and calls its tools as that person. The caller presents a credential from an identity provider; Catalyst verifies it, hands the agent a verified user, and mints a fresh token for each tool call so the tool can see the caller too. The agent handles no password, API key or token of its own.

Three lines of application code cover both halves. No tool reads a header or a credential.

```csharp
builder.Services.AddDiagridIdentity();            // who is calling
builder.Services.AddDiagridIdentityHttpClient();  // carry them onward
app.UseDiagridIdentity();                         // enforced ahead of every route
```

## What This Quickstart Demonstrates

- **Verified inbound identity**: `OAuthMiddleware` verifies the `X-Diagrid-User-Token` header on every request and attaches a `VerifiedUser`, read with `context.GetVerifiedUser()`, carrying `Subject`, `Tenant`, `Scopes`, `Claims` and `IssuerId`
- **Nothing to configure**: `AddDiagridIdentity()` discovers the issuer, audience and JWKS URI from Catalyst, so the app hardcodes no identity coordinates and no provider URLs
- **The caller reaches the tool too**: the agent's outbound call goes through Catalyst's MCP proxy on an identity-aware `HttpClient`, and Catalyst mints a token naming both the user and the agent acting for them, so the CRM establishes who is asking rather than trusting the agent
- **Fail closed, before your code**: a missing credential is a `401` and an insufficient one is a `403`, decided in the middleware before the agent, the model, or any application code runs
- **A plain `ChatClientAgent`**: built from `AsAIAgent` and invoked with `RunAsync` straight from the request handler, so you can see exactly where identity enters and how little of the agent knows about it
- **The verified subject, not the model's guess**: the canned model asks for `someone@example.com`, who is nobody. The tool the run is handed is built around the verified subject and substitutes it over that argument, so the answer names the real caller
- **Direct LLM integration**: runs on a deterministic canned model by default, so no API key is needed; a real provider is opt-in via `Microsoft.Extensions.AI.OpenAI`

## Current Scope

This quickstart covers both legs of the journey: **inbound**, the end user's verified identity arriving at the agent, and **outbound** — also called on-behalf-of — the agent carrying that caller onward to a tool.

With inbound alone, the agent knows you are Alice and then calls every tool as one shared service account: the CRM cannot tell Alice from Bob, so it cannot apply Alice's permissions. Outbound is what lets the downstream system enforce them.

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/references/catalyst/catalyst-cli-intro/) installed
2. [.NET 10 SDK](https://dotnet.microsoft.com/download) installed

No LLM API key, and no identity provider of your own. The model is canned by default, and the last section runs the whole thing offline against a throwaway issuer.

## Setup

Navigate to the `enterprise-identity` directory and build both apps:

```bash
cd agents/microsoft-dotnet/enterprise-identity
dotnet build ./agent && dotnet build ./crm-mcp
```

`agent/` is the agent and `crm-mcp/` is the stand-in CRM it calls. A third project, `unit-tests/`, covers the offline identity paths.

### Using a real LLM provider

This quickstart runs offline by default. It uses a canned model, needs no API key, and returns the same tool call and the same answer on every run, whatever task you send. To use a real model instead, set `DIAGRID_QUICKSTART_MODEL` to `openai` and export your key. The example below uses OpenAI, but you can use any provider with an `IChatClient` implementation.

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

The identity behavior is identical either way. A real model, like the canned one, is not consulted on who is calling.

## Run with Catalyst

### 1. Login and Run

1. Login to Catalyst using the Diagrid CLI:

```bash
diagrid login
```

2. Create a new Catalyst project for the quickstart and use it as the default project for the current session:

```bash
diagrid project create enterprise-identity-dotnet-quickstart --use --wait
```

3. Register the CRM and say who may use it:

```bash
diagrid appid create identity-agent --wait
diagrid apply -f resources/crm-mcp.yaml
diagrid apply -f resources/crm-mcp-access.yaml
```

`crm-mcp.yaml` scopes the CRM to `identity-agent`, so that App ID is created first. The second command registers the CRM as an MCP server so the agent reaches it through Catalyst. The third grants access:

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

4. Run both apps with Catalyst:

```bash
diagrid dev run -f dev-enterprise-identity.yaml --approve --skip-managed-kv --skip-managed-pubsub --skip-managed-workflow
```

This agent uses no state, pub/sub or workflow, so the `--skip-*` flags keep `dev run` from provisioning managed components it will not use.

Wait until the output shows `Now listening on: http://localhost:8006`.

### 2. Ask the Agent Who You Are

From another terminal.

`diagrid call invoke` sends your Diagrid login with the request as the `X-Diagrid-User-Token` header, so that the agent can act on your behalf:

```bash
diagrid call invoke get identity-agent.whoami --id identity-agent --verbose
```

`--verbose` is what prints the response body. It also echoes the request that was sent, so treat that output as you would treat the credential itself.

`GET /whoami` runs no model turn and no tool, which makes it the cheapest place to see identity on its own. It returns the four fields `agent/IdentityEndpoints.cs` chooses to expose from the `VerifiedUser`:

```text
subject     the token's `sub` claim: who the caller is
tenant      the token's `tid` claim: which tenant they belong to
issuer_id   the `iss` value on the verified token
scopes      the scopes the verified credential carried
```

The full decoded credential is available to the handler as `user.Claims`, and `IdentityEndpoints` deliberately does not return it. Claim *names* are safe to echo; claim *values* are a real person's identity data.

> **On scopes.** `AddDiagridIdentity()` here requires a *verified* caller and nothing more. You can also demand a scope -- `AddDiagridIdentity(config => config.Scopes = ["reports.read"])` answers `403 {"error": "oauth.missing_scope"}` for any verified caller without it. This walkthrough requires no scope, because a Diagrid login carries only `openid profile email offline_access`. Require the scopes your own identity provider issues. [Run Offline Without a Catalyst Project](#run-offline-without-a-catalyst-project) demonstrates the 403 against an issuer that does mint one.

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

Two identities in one call. `user` is you; `agent` is the thing that asked on your behalf. The CRM was never told who you are -- it read both off the token Catalyst minted for that call, so it can apply your permissions.

Note what `account_summary` in `agent/Tools.cs` does *not* take: a subject argument. It cannot be told who is calling, so it cannot be lied to. That is the difference between this and `my_bookings`, whose caller is a string the agent fills in.

You can watch both hops in the terminal running `diagrid dev run`:

```text
== APP - identity-agent == info: EnterpriseIdentity.IdentityEndpoints[0]
== APP - identity-agent ==       [IDENTITY] verified caller subject=... issuer=...
== APP - crm-mcp        == info: CrmTools[0]
== APP - crm-mcp        ==       account_summary(ACME-1) for user=... via agent=...
```

The first line is Catalyst's verdict on your credential. The second is the CRM, one network hop later, independently establishing the same person.

### 4. See It Fail Closed

`diagrid dev run` connects Catalyst to `localhost:8006`, so you can also reach the app directly. Doing so bypasses Catalyst, which means the request arrives with no credential attached at all:

```bash
curl -i http://localhost:8006/whoami
```

```text
HTTP/1.1 401 Unauthorized
Content-Type: application/json
Cache-Control: no-store

{"error":"oauth.missing_token"}
```

`Cache-Control: no-store`, because an authorization verdict is not a cacheable response.

Every route answers the same way. `RequireAuth` defaults to `true` and applies to the whole app, with no per-path exclusion:

```bash
curl -i -X POST http://localhost:8006/agent/run -H "Content-Type: application/json" -d '{"task": "What bookings do I have?"}'
```

That app-wide rule is also why this quickstart exposes no health endpoint and why `dev-enterprise-identity.yaml` sets `enableAppHealthCheck: false`. An unauthenticated probe could only ever see the `401`, so a health check would report a perfectly healthy app as down.

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above either of the two requests that send no credential. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension. Its other two requests need a credential the app verifies — fill in `@token` with the credential the offline issuer logs under `200`.

To stop, press CTRL+C in the terminal running `diagrid dev run`.

## Run Offline Without a Catalyst Project

**What this is for.** Two things, and it is opt-in for both:

1. **Try the quickstart with no Catalyst project at all** -- no login, no project, no identity provider.
2. **See the `403`.** A `403` needs a credential that verifies but lacks a required scope. Here the issuer is yours, so it can mint one deliberately missing a scope.

`agent/LocalIdentity.cs` generates a throwaway RSA key at startup, serves the public half as JWKS on a loopback port the OS picks, and signs three credentials: valid, wrong-scope, and expired.

Two limits worth knowing. It shows the **inbound** half only: with no Catalyst project there is no MCP server to reach, so the agent calls the in-process tool and the on-behalf-of leg does not appear. And it is debug-only — the file is behind `#if DEBUG` and `agent/Dockerfile` publishes `-c Release`, so setting `DIAGRID_QUICKSTART_IDENTITY=local` on a container fails to start rather than disabling authentication.

### 1. Start the Local Issuer

Stop the `diagrid dev run` from the previous section first, since both bind port 8006.

```bash
DIAGRID_QUICKSTART_IDENTITY=local dotnet run --project agent --urls http://localhost:8006
```

The startup output logs the three credentials, ready to paste:

```text
warn: agent[0]
      LOCAL IDENTITY MODE - throwaway keys, never a real deployment
info: agent[0]
      JWKS served at http://127.0.0.1:56895/jwks.json
info: agent[0]
      200 (verified, has agent.invoke):
info: agent[0]
        eyJhbGciOiJSUzI1NiIsImtpZCI6ImxvY2FsLXF1aWNrc3RhcnQta2V5...
info: agent[0]
      403 (verifies, wrong scope) oauth.missing_scope:
info: agent[0]
        eyJhbGciOiJSUzI1NiIsImtpZCI6ImxvY2FsLXF1aWNrc3RhcnQta2V5...
info: agent[0]
      401 (expired 5 minutes ago) oauth.expired:
info: agent[0]
        eyJhbGciOiJSUzI1NiIsImtpZCI6ImxvY2FsLXF1aWNrc3RhcnQta2V5...
info: EnterpriseIdentity.Model[0]
      Using the canned offline model: no API key needed and the answer is always the same. Set DIAGRID_QUICKSTART_MODEL=openai for a real provider.
info: Microsoft.Hosting.Lifetime[14]
      Now listening on: http://localhost:8006
```

The private key lives in this process's memory and the credentials it signs are printed in plain text. Never use this mode outside local development.

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
curl -i -X POST -H "X-Diagrid-User-Token: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"task": "What bookings do I have?"}' http://localhost:8006/agent/run
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

Look at the second message. The tool was asked for `someone@example.com` and answered for `alice@example.com`, because the tool instance the run was handed is closed over the subject the middleware verified.

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

`403`, not `401`, and the distinction is deliberate: authentication succeeded and authorization failed.

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

The verifier allows 120 seconds of clock skew, so this credential is backdated five minutes.

## How It Works

The credential the app verifies is **not** the one the caller sent. Catalyst verifies the caller's identity-provider token at the edge and passes a Catalyst-signed identity to the app in `X-Diagrid-User-Token`. Your application never sees the original token and never talks to your identity provider.

That is what makes the app's configuration so small. `AddDiagridIdentity()` names a policy and nothing else -- here, "a verified caller is required". The issuer, audience and JWKS URI are read from Catalyst at first use, so changing identity providers changes nothing in the app.

The middleware then does five things in order, and stops at the first failure:

1. No `X-Diagrid-User-Token` header, or an empty one: `401 oauth.missing_token`
2. The credential is not a well-formed JWT: `401 oauth.decode_error`
3. Signature or claims fail against the discovered JWKS: `401`, with a code naming the reason, such as `oauth.expired`
4. The verified scopes do not include every required scope: `403 oauth.missing_scope`
5. Otherwise it builds a `VerifiedUser`, attaches it to `HttpContext.Items`, and stores the raw token for the duration of the request

Only after step 5 does any of this repository's code run. Both handlers in `agent/IdentityEndpoints.cs` read `context.GetVerifiedUser()` and can treat it as trustworthy, because an untrustworthy request never reached them.

Inside the agent, identity is deliberately ordinary. `POST /agent/run` builds the tool for the verified subject and passes it as `ChatClientAgentRunOptions`, which the framework merges into that one invocation. The subject is therefore per-run configuration rather than a message the model could rewrite. Nothing about the agent is Diagrid-specific, which is the point: the same agent runs unchanged off Catalyst, just without a verified caller to run it for.

The outbound half is smaller still. `account_summary` reaches Catalyst's MCP proxy over the `HttpClient` that `AddDiagridIdentityHttpClient()` registered, and that client's handler reads the caller's token at *send* time and sets the header itself. One client is therefore safe to share across concurrent requests, and the app never assembles an identity header -- which is also why the user token must never be put in `HttpClientTransportOptions.AdditionalHeaders` instead.

## Files

| File | Purpose |
|------|---------|
| `agent/Program.cs` | The composition root: the three-line identity install, the model choice, the tool choice, `GET /whoami` and `POST /agent/run` |
| `agent/IdentityEndpoints.cs` | Both route handlers and the identity projection |
| `agent/IdentityAgent.cs` | The `ChatClientAgent`, built tool-less and handed one tool per run — which is how the verified subject reaches the tool as configuration |
| `agent/Tools.cs` | Both tools: `my_bookings(subject)` runs in-process, `account_summary(accountId)` goes out through Catalyst's MCP proxy and carries the caller with it |
| `agent/CannedChatClient.cs` | The deterministic canned model, so the quickstart needs no API key |
| `agent/LocalIdentity.cs` | The opt-in throwaway issuer for the offline section and the tests. Debug builds only |
| `crm-mcp/Program.cs` | The stand-in CRM behind MCP. Its one tool reports the user and the agent it was called for |
| `resources/` | The `MCPServer` registration and the access policy whose `requireUser: true` turns on on-behalf-of |
| `dev-enterprise-identity.yaml` | The `diagrid dev run` file: `identity-agent` on port 8006, `crm-mcp` on 8007 |
| `unit-tests/IdentityTests.cs` | The offline tests: `401`, `403`, `200`, and the verified subject reaching the tool. `dotnet test unit-tests` |
| `test.http` | The same four requests, for the VS Code REST Client. Its credential-bearing pair needs the offline issuer |

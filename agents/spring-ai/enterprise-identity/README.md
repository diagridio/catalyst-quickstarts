# Spring AI Quickstart - End-User Identity, End to End

This quickstart demonstrates a [Spring AI](https://docs.spring.io/spring-ai/reference/) agent running on **Diagrid Catalyst** that knows *who is calling it* and calls its tools as that person. The caller presents a credential from an identity provider; Catalyst verifies it, hands the agent a verified user, and mints a fresh token for each tool call so the tool can see the caller too. The agent handles no password, API key or token of its own.

One bean buys the inbound half. Look at `identity-agent/src/main/java/.../EnterpriseIdentityApplication.java` and note what is absent: no `io.diagrid` import in the controller, in the agent configuration or in either tool, and nothing in the application reads a header or a credential.

```java
@Bean
OAuthFilter diagridOAuthFilter() {
  return new OAuthFilter(new OAuthConfig());   // who is calling
}
```

## What This Quickstart Demonstrates

- **Verified inbound identity**: `OAuthFilter` verifies the `X-Diagrid-User-Token` header on every request and publishes a `VerifiedUser`, carrying `subject`, `tenant`, `scopes`, `claims` and `issuerId`, which handlers read with `OAuthFilter.verifiedUser(request)`
- **Nothing to configure**: `new OAuthConfig()` discovers the issuer, audience and JWKS URI from Catalyst, so the app hardcodes no identity coordinates and no provider URLs
- **The caller reaches the tool too**: the agent's outbound call goes through Catalyst's MCP proxy, which mints a token naming both the user and the agent acting for them, so the CRM establishes who is asking rather than trusting the agent
- **Fail closed, before your code**: a missing credential is a `401` and an insufficient one is a `403`, decided in the filter before the agent, the model, or any application code runs
- **A plain Spring AI agent, on the synchronous path**: a `ChatClient` and two `@Tool` methods, called from a `@RestController`. **No `diagrid-spring-ai-starter`** and so no Dapr Workflow, unlike the three sibling quickstarts in [`agents/spring-ai`](../) — you can see exactly where identity enters and how little of the agent knows about it
- **The verified subject, not the model's guess**: the canned model asks for `someone@example.com`, who is nobody. The tool answers for the verified subject instead, so the reply names the real caller
- **Direct LLM integration**: runs on a deterministic canned model by default, so no API key is needed; a real provider is opt-in via `spring-ai-starter-model-openai`

## Current Scope

This quickstart covers both legs of the journey.

**Inbound** is the end user's verified identity arriving at the agent: Catalyst checks the caller's credential, exchanges it for a Catalyst-signed identity, and hands the agent a `VerifiedUser`.

**Outbound**, also called on-behalf-of, is the agent carrying that caller onward to a tool. When the agent calls the CRM through Catalyst's MCP proxy, Catalyst mints a *second* token, scoped to that one tool and naming two parties: the user it is for, and the agent acting for them. The CRM establishes who is asking for itself rather than taking the agent's word for it.

The difference matters. With inbound alone, the agent knows you are Alice and then calls every tool as one shared service account -- the CRM cannot tell Alice from Bob, so it cannot apply Alice's permissions. Outbound is what lets the downstream system enforce them.

## Prerequisites

1. [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/overview) installed
2. [JDK 21](https://adoptium.net/) or later, and [Maven 3.9+](https://maven.apache.org/download.cgi)

No LLM API key, and no identity provider of your own. The model is canned by default, and the last section runs the whole thing offline against a throwaway issuer.

## Setup

Navigate to the `enterprise-identity` directory and build both applications:

```bash
cd agents/spring-ai/enterprise-identity
mvn package -DskipTests
```

This directory holds **two** Maven modules under one aggregator pom: `identity-agent` is the agent, and `crm-mcp` is the stand-in CRM it calls. One build command covers both.

### Using a real LLM provider

This quickstart runs offline by default. It uses a canned model, needs no API key, and returns the same tool call and the same answer on every run, whatever task you send. To use a real model instead, set `DIAGRID_QUICKSTART_MODEL` to `openai` and export your key. The example below uses OpenAI, but you can use any LLM provider Spring AI supports.

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
diagrid agent create identity-agent --wait
diagrid apply -f resources/crm-mcp.yaml
diagrid apply -f resources/crm-mcp-access.yaml
```

`crm-mcp.yaml` scopes the CRM to `identity-agent`, and Catalyst rejects a scope that names an App ID which does not exist yet — so the agent's App ID is created first. The CRM needs no such step: registering the MCP server creates its App ID automatically, which is also why `crm-mcp` must not be created by hand. `agent create` rather than `appid create`: an Agent carries the agent config the sidecar needs to verify the caller and attach the user identity.

The first registers the CRM as an MCP server, so the agent reaches it through Catalyst rather than calling it directly. The second is the interesting one:

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

4. Run both applications with Catalyst:

```bash
diagrid dev run -f dev-enterprise-identity.yaml --approve --skip-managed-kv --skip-managed-pubsub --skip-managed-workflow
```

The three `--skip-*` flags are worth understanding rather than copying. This agent calls no Dapr building block at all: no state, no pub/sub, no workflow. There is nothing for a managed KV store, a managed broker or a managed workflow store to serve, and without these flags `dev run` provisions all three the first time it creates the App ID. Identity needs none of them, because it is served by the sidecar itself.

Wait until the output shows `Tomcat started on port 8006`.

### 2. Ask the Agent Who You Are

From another terminal.

`diagrid call invoke` sends your Diagrid login with the request as the `X-Diagrid-User-Token` header, so that the agent can act on your behalf. That header is the whole subject of this quickstart:

```bash
diagrid call invoke get identity-agent.whoami --id identity-agent --verbose
```

`--verbose` is what prints the response body. It also echoes the request that was sent, so treat that output as you would treat the credential itself.

`GET /whoami` runs no model turn and no tool, which makes it the cheapest place to see identity on its own. It returns the four fields `IdentityController` chooses to expose from the `VerifiedUser`:

```text
subject     the token's `sub` claim: who the caller is
tenant      the token's `tid` claim: which tenant they belong to
issuer_id   the `iss` value on the verified token
scopes      the scopes the verified credential carried
```

The full decoded credential is available to the handler as `user.claims()`, and `IdentityController` deliberately does not return it. Claim *names* are safe to echo; claim *values* are a real person's identity data, and whatever the provider chose to put there would leak with them.

> **On scopes.** `new OAuthConfig()` here requires a *verified* caller and nothing more. You can also demand a scope -- `new OAuthConfig(Set.of("reports.read"))` answers `403 {"error": "oauth.missing_scope"}` for any verified caller without it. The walkthrough does not, because scopes come from your identity provider and no Catalyst command can add them: a Diagrid login carries `openid profile email offline_access` and nothing else, so requiring one would answer 403 for everybody. [Run Offline Without a Catalyst Project](#run-offline-without-a-catalyst-project) demonstrates the 403 against an issuer that does mint the scope.

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

Note what `CrmTools.accountSummary` does *not* take: a subject argument. It cannot be told who is calling, so it cannot be lied to. That is the difference between it and `BookingTools.myBookings`, whose caller is a string the model fills in.

You can watch both hops in the terminal running `diagrid dev run`:

```text
== APP - identity-agent == [IDENTITY] verified caller subject=... issuer=...
== APP - crm-mcp        == account_summary(ACME-1) for user=... via agent=...
```

The first line is Catalyst's verdict on your credential. The second is the CRM, one network hop later, independently establishing the same person.

### 4. See It Fail Closed

`diagrid dev run` connects Catalyst to `localhost:8006`, so you can also reach the app directly. Doing so bypasses Catalyst, which means the request arrives with no credential attached at all:

```bash
curl -i http://localhost:8006/whoami
```

```text
HTTP/1.1 401
Cache-Control: no-store
Content-Type: application/json;charset=UTF-8

{"error":"oauth.missing_token"}
```

The `Cache-Control: no-store` is the filter's, not Spring MVC's: an authorization verdict is not a cacheable response.

Every route answers the same way. `requireAuth` defaults to `true` and applies to the whole application, with no per-path exclusion:

```bash
curl -i -X POST http://localhost:8006/agent/run -H "Content-Type: application/json" -d '{"task": "What bookings do I have?"}'
```

That app-wide rule is also why this quickstart exposes no health endpoint -- there is no `spring-boot-starter-actuator` on the classpath -- and why `dev-enterprise-identity.yaml` sets `enableAppHealthCheck: false`. An unauthenticated probe could only ever see the `401`, so a health check would report a perfectly healthy app as down.

**VS Code REST Client (any OS):** Open [`test.http`](./test.http) and click *Send Request* above either of the two requests that send no credential. Requires the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension. Its other two requests need a credential the app will accept, and these requests reach port 8006 directly — bypassing Catalyst — so a token from your own identity provider is refused `401 oauth.invalid_signature` here. Fill in `@token` from the offline section below, which is the only mode that mints a credential this app verifies.

To stop, press CTRL+C in the terminal running `diagrid dev run`.

## Run Offline Without a Catalyst Project

**What this is for.** Two things, and it is opt-in for both:

1. **Try the quickstart with no Catalyst project at all** -- no login, no project, no identity provider.
2. **See the `403`**, which the walkthrough above cannot show you. A `403` needs a credential that verifies but lacks a required scope, and scopes come from your identity provider: a Diagrid login carries `openid profile email offline_access` and no Catalyst command can add to that. Here the issuer is yours, so it can mint a credential deliberately missing one.

`LocalIdentityIssuer` generates a throwaway key at startup, serves the public half on a loopback port, and signs three credentials: valid, wrong-scope, and expired. It is the same trade `CannedChatModel` makes for the model -- free, offline, identical on every run.

Three limits worth knowing. It shows the **inbound** half only: with no Catalyst project there is no MCP server to reach, so the agent is given the in-process tool and the on-behalf-of leg does not appear. Only the agent runs, so nothing binds port 8007. And, unlike the [Python version of this quickstart](../../langgraph/enterprise-identity/), **nothing keeps the offline issuer out of a built image**: `.dockerignore` cannot exclude a class that Maven already compiled into `target/*.jar`, so the only guards are the opt-in environment variable and the `WARNING` the issuer logs on every start.

### 1. Start the Local Issuer

Stop the `diagrid dev run` from the previous section first, since both bind port 8006.

```bash
DIAGRID_QUICKSTART_IDENTITY=local mvn -f identity-agent/pom.xml spring-boot:run
```

This generates a throwaway RSA key, serves the public half as JWKS on a loopback port the OS picks, and logs three ready-to-paste credentials:

```text
WARN  i.d.q.s.e.LocalIdentityIssuer : LOCAL IDENTITY MODE - throwaway keys, never a real deployment
INFO  i.d.q.s.e.LocalIdentityIssuer : JWKS served at http://127.0.0.1:57013/jwks.json
INFO  i.d.q.s.e.LocalIdentityIssuer : 200 (verified, has agent.invoke):
INFO  i.d.q.s.e.LocalIdentityIssuer :   eyJraWQiOiJsb2NhbC1xdWlja3N0YXJ0LWtleSIsImFsZyI6IlJTMjU2In0...
INFO  i.d.q.s.e.LocalIdentityIssuer : 403 (verifies, wrong scope) oauth.missing_scope:
INFO  i.d.q.s.e.LocalIdentityIssuer :   eyJraWQiOiJsb2NhbC1xdWlja3N0YXJ0LWtleSIsImFsZyI6IlJTMjU2In0...
INFO  i.d.q.s.e.LocalIdentityIssuer : 401 (expired 5 minutes ago) oauth.expired:
INFO  i.d.q.s.e.LocalIdentityIssuer :   eyJraWQiOiJsb2NhbC1xdWlja3N0YXJ0LWtleSIsImFsZyI6IlJTMjU2In0...
INFO  i.d.q.s.e.CannedModelConfig   : >>> Using the canned offline model: no API key needed and the answer is always the same.
INFO  o.s.boot.tomcat.TomcatWebServer : Tomcat started on port 8006 (http) with context path '/'
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

Look at the second message. The tool was asked for `someone@example.com` and answered for `alice@example.com`, because it read the verified subject out of the tool context instead of trusting the argument the model filled in. The identity is visible *inside the agent's own conversation*, which is the difference between propagating identity and echoing a header back.

### 3. A Credential Without the Scope (403)

The credential logged under `403` verifies perfectly. It is signed by the same issuer, it has not expired, and its subject is `bob@example.com`. It simply carries `reports.read` instead of `agent.invoke`:

```bash
export TOKEN="<the credential logged under 403>"
curl -i -H "X-Diagrid-User-Token: Bearer $TOKEN" http://localhost:8006/whoami
```

```text
HTTP/1.1 403

{"error":"oauth.missing_scope"}
```

`403`, not `401`, and the distinction is deliberate: authentication succeeded and authorization failed. The filter knows exactly who `bob@example.com` is and is refusing him anyway.

### 4. An Expired Credential (401)

The credential logged under `401` is the `200` credential, five minutes stale:

```bash
export TOKEN="<the credential logged under 401>"
curl -i -H "X-Diagrid-User-Token: Bearer $TOKEN" http://localhost:8006/whoami
```

```text
HTTP/1.1 401

{"error":"oauth.expired"}
```

Five minutes, not one. The verifier allows 120 seconds of clock skew, so a credential that expired a minute ago still returns `200`. Anything demonstrating expiry has to be older than the skew window.

## How It Works

The credential the app verifies is **not** the one the caller sent. Catalyst verifies the caller's upstream identity-provider token at the edge, exchanges it with dataplane Sentry, and passes a Catalyst-signed identity to the app in `X-Diagrid-User-Token`. Your application never sees the original token and never talks to your identity provider.

That is what makes the app's configuration so small. `new OAuthConfig()` names a policy and nothing else -- here, "a verified caller is required". The issuer, audience and JWKS URI are read from Catalyst at first use, so changing identity providers changes nothing in the app.

The filter then does five things in order, and stops at the first failure:

1. No `X-Diagrid-User-Token` header, or an empty one: `401 oauth.missing_token`
2. The credential is not a well-formed JWT: `401 oauth.decode_error`
3. Signature or claims fail against the discovered JWKS: `401`, with a code naming the reason, such as `oauth.expired`
4. The verified scopes do not include every required scope: `403 oauth.missing_scope`
5. Otherwise it publishes a `VerifiedUser` on the request and parks the raw token for the duration of it

Only after step 5 does any of this repository's code run. Both handlers in `IdentityController` call `OAuthFilter.verifiedUser(request).orElseThrow()` and can treat the result as trustworthy, because an untrustworthy request never reached them.

Inside the agent, identity is deliberately ordinary. `POST /agent/run` passes the verified subject in `.toolContext(...)`, and the tool reads it from there. The tool context belongs to the application: unlike a message or a tool argument, the model never sees it and cannot rewrite it. Nothing about the agent is Diagrid-specific, which is the point -- the same agent runs unchanged off Catalyst, just without a verified caller to run it for.

### Three things Java does differently

The [Python version of this quickstart](../../langgraph/enterprise-identity/) is the reference for this one, and three differences are worth stating rather than glossing.

**The outbound hand-off is explicit.** In Python, the SDK's identity-aware HTTP client is handed straight to the MCP transport and decides the header per request. Java's MCP transport takes only an `HttpClient.Builder`, never a pre-built client, and `IdentityContext` holds the caller in a `ThreadLocal` that the transport's sending thread may not share. So `CatalystMcpClient` uses the hand-off the SDK prescribes for exactly this case: `transportContextProvider` reads the caller on the request thread, and `httpRequestCustomizer` sets `IdentityContext.USER_TOKEN_HEADER` with `IdentityContext.BEARER_PREFIX` on whichever thread sends. The header name and the scheme are still the SDK's constants — but this application does assemble the header, and the Python one does not. The two approaches cannot be combined, either: `IdentityHttpClient.wrap` clears the header and re-sets it from the current thread, so wrapping the transport's client would strip the header on exactly the sends the hand-off exists to cover. Measured with `logging.level.io.diagrid.quickstart.springai=DEBUG`: for a single tool call the JSON-RPC `POST`s go out on the request thread while the SSE `GET` stream and the post-initialize notification go out on a JDK `HttpClient-1-Worker-N`. A wrapped client would have carried the caller on some of those and silently not on others.

**The tool transcript is assembled through the tool context.** `ChatClient.call().content()` returns only the final assistant message; Spring AI runs the tool calls inside that call rather than replaying a message history the way LangGraph does. So the tool context carries a list the tools append their answers to, and `IdentityController` assembles the `messages` array from it. That is a structural difference, not a cosmetic one — and it doubles as a demonstration that the tool context is the application's channel and not the model's.

**The offline issuer cannot be excluded from an image.** Python's `.dockerignore` keeps `local_identity.py` out of the build context, so setting `DIAGRID_QUICKSTART_IDENTITY=local` on a container fails to start instead of quietly disabling authentication. This repository's Java images copy an already-built `target/*.jar`, so no build-context exclusion can reach a compiled class. The env-var gate and the issuer's `WARNING` are the only guards here.

## Files

| File | Purpose |
|------|---------|
| `pom.xml` | The aggregator over both modules, so one `mvn package` builds the agent and the CRM. It deliberately does **not** depend on `diagrid-spring-ai-starter` |
| `identity-agent/.../EnterpriseIdentityApplication.java` | The one-bean identity install, and the choice between Catalyst's identity plane and the offline issuer |
| `identity-agent/.../IdentityController.java` | `GET /whoami` and `POST /agent/run`, and the only place this app touches identity |
| `identity-agent/.../AgentConfig.java` | The `ChatClient` and the tool it is given. No durability dependency, so nothing runs as a workflow |
| `identity-agent/.../BookingTools.java` | `my_bookings(subject)`, which runs in-process and answers for the verified subject rather than the one the model asked for |
| `identity-agent/.../CrmTools.java` | `account_summary(accountId)`, which takes no subject at all and goes out through Catalyst's MCP proxy |
| `identity-agent/.../CatalystMcpClient.java` | The MCP client, and the cross-thread on-behalf-of hand-off described above |
| `identity-agent/.../AgentToolContext.java` | The tool context: the verified subject and the tool transcript, both owned by the application |
| `identity-agent/.../CannedChatModel.java` | The deterministic canned model, so the quickstart needs no API key |
| `identity-agent/.../LocalIdentityIssuer.java` | The opt-in throwaway issuer used by the offline section and by the tests. Never part of a deployment |
| `crm-mcp/.../CrmTools.java` | The stand-in CRM's one tool. It reports the user and the agent it was called for, and verifies nothing -- Catalyst already did |
| `resources/` | The `MCPServer` registration and the access policy whose `requireUser: true` turns on on-behalf-of |
| `dev-enterprise-identity.yaml` | The `diagrid dev run` file: `identity-agent` on port 8006, `crm-mcp` on 8007 |
| `identity-agent/src/test/java/...` | The offline tests: `401`, `403`, `200`, the verified subject reaching the tool, and the outbound hand-off. `mvn test` |
| `test.http` | The same four requests, for the VS Code REST Client. Its credential-bearing pair needs the offline issuer |

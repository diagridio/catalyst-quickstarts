using Diagrid.AI.Identity;
using EnterpriseIdentity;
using Microsoft.Extensions.AI;
using OpenAI;

// Which identity plane the app trusts, and so which tool the agent can use. The offline issuer runs
// with no Catalyst project behind it, so there is no MCP server to reach and the agent calls the
// in-process tool instead. Against Catalyst the tool call leaves the agent and picks the caller up
// on the way.
var offlineIdentity = string.Equals(
    Environment.GetEnvironmentVariable("DIAGRID_QUICKSTART_IDENTITY"),
    "local",
    StringComparison.OrdinalIgnoreCase);

var builder = WebApplication.CreateBuilder(args);

#if DEBUG
// Declared out here so the credentials can be logged after the app is built, which is the first
// point at which there is a logger to log them with.
LocalIdentity.LocalIssuer? localIssuer = null;
#endif

// --- The entire Catalyst identity integration ------------------------------
if (offlineIdentity)
{
#if DEBUG
    // DIAGRID_QUICKSTART_IDENTITY=local swaps in a throwaway offline issuer so the 200, 403 and 401
    // responses are all reachable with no Catalyst project and no identity provider at all. The
    // credentials are logged below. See LocalIdentity.cs.
    var issuer = LocalIdentity.BuildLocalIssuer(LocalIdentity.RequiredScopes);
    localIssuer = issuer;
    builder.Services.AddDiagridIdentity(config =>
    {
        config.Scopes = issuer.Config.Scopes;
        config.Issuer = issuer.Config.Issuer;
        config.Audience = issuer.Config.Audience;
        config.JwksUri = issuer.Config.JwksUri;
    });
#else
    // A compiled assembly cannot omit a source file the way the python sibling's .dockerignore
    // omits local_identity.py, so the guard is this: the issuer does not exist in a Release build
    // and asking for it refuses to start. The Dockerfile publishes -c Release, so setting this
    // variable on a container fails closed instead of quietly trusting tokens the app minted
    // itself. Prose is a weaker guard than a missing type.
    throw new InvalidOperationException(
        "DIAGRID_QUICKSTART_IDENTITY=local is a debug-only mode: it replaces the Catalyst identity "
        + "plane with a throwaway in-process issuer, so it is compiled out of Release builds. "
        + "Unset the variable to verify against Catalyst.");
#endif
}
else
{
    // Against Catalyst this is the whole configuration. Issuer, audience and JWKS URI are all
    // discovered from Catalyst, so the app names none of them.
    //
    // To require a scope as well, pass one: AddDiagridIdentity(config => config.Scopes =
    // ["reports.read"]) answers 403 for any verified caller without it. That needs an identity
    // provider issuing the scope, which is why the walkthrough does not use it.
    builder.Services.AddDiagridIdentity();
}

// The outbound half. This client carries the calling user on every request it makes: its handler
// reads the inbound token at send time, so one shared client is safe under concurrency and
// concurrent requests each carry their own caller. The app never assembles an identity header.
builder.Services.AddDiagridIdentityHttpClient(configure: client =>
{
    // Catalyst's own API token, which is a separate concern from the end user's identity: this one
    // says the APP may talk to its sidecar, the user token says WHO it is talking for. Added only
    // when set, because an empty header value is rejected outright.
    var daprApiToken = Environment.GetEnvironmentVariable("DAPR_API_TOKEN");
    if (!string.IsNullOrEmpty(daprApiToken))
    {
        client.DefaultRequestHeaders.Add("dapr-api-token", daprApiToken);
    }
});
// ---------------------------------------------------------------------------

builder.Services.AddSingleton(serviceProvider =>
{
    var loggerFactory = serviceProvider.GetRequiredService<ILoggerFactory>();
    var httpClientFactory = serviceProvider.GetRequiredService<IHttpClientFactory>();

    // The agent gets one tool or the other, built per request from the verified subject. The
    // offline issuer cannot reach an MCP server, so my_bookings keeps the whole walkthrough
    // runnable there; account_summary takes no subject and ignores the one it is offered.
    Func<string, AIFunction> toolForCaller = offlineIdentity
        ? Tools.MyBookings
        : _ => Tools.AccountSummary(
            httpClientFactory.CreateClient(
                DiagridIdentityHttpClientServiceCollectionExtensions.DefaultClientName),
            loggerFactory);

    return IdentityAgent.Create(BuildChatClient(loggerFactory), toolForCaller, loggerFactory);
});

var app = builder.Build();

// --- The other half of the identity integration ----------------------------
app.UseDiagridIdentity();
// ---------------------------------------------------------------------------
// RequireAuth stays at its default true, so every route is authenticated. That is why no health
// route is exposed and why dev-enterprise-identity.yaml sets enableAppHealthCheck: false -- an
// unauthenticated probe would only ever see the 401. There is no per-path exclusion; RequireAuth is
// app-wide.

#if DEBUG
if (offlineIdentity)
{
    LocalIdentity.LogCredentials(app.Logger, localIssuer!);
}
#endif

// Materialised at start-up rather than on the first request. Two reasons: the line saying which
// model was chosen belongs in the startup output a reader is watching, and a missing OPENAI_API_KEY
// on the opt-in provider path should stop the app rather than fail the first call.
app.Services.GetRequiredService<IdentityAgent>();

// Who Catalyst says is calling. No model turn, so the 401/200 contrast is free.
app.MapGet("/whoami", IdentityEndpoints.WhoAmI);
app.MapPost("/agent/run", IdentityEndpoints.AgentRun);

await app.RunAsync();

// The model: a real provider on request, the canned one otherwise. The identity behaviour is
// identical either way -- a real model, like the canned one, does not know who is calling and is
// not consulted on the question.
IChatClient BuildChatClient(ILoggerFactory loggerFactory)
{
    var logger = loggerFactory.CreateLogger("EnterpriseIdentity.Model");

    if (!string.Equals(
        Environment.GetEnvironmentVariable("DIAGRID_QUICKSTART_MODEL"),
        "openai",
        StringComparison.OrdinalIgnoreCase))
    {
        logger.LogInformation(
            "Using the canned offline model: no API key needed and the answer is always the same. "
            + "Set DIAGRID_QUICKSTART_MODEL=openai for a real provider.");

        return new CannedChatClient(offlineIdentity);
    }

    // IsNullOrWhiteSpace, not a null check: on Unix an exported-but-empty variable reads back as
    // "", which would fail deeper in the OpenAI client with a message about an argument rather than
    // about the key.
    var apiKey = Environment.GetEnvironmentVariable("OPENAI_API_KEY");
    if (string.IsNullOrWhiteSpace(apiKey))
    {
        throw new InvalidOperationException(
            "OPENAI_API_KEY is required when DIAGRID_QUICKSTART_MODEL=openai.");
    }

    logger.LogInformation("Using OpenAI (gpt-4.1-mini).");

    return new OpenAIClient(apiKey).GetChatClient("gpt-4.1-mini").AsIChatClient();
}

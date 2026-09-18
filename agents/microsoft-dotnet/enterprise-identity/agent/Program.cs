using Diagrid.AI.Identity;
using EnterpriseIdentity;
using Microsoft.Extensions.AI;
using OpenAI;

// Which identity plane the app trusts, and so which tool the agent can use: the offline issuer has
// no Catalyst project behind it, so there is no MCP server to reach.
var offlineIdentity = string.Equals(
    Environment.GetEnvironmentVariable("DIAGRID_QUICKSTART_IDENTITY"),
    "local",
    StringComparison.OrdinalIgnoreCase);

var builder = WebApplication.CreateBuilder(args);

#if DEBUG
// Declared out here so the credentials can be logged once there is a logger to log them with.
LocalIdentity.LocalIssuer? localIssuer = null;
#endif

// --- The entire Catalyst identity integration ------------------------------
if (offlineIdentity)
{
#if DEBUG
    // A throwaway offline issuer, so 200, 403 and 401 are all reachable with no Catalyst project.
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
    // Compiled out of Release builds, so a container cannot trust tokens the app minted itself.
    throw new InvalidOperationException(
        "DIAGRID_QUICKSTART_IDENTITY=local is a debug-only mode: it replaces the Catalyst identity "
        + "plane with a throwaway in-process issuer, so it is compiled out of Release builds. "
        + "Unset the variable to verify against Catalyst.");
#endif
}
else
{
    // Against Catalyst this is the whole configuration: issuer, audience and JWKS URI are all
    // discovered, so the app names none of them. Pass config.Scopes to require a scope as well.
    builder.Services.AddDiagridIdentity();
}

// The outbound half. The handler reads the inbound token at send time, so one shared client is safe
// under concurrency and the app never assembles an identity header itself.
builder.Services.AddDiagridIdentityHttpClient(configure: client =>
{
    // Catalyst's own API token, a separate concern from the end user's identity: this says the APP
    // may talk to its sidecar, the user token says WHO it is talking for.
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

    // The agent gets one tool or the other, built per request from the verified subject.
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
// RequireAuth stays at its default true, so every route is authenticated — including any health
// probe, which is why dev-enterprise-identity.yaml sets enableAppHealthCheck: false.

#if DEBUG
if (offlineIdentity)
{
    LocalIdentity.LogCredentials(app.Logger, localIssuer!);
}
#endif

// Built at start-up so a missing OPENAI_API_KEY stops the app rather than failing the first call.
app.Services.GetRequiredService<IdentityAgent>();

// Who Catalyst says is calling. No model turn, so the 401/200 contrast is free.
app.MapGet("/whoami", IdentityEndpoints.WhoAmI);
app.MapPost("/agent/run", IdentityEndpoints.AgentRun);

await app.RunAsync();

// The model: a real provider on request, the canned one otherwise. Neither is consulted on who is
// calling.
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

    // IsNullOrWhiteSpace, not a null check: an exported-but-empty variable reads back as "".
    var apiKey = Environment.GetEnvironmentVariable("OPENAI_API_KEY");
    if (string.IsNullOrWhiteSpace(apiKey))
    {
        throw new InvalidOperationException(
            "OPENAI_API_KEY is required when DIAGRID_QUICKSTART_MODEL=openai.");
    }

    logger.LogInformation("Using OpenAI (gpt-4.1-mini).");

    return new OpenAIClient(apiKey).GetChatClient("gpt-4.1-mini").AsIChatClient();
}

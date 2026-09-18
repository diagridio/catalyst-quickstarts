using System.Buffers.Text;
using System.ComponentModel;
using System.Text.Json;
using ModelContextProtocol.Server;

var builder = WebApplication.CreateBuilder(args);

builder.Services
    .AddMcpServer(options => options.ServerInfo = new() { Name = "crm", Version = "1.0.0" })
    .WithHttpTransport()
    .WithTools<CrmTools>();

// The C# stand-in for fastmcp's get_http_headers(): the tool below needs the headers of the request
// the MCP call arrived on, and this is what makes them reachable from inside it.
builder.Services.AddHttpContextAccessor();

var app = builder.Build();
// "/mcp", explicitly: MapMcp() defaults to the application root, and resources/crm-mcp.yaml
// registers this server with Catalyst at http://localhost:8007/mcp.
app.MapMcp("/mcp");

await app.RunAsync();

/// <summary>
/// A stand-in CRM, exposed over MCP.
/// </summary>
/// <remarks>
/// Its one tool reports the identity the call arrived with. The agent sends no password and no API
/// key, and the CRM still knows whose question it is answering — and which agent asked on their
/// behalf.
/// </remarks>
[McpServerToolType]
internal sealed class CrmTools(IHttpContextAccessor httpContextAccessor, ILogger<CrmTools> logger)
{
    /// <summary>The header Catalyst mints for one call and forwards to this server.</summary>
    private const string UserTokenHeader = "X-Diagrid-User-Token";

    private const string BearerPrefix = "Bearer ";

    /// <summary>
    /// Summarises a CRM account, and reports who the CRM is answering.
    /// </summary>
    /// <param name="accountId">The account to summarise.</param>
    /// <returns>The summary, naming the calling user and the agent acting for them.</returns>
    [McpServerTool(Name = "account_summary")]
    [Description("Summarise a CRM account, and report who the CRM is answering.")]
    public string AccountSummary([Description("The CRM account id.")] string accountId)
    {
        var claims = CallingUser();
        var user = ReadString(claims, "sub") ?? "<no user identity>";
        // `act` is the actor claim: the agent that made this call on the user's behalf. Two
        // identities in one token is what on-behalf-of means.
        var agent = claims is not null
            && claims.Value.TryGetProperty("act", out var actor)
            && actor.ValueKind == JsonValueKind.Object
                ? ReadString(actor, "sub") ?? "<no agent>"
                : "<no agent>";

        logger.LogInformation(
            "account_summary({AccountId}) for user={User} via agent={Agent}",
            accountId,
            user,
            agent);

        return $"Account {accountId}: 3 open opportunities, $120k pipeline. "
            + $"Served to user={user} via agent={agent}.";
    }

    /// <summary>
    /// Reads the calling user from the token Catalyst minted for this request.
    /// </summary>
    /// <remarks>
    /// Catalyst verifies the signature before the request arrives, so this only decodes the claims
    /// in order to show them. A server that needed to decide anything on these claims would have to
    /// verify the token itself — which is what Diagrid.AI.Identity's middleware is for, and why the
    /// agent next door installs it and this stand-in does not.
    /// </remarks>
    /// <returns>The decoded payload, or <see langword="null"/> when the call carried no user.</returns>
    private JsonElement? CallingUser()
    {
        var raw = httpContextAccessor.HttpContext?.Request.Headers[UserTokenHeader].ToString();
        if (string.IsNullOrWhiteSpace(raw))
        {
            return null;
        }

        var token = raw.StartsWith(BearerPrefix, StringComparison.OrdinalIgnoreCase)
            ? raw[BearerPrefix.Length..].Trim()
            : raw.Trim();

        var parts = token.Split('.');
        if (parts.Length < 2)
        {
            return null;
        }

        try
        {
            // Base64Url handles the unpadded encoding JWT segments use, which a plain
            // Convert.FromBase64String would reject.
            var payload = Base64Url.DecodeFromChars(parts[1]);
            using var document = JsonDocument.Parse(payload);
            return document.RootElement.Clone();
        }
        catch (Exception exception) when (exception is FormatException or JsonException)
        {
            // A malformed token is a display problem here and nothing more: this server is not the
            // one adjudicating the call, so it reports "no user identity" rather than refusing.
            logger.LogWarning("the user token on this request could not be decoded");
            return null;
        }
    }

    private static string? ReadString(JsonElement? element, string property) =>
        element is not null
            && element.Value.TryGetProperty(property, out var value)
            && value.ValueKind == JsonValueKind.String
                ? value.GetString()
                : null;
}

using Microsoft.Extensions.AI;
using ModelContextProtocol.Client;
using ModelContextProtocol.Protocol;

namespace EnterpriseIdentity;

/// <summary>
/// The two ways an agent can act for someone. <see cref="MyBookings(string)"/> runs in-process and
/// is built around the caller's verified subject; <see cref="AccountSummary(HttpClient,
/// ILoggerFactory)"/> leaves the process, carrying the caller in a token Catalyst mints per call.
/// </summary>
public static class Tools
{
    public const string MyBookingsToolName = "my_bookings";

    public const string AccountSummaryToolName = "account_summary";

    /// <summary>The MCP server as registered with Catalyst in <c>resources/crm-mcp.yaml</c>.</summary>
    private const string McpServerName = "crm-mcp";

    private const string DefaultDaprHttpEndpoint = "http://localhost:3500";

    /// <summary>
    /// The in-process tool, built for one verified caller — the substitution this sample is about.
    /// The tool declares a <c>subject</c> parameter so the model asks for one, and asks for the
    /// wrong one; the body ignores it and answers for the verified subject instead.
    /// </summary>
    public static AIFunction MyBookings(string verifiedSubject) => AIFunctionFactory.Create(
        // Deliberately unused: it puts the parameter in the schema the model sees.
        (string subject) =>
            $"Bookings for {verifiedSubject}: "
            + "Grand Ballroom on March 15th, 9AM-1PM; "
            + "Rooftop Terrace on March 22nd, 6PM-11PM.",
        MyBookingsToolName,
        "List the bookings that belong to the calling user.");

    // --- The outbound half: calling a tool as the user -------------------------

    /// <summary>
    /// The outbound tool: summarise a CRM account, as the user who invoked the agent. It takes no
    /// subject, so it cannot be told who is calling. <paramref name="identityHttpClient"/> is what
    /// attaches the caller, setting <c>X-Diagrid-User-Token</c> itself — never do that by hand.
    /// </summary>
    public static AIFunction AccountSummary(HttpClient identityHttpClient, ILoggerFactory loggerFactory) =>
        AIFunctionFactory.Create(
            async (string accountId, CancellationToken cancellationToken) =>
            {
                await using var transport = new HttpClientTransport(
                    new HttpClientTransportOptions
                    {
                        Endpoint = new Uri(McpUrl()),
                        // Named rather than AutoDetect: the proxy speaks streamable HTTP, and
                        // detection would spend a round trip probing for SSE first.
                        TransportMode = HttpTransportMode.StreamableHttp,
                    },
                    identityHttpClient,
                    loggerFactory,
                    // The client is the DI container's, shared across requests.
                    ownsHttpClient: false);

                await using var client = await McpClient.CreateAsync(
                    transport,
                    loggerFactory: loggerFactory,
                    cancellationToken: cancellationToken);

                var answer = await client.CallToolAsync(
                    AccountSummaryToolName,
                    new Dictionary<string, object?> { ["accountId"] = accountId },
                    cancellationToken: cancellationToken);

                return answer.Content.OfType<TextContentBlock>().FirstOrDefault()?.Text
                    ?? "<the CRM returned no text>";
            },
            AccountSummaryToolName,
            "Summarise a CRM account. Runs as the user who invoked the agent.");

    /// <summary>
    /// Catalyst's MCP proxy for the CRM. Reaching a tool through this path is what attaches the
    /// calling user; calling the CRM directly would not.
    /// </summary>
    private static string McpUrl()
    {
        var daprHttpEndpoint = Environment.GetEnvironmentVariable("DAPR_HTTP_ENDPOINT");
        var endpoint = string.IsNullOrWhiteSpace(daprHttpEndpoint)
            ? DefaultDaprHttpEndpoint
            : daprHttpEndpoint.TrimEnd('/');

        return $"{endpoint}/v1.0/diagrid/mcp/{McpServerName}";
    }
}

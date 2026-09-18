using Microsoft.Extensions.AI;
using ModelContextProtocol.Client;
using ModelContextProtocol.Protocol;

namespace EnterpriseIdentity;

/// <summary>
/// The agent's tools.
/// </summary>
/// <remarks>
/// Two tools, showing the two ways an agent can act for someone.
/// <see cref="MyBookings(string)"/> runs in-process and is built around the caller's verified
/// subject. <see cref="AccountSummary(HttpClient, ILoggerFactory)"/> leaves the process, and
/// carries the caller in a token Catalyst mints for that one call.
/// </remarks>
public static class Tools
{
    /// <summary>The in-process tool's name, as the model asks for it.</summary>
    public const string MyBookingsToolName = "my_bookings";

    /// <summary>The outbound tool's name, which is also the CRM's own tool name.</summary>
    public const string AccountSummaryToolName = "account_summary";

    /// <summary>The MCP server as registered with Catalyst in <c>resources/crm-mcp.yaml</c>.</summary>
    private const string McpServerName = "crm-mcp";

    private const string DefaultDaprHttpEndpoint = "http://localhost:3500";

    /// <summary>
    /// The in-process tool, built for one verified caller.
    /// </summary>
    /// <remarks>
    /// <para>
    /// The substitution this whole sample is about. The tool still declares a <c>subject</c>
    /// parameter, so the model asks for one and asks for the wrong one — the canned first turn
    /// requests <see cref="CannedChatClient.ModelGuess"/>, who is nobody. The body ignores that
    /// argument and answers for <paramref name="verifiedSubject"/>, which came from the
    /// middleware's <c>VerifiedUser</c> and reached this tool as per-run configuration the model
    /// cannot rewrite.
    /// </para>
    /// </remarks>
    /// <param name="verifiedSubject">The subject the middleware verified for this request.</param>
    /// <returns>The tool, closed over that subject.</returns>
    public static AIFunction MyBookings(string verifiedSubject) => AIFunctionFactory.Create(
        // `subject` is declared and deliberately unused: it is what puts the parameter in the
        // schema the model sees, so the model can ask for the wrong person and be overridden.
        (string subject) =>
            $"Bookings for {verifiedSubject}: "
            + "Grand Ballroom on March 15th, 9AM-1PM; "
            + "Rooftop Terrace on March 22nd, 6PM-11PM.",
        MyBookingsToolName,
        "List the bookings that belong to the calling user.");

    // --- The outbound half: calling a tool as the user -------------------------
    // MyBookings above runs in-process, so it trusts whatever subject the agent hands it.
    // AccountSummary below leaves the process, and that changes the trust story: it takes no
    // subject at all. The calling user travels in a token Catalyst mints for this one call, so the
    // CRM establishes who is asking for itself rather than believing the agent.

    /// <summary>
    /// The outbound tool: summarise a CRM account, as the user who invoked the agent.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Note what it does NOT take: a subject. It cannot be told who is calling, so it cannot be
    /// lied to.
    /// </para>
    /// <para>
    /// <paramref name="identityHttpClient"/> is the only thing that attaches the caller. It comes
    /// from <c>AddDiagridIdentityHttpClient</c>, whose handler reads the inbound token at send time
    /// and sets <c>X-Diagrid-User-Token</c> itself. Do not put the user token in
    /// <see cref="HttpClientTransportOptions.AdditionalHeaders"/> instead: that is the app
    /// assembling an identity header by hand, with no origin guard and no send-time read.
    /// </para>
    /// </remarks>
    /// <param name="identityHttpClient">The identity-aware client the MCP transport sends on.</param>
    /// <param name="loggerFactory">Receives the MCP client's own diagnostics.</param>
    /// <returns>The tool.</returns>
    public static AIFunction AccountSummary(HttpClient identityHttpClient, ILoggerFactory loggerFactory) =>
        AIFunctionFactory.Create(
            async (string accountId, CancellationToken cancellationToken) =>
            {
                await using var transport = new HttpClientTransport(
                    new HttpClientTransportOptions
                    {
                        Endpoint = new Uri(McpUrl()),
                        // Named rather than left to AutoDetect: Catalyst's proxy speaks streamable
                        // HTTP, and detection would spend a round trip probing for SSE first.
                        TransportMode = HttpTransportMode.StreamableHttp,
                    },
                    identityHttpClient,
                    loggerFactory,
                    // The client is the DI container's, shared across requests. Disposing it here
                    // would break every later tool call.
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
    /// Catalyst's MCP proxy for the CRM.
    /// </summary>
    /// <remarks>
    /// Reaching a tool through this path is what attaches the calling user; calling the CRM
    /// directly on port 8007 would not. Read per call rather than cached in a static, so the
    /// sidecar endpoint the app was started with is the one it uses.
    /// </remarks>
    /// <returns>The absolute proxy URL.</returns>
    private static string McpUrl()
    {
        var daprHttpEndpoint = Environment.GetEnvironmentVariable("DAPR_HTTP_ENDPOINT");
        var endpoint = string.IsNullOrWhiteSpace(daprHttpEndpoint)
            ? DefaultDaprHttpEndpoint
            : daprHttpEndpoint.TrimEnd('/');

        return $"{endpoint}/v1.0/diagrid/mcp/{McpServerName}";
    }
}

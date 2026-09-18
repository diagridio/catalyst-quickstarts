using Microsoft.Extensions.AI;

namespace EnterpriseIdentity;

/// <summary>
/// A deterministic stand-in for a hosted chat model.
/// </summary>
/// <remarks>
/// <para>
/// This quickstart's point is inbound identity, not model quality, so it ships a canned two-turn
/// conversation: ask for the tool, then answer from the tool's result. That keeps the demo free,
/// offline and identical on every run. Set <c>DIAGRID_QUICKSTART_MODEL=openai</c> and
/// <c>OPENAI_API_KEY</c> to use a real provider instead.
/// </para>
/// <para>
/// Note the subject the first turn asks for: <see cref="ModelGuess"/>, which is nobody. A model
/// does not know who is calling and must not be trusted to decide — <see cref="Tools.MyBookings"/>
/// is built around the subject the middleware verified and substitutes it over this argument. A
/// real provider behaves the same way, which is the point of substituting rather than validating.
/// </para>
/// <para>
/// The turn is chosen by counting tool results in the conversation, so it stays correct however
/// many times the client is re-entered.
/// </para>
/// </remarks>
public sealed class CannedChatClient : IChatClient
{
    /// <summary>The model id this client reports.</summary>
    public const string ModelId = "canned-offline";

    /// <summary>
    /// The subject the canned first turn asks <c>my_bookings</c> for.
    /// </summary>
    /// <remarks>
    /// Nobody. It must never reach the tool's answer, and the unit tests assert it appears nowhere
    /// in the response body.
    /// </remarks>
    public const string ModelGuess = "someone@example.com";

    /// <summary>The account the Catalyst-path first turn asks <c>account_summary</c> for.</summary>
    public const string AccountId = "ACME-1";

    private static readonly ChatClientMetadata Meta = new("canned", null, ModelId);

    private readonly bool _offline;

    /// <summary>
    /// Initializes a new instance of the <see cref="CannedChatClient"/> class.
    /// </summary>
    /// <param name="offline">
    /// Whether the agent is running on the offline identity plane, which decides which tool the
    /// first turn calls. The offline issuer has no Catalyst project behind it, so there is no MCP
    /// server to reach and the in-process tool is the only one available.
    /// </param>
    public CannedChatClient(bool offline) => _offline = offline;

    /// <inheritdoc />
    public object? GetService(Type serviceType, object? serviceKey = null)
    {
        ArgumentNullException.ThrowIfNull(serviceType);

        // A keyed lookup asks for something this client does not provide. Otherwise: its metadata,
        // or itself, which is the rest of the IChatClient convention.
        return serviceKey is not null ? null
            : serviceType == typeof(ChatClientMetadata) ? Meta
            : serviceType.IsInstanceOfType(this) ? this
            : null;
    }

    /// <inheritdoc />
    public Task<ChatResponse> GetResponseAsync(
        IEnumerable<ChatMessage> messages,
        ChatOptions? options = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(messages);

        var toolHasRun = messages
            .SelectMany(message => message.Contents)
            .OfType<FunctionResultContent>()
            .Any();

        // The parameter names are load-bearing: AIFunctionFactory takes them from the tool lambdas
        // in Tools.cs, so a mismatch here is a tool call the framework cannot bind.
        AIContent content = (toolHasRun, _offline) switch
        {
            (false, true) => new FunctionCallContent(
                "call_my_bookings_1",
                Tools.MyBookingsToolName,
                new Dictionary<string, object?> { ["subject"] = ModelGuess }),
            (false, false) => new FunctionCallContent(
                "call_account_summary_1",
                Tools.AccountSummaryToolName,
                new Dictionary<string, object?> { ["accountId"] = AccountId }),
            (true, true) => new TextContent(
                "You have two bookings: the Grand Ballroom on March 15th "
                + "(9AM-1PM) and the Rooftop Terrace on March 22nd (6PM-11PM)."),
            (true, false) => new TextContent($"Here is what the CRM returned for {AccountId}."),
        };

        var response = new ChatResponse(new ChatMessage(ChatRole.Assistant, [content]))
        {
            ModelId = ModelId,
            // Reported for fidelity rather than control flow: the framework decides whether to run
            // another turn from whether the response carries function calls, not from this.
            FinishReason = toolHasRun ? ChatFinishReason.Stop : ChatFinishReason.ToolCalls,
        };

        return Task.FromResult(response);
    }

    /// <summary>
    /// Throws, deliberately. Nothing in this quickstart streams, and a clear failure beats a canned
    /// half-answer.
    /// </summary>
    /// <param name="messages">Ignored.</param>
    /// <param name="options">Ignored.</param>
    /// <param name="cancellationToken">Ignored.</param>
    /// <returns>Never returns.</returns>
    public IAsyncEnumerable<ChatResponseUpdate> GetStreamingResponseAsync(
        IEnumerable<ChatMessage> messages,
        ChatOptions? options = null,
        CancellationToken cancellationToken = default) =>
        throw new NotSupportedException("streaming is not supported");

    /// <inheritdoc />
    public void Dispose()
    {
    }
}

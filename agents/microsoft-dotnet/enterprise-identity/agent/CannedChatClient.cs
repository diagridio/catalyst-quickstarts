using Microsoft.Extensions.AI;

namespace EnterpriseIdentity;

/// <summary>
/// A deterministic stand-in for a hosted chat model: a canned two-turn conversation that asks for
/// the tool, then answers from its result. Set <c>DIAGRID_QUICKSTART_MODEL=openai</c> and
/// <c>OPENAI_API_KEY</c> for a real provider, which behaves the same way in what matters here.
/// </summary>
public sealed class CannedChatClient : IChatClient
{
    public const string ModelId = "canned-offline";

    /// <summary>
    /// The subject the canned first turn asks <c>my_bookings</c> for. Nobody: a model does not know
    /// who is calling, and this must never reach the tool's answer.
    /// </summary>
    public const string ModelGuess = "someone@example.com";

    public const string AccountId = "ACME-1";

    private static readonly ChatClientMetadata Meta = new("canned", null, ModelId);

    private readonly bool _offline;

    /// <summary>
    /// Initializes a new instance of the <see cref="CannedChatClient"/> class. The offline plane has
    /// no MCP server to reach, so which tool the first turn asks for depends on it.
    /// </summary>
    public CannedChatClient(bool offline) => _offline = offline;

    /// <inheritdoc />
    public object? GetService(Type serviceType, object? serviceKey = null)
    {
        ArgumentNullException.ThrowIfNull(serviceType);

        // A keyed lookup asks for something this client does not provide.
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

        // The parameter names must match the tool lambdas in Tools.cs, or the call cannot bind.
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
            FinishReason = toolHasRun ? ChatFinishReason.Stop : ChatFinishReason.ToolCalls,
        };

        return Task.FromResult(response);
    }

    /// <summary>Throws, deliberately: nothing in this quickstart streams.</summary>
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

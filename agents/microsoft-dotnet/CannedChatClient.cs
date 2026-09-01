using System.Text.Json;
using Microsoft.Extensions.AI;

/// <summary>
/// An offline <see cref="IChatClient"/> that always plays the same script: call the three tools in
/// the order the sample mandates, then report what the last one returned.
///
/// Why this exists. This quickstart is about durable execution, not model quality, and the model is
/// on its critical path: every LLM call and every tool call runs as a separate Dapr workflow
/// activity, and the model's tool choice is the only thing that reaches step_two_compare, whose
/// delay is the crash window. So the demo cannot run without a model at all, and shipping a canned
/// one is what lets it run without an account. Set DIAGRID_QUICKSTART_MODEL=openai to use a real
/// provider instead (see Program.cs).
///
/// FOUR TURNS, NOT TWO, and the tool ordering is why. Program.cs explains that step_one_search must
/// complete and be recorded before the slow step_two_compare starts, or the crash lands before
/// anything has completed and the replay proves nothing. Each tool also takes the previous tool's
/// result as its argument, because the real model is instructed to chain them. So the script is:
/// tool 1, tool 2, tool 3, then a final answer.
///
/// THE TURN IS CHOSEN BY COUNTING TOOL RESULTS IN THE CONVERSATION, NEVER BY A CALL COUNTER. The
/// SDK rebuilds the whole conversation from the workflow's recorded history and passes it on every
/// call, and this client runs inside an activity that can be re-entered. A counter field would
/// reset with the process and re-run step_one_search after the restart, which is exactly the
/// replay failure this quickstart exists to disprove.
/// </summary>
public sealed class CannedChatClient : IChatClient
{
    public const string ModelId = "canned-offline";

    /// <summary>
    /// Fixed rather than read back from the prompt. The city reaches step_one_search's log line and
    /// its return string and then washes out: tool 2 answers "Grand Ballroom is the best option"
    /// whatever it is handed, and tool 3's text is the final answer. So parsing it would buy a
    /// truthful log line and nothing else. This is the sample's own default prompt and the body the
    /// Catalyst console sends, so the three stay in agreement.
    /// </summary>
    private const string City = "Austin";

    /// <summary>
    /// The IChatClient convention: implementations describe themselves here, and generic
    /// Microsoft.Extensions.AI middleware (telemetry, caching, logging) reads it.
    ///
    /// It is NOT what the Catalyst agent registry displays. That reads the concrete type's name for
    /// the LLM client, and takes the provider from a Dapr conversation component rather than from
    /// the client at all: it looks for one named after the agent, falls back to the first
    /// conversation component in the project, and reports "unknown" when there is none. This
    /// quickstart uses a direct client and no conversation component, so it reports client
    /// "CannedChatClient" with provider and model "unknown" — the same "unknown" it already reports
    /// on the OpenAI path. The class name is the only part of this that reaches the console.
    /// </summary>
    private static readonly ChatClientMetadata Meta = new("canned", null, ModelId);

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

    public Task<ChatResponse> GetResponseAsync(
        IEnumerable<ChatMessage> messages,
        ChatOptions? options = null,
        CancellationToken cancellationToken = default)
    {
        // The conversation is the state, not a field on this object. Every turn the workflow has
        // recorded is replayed into this list, so counting results here stays correct after a crash
        // in a way a counter never is.
        var results = messages
            .SelectMany(message => message.Contents)
            .OfType<FunctionResultContent>()
            .ToList();

        // The parameter names are load-bearing: AIFunctionFactory.Create takes them from the tool
        // lambdas in Program.cs, so a mismatch here is a tool call the framework cannot bind.
        AIContent content = results.Count switch
        {
            0 => Call("call_1", "step_one_search", "city", City),
            1 => Call("call_2", "step_two_compare", "data", Text(results[0])),
            2 => Call("call_3", "step_three_confirm", "selection", Text(results[1])),
            3 => new TextContent(Text(results[2])),
            // Loud, not a fall-through to "answer with the last result". The count is a proxy for
            // how far through a three-tool script this is, and it counts every result in the
            // conversation. Anything that puts more there — a session's PriorMessages, an
            // AIContextProvider's additional messages — makes that proxy wrong, and the quiet
            // failure is answering a new question with the previous turn's answer and running no
            // tools at all.
            _ => throw new InvalidOperationException(
                $"The canned script covers three tool results; this conversation carries {results.Count}."
                + " This client does not support sessions or prior message history."),
        };

        var response = new ChatResponse(new ChatMessage(ChatRole.Assistant, [content]))
        {
            ModelId = ModelId,
            // Reported for fidelity rather than control flow: the SDK decides whether to run
            // another turn from whether the response carries function calls, not from this.
            FinishReason = results.Count < 3 ? ChatFinishReason.ToolCalls : ChatFinishReason.Stop,
        };
        return Task.FromResult(response);
    }

    /// <summary>
    /// Throws, deliberately. Nothing in this quickstart streams, and a durable activity that
    /// streamed would have nothing to record, so a clear failure beats a canned half-answer.
    /// </summary>
    public IAsyncEnumerable<ChatResponseUpdate> GetStreamingResponseAsync(
        IEnumerable<ChatMessage> messages,
        ChatOptions? options = null,
        CancellationToken cancellationToken = default) =>
        throw new NotSupportedException("streaming is not supported");

    public void Dispose()
    {
    }

    /// <summary>
    /// A tool result as text. The SDK round-trips results through JSON, so Result arrives as a
    /// JsonElement; the string case is unwrapped to its unquoted value, which is what the next tool
    /// wants as its argument and what the final answer should read as.
    ///
    /// Anything else throws rather than stringifying. All three tools here return strings, and a
    /// tool changed to return a record would otherwise hand raw JSON to the next tool as its
    /// argument and end the demo with a JSON blob for an answer, with nothing to say why.
    /// </summary>
    private static string Text(FunctionResultContent result) => result.Result switch
    {
        JsonElement { ValueKind: JsonValueKind.String } text => text.GetString() ?? string.Empty,
        null => string.Empty,
        var other => throw new InvalidOperationException(
            $"The canned script chains tool results as strings; got {other}. Tools must return a string."),
    };

    private static FunctionCallContent Call(string callId, string name, string parameter, string value) =>
        new(callId, name, new Dictionary<string, object?> { [parameter] = value });
}

using System.Text.Json;
using Microsoft.Extensions.AI;
using Xunit;

namespace microsoft_dotnet.Tests;

/// <summary>
/// The offline model's contract, which is what the crash-recovery demo runs on by default.
///
/// Cases 1 to 3 are the ones that would catch a parameter-name drift against Program.cs's tool
/// lambdas, which is the failure that produces a tool call the framework cannot bind.
/// </summary>
public class CannedChatClientTests
{
    private readonly CannedChatClient client = new();

    private static readonly string[] ToolNames = ["step_one_search", "step_two_compare", "step_three_confirm"];

    /// <summary>
    /// A conversation carrying <paramref name="toolResults"/> completed tool calls, shaped the way
    /// the SDK rebuilds it from recorded workflow history: an assistant message carrying the call,
    /// then a tool message carrying its result. Results arrive as JSON, so Result is a JsonElement
    /// rather than a string.
    ///
    /// The assistant turns do not change today's outcome, because the client counts only
    /// FunctionResultContent. They are here so the fixture is the thing this docstring claims it
    /// is: without them a change that paired calls to results, or that read the assistant history,
    /// would pass every test and break in production.
    /// </summary>
    private static List<ChatMessage> Conversation(params string[] toolResults)
    {
        var messages = new List<ChatMessage>
        {
            new(ChatRole.System, "You are an event planner."),
            new(ChatRole.User, "Find a venue in Austin for a company gala"),
        };
        for (var i = 0; i < toolResults.Length; i++)
        {
            var callId = $"call_{i + 1}";
            // Beyond the third there is no scripted tool; the name only has to be present, because
            // the over-length case exists to prove the client refuses that conversation.
            var toolName = i < ToolNames.Length ? ToolNames[i] : $"unscripted_{i + 1}";
            messages.Add(new ChatMessage(ChatRole.Assistant, [
                new TextContent(string.Empty),
                new FunctionCallContent(callId, toolName, new Dictionary<string, object?> { ["arg"] = "x" }),
            ]));
            var result = JsonSerializer.Deserialize<JsonElement>(JsonSerializer.Serialize(toolResults[i]));
            messages.Add(new ChatMessage(ChatRole.Tool, [new FunctionResultContent(callId, result)]));
        }
        return messages;
    }

    private async Task<ChatResponse> Respond(params string[] toolResults) =>
        await this.client.GetResponseAsync(Conversation(toolResults));

    private static FunctionCallContent SingleCall(ChatResponse response) =>
        Assert.Single(response.Messages[^1].Contents.OfType<FunctionCallContent>());

    [Fact]
    public async Task OpensBySearchingTheCity()
    {
        var call = SingleCall(await this.Respond());

        Assert.Equal("step_one_search", call.Name);
        Assert.Equal("Austin", Assert.Contains("city", call.Arguments!));
    }

    [Fact]
    public async Task ComparesUsingTheFirstToolsResult()
    {
        // The chaining is the point: the real model is instructed to pass each result on, so the
        // canned one has to as well or the recorded conversation stops making sense.
        var call = SingleCall(await this.Respond("Found 3 venues in Austin. Now call step_two_compare."));

        Assert.Equal("step_two_compare", call.Name);
        Assert.Equal("Found 3 venues in Austin. Now call step_two_compare.", Assert.Contains("data", call.Arguments!));
    }

    [Fact]
    public async Task ConfirmsUsingTheSecondToolsResult()
    {
        var call = SingleCall(await this.Respond(
            "Found 3 venues in Austin. Now call step_two_compare.",
            "Grand Ballroom is the best option. Now call step_three_confirm."));

        Assert.Equal("step_three_confirm", call.Name);
        Assert.Equal(
            "Grand Ballroom is the best option. Now call step_three_confirm.",
            Assert.Contains("selection", call.Arguments!));
    }

    [Fact]
    public async Task AnswersWithTheThirdToolsResultAndAsksForNothingMore()
    {
        var response = await this.Respond(
            "Found 3 venues in Austin. Now call step_two_compare.",
            "Grand Ballroom is the best option. Now call step_three_confirm.",
            "Booking confirmed for Grand Ballroom. All steps complete!");

        Assert.Empty(response.Messages[^1].Contents.OfType<FunctionCallContent>());
        Assert.Equal("Booking confirmed for Grand Ballroom. All steps complete!", response.Messages[^1].Text);
    }

    [Fact]
    public async Task ReportsToolCallsUntilTheScriptIsDoneAndThenStops()
    {
        Assert.Equal(ChatFinishReason.ToolCalls, (await this.Respond()).FinishReason);
        Assert.Equal(ChatFinishReason.ToolCalls, (await this.Respond("one")).FinishReason);
        Assert.Equal(ChatFinishReason.ToolCalls, (await this.Respond("one", "two")).FinishReason);
        Assert.Equal(ChatFinishReason.Stop, (await this.Respond("one", "two", "three")).FinishReason);

        Assert.Equal(CannedChatClient.ModelId, (await this.Respond()).ModelId);
    }

    [Fact]
    public async Task PicksTheTurnFromTheConversationRatherThanACallCounter()
    {
        // The one that matters after a crash. The SDK replays the recorded conversation into this
        // client, so the same conversation must produce the same turn however many times it is
        // called. A counter would re-run step_one_search on the restart, which is the replay
        // failure this quickstart exists to disprove.
        var first = SingleCall(await this.Respond("Found 3 venues in Austin. Now call step_two_compare."));
        var second = SingleCall(await this.Respond("Found 3 venues in Austin. Now call step_two_compare."));

        // Asserted against the expected tool, not just against each other: two calls that both
        // wrongly returned step_one_search would be equal, and re-running step_one_search after a
        // restart is precisely the failure this test is named for.
        Assert.Equal("step_two_compare", first.Name);
        Assert.Equal("step_two_compare", second.Name);
        Assert.Equal(first.Arguments!["data"], second.Arguments!["data"]);
    }

    [Fact]
    public async Task RefusesAConversationLongerThanTheScript()
    {
        // Loud rather than answering with a stale result. Sessions and prior message history both
        // put extra results in the conversation, and the count is what tells this client which turn
        // it is on.
        var tooMany = await Assert.ThrowsAsync<InvalidOperationException>(
            () => this.Respond("one", "two", "three", "four"));

        Assert.Contains("carries 4", tooMany.Message);
    }

    [Fact]
    public async Task RefusesAToolResultThatIsNotAString()
    {
        // The three tools all return strings, and their results are chained into the next tool's
        // argument. A tool changed to return a record would otherwise pass raw JSON along silently.
        var messages = Conversation();
        var structured = JsonSerializer.Deserialize<JsonElement>("""{"venues":3}""");
        messages.Add(new ChatMessage(ChatRole.Tool, [new FunctionResultContent("call_1", structured)]));

        var wrongType = await Assert.ThrowsAsync<InvalidOperationException>(
            () => this.client.GetResponseAsync(messages));

        Assert.Contains("must return a string", wrongType.Message);
    }

    [Fact]
    public void DescribesItselfThroughTheChatClientConvention()
    {
        var metadata = Assert.IsType<ChatClientMetadata>(this.client.GetService(typeof(ChatClientMetadata)));

        Assert.Equal("canned", metadata.ProviderName);
        Assert.Equal(CannedChatClient.ModelId, metadata.DefaultModelId);
        // The rest of the convention: itself for its own type and for IChatClient, null for an
        // unrelated type or any keyed lookup, and a throw for a null type.
        Assert.Same(this.client, this.client.GetService(typeof(IChatClient)));
        Assert.Same(this.client, this.client.GetService(typeof(CannedChatClient)));
        Assert.Null(this.client.GetService(typeof(string)));
        Assert.Null(this.client.GetService(typeof(ChatClientMetadata), "a-key"));
        Assert.Throws<ArgumentNullException>(() => this.client.GetService(null!));
    }

    [Fact]
    public void KeepsTheTypeNameTheAgentRegistryDisplays()
    {
        // The Catalyst agent registry reports the concrete type's name verbatim as this agent's LLM
        // client, so renaming this class silently changes what a user sees on the agent page and
        // nothing else here would notice.
        Assert.Equal("CannedChatClient", typeof(CannedChatClient).Name);
    }

    [Fact]
    public void RefusesToStream()
    {
        Assert.Throws<NotSupportedException>(() => this.client.GetStreamingResponseAsync(Conversation()));
    }
}

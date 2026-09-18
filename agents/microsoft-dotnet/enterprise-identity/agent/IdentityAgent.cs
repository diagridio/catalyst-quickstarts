using System.Text.Json;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace EnterpriseIdentity;

/// <summary>
/// The Microsoft Agent Framework agent this quickstart runs, and the one thing it needs per
/// request: the verified caller.
/// </summary>
/// <remarks>
/// <para>
/// An ordinary <see cref="ChatClientAgent"/>. Note what is absent: nothing here imports anything
/// from Diagrid, and no tool reads a header or a credential. Identity is handled entirely in the
/// HTTP layer (see Program.cs) and reaches the agent as a plain string.
/// </para>
/// <para>
/// No Dapr Workflow and no durable agent runtime. <see cref="ChatClientAgent.RunAsync(string,
/// AgentSession, ChatClientAgentRunOptions, CancellationToken)"/> is called straight from the
/// request handler, so you can see exactly where identity enters and how little of the agent knows
/// about it.
/// </para>
/// </remarks>
public sealed class IdentityAgent
{
    /// <summary>The agent name, which is also the App ID in <c>dev-enterprise-identity.yaml</c>.</summary>
    public const string AgentName = "identity-agent";

    /// <summary>
    /// The instructions a real provider runs on.
    /// </summary>
    /// <remarks>
    /// Kept even though <see cref="CannedChatClient"/> ignores them: they are what the OpenAI
    /// branch needs, and what a reader swapping in another provider reads first. They say nothing
    /// about who is calling, because the model is not consulted on that question.
    /// </remarks>
    private const string Instructions = """
        You help a signed-in user with their own bookings and accounts.
        Use the tool you are given to answer, and answer only from what it returns.
        """;

    private readonly ChatClientAgent _agent;
    private readonly Func<string, AIFunction> _toolForCaller;
    private readonly ILogger<IdentityAgent> _logger;

    private IdentityAgent(
        ChatClientAgent agent,
        Func<string, AIFunction> toolForCaller,
        ILogger<IdentityAgent> logger)
    {
        _agent = agent;
        _toolForCaller = toolForCaller;
        _logger = logger;
    }

    /// <summary>
    /// Builds the agent.
    /// </summary>
    /// <remarks>
    /// The agent is built with no tools, which is deliberate.
    /// <see cref="ChatClientAgentRunOptions.ChatOptions"/> is merged with the agent's own defaults
    /// per invocation, and for collections such as <see cref="ChatOptions.Tools"/> the two are
    /// UNIONED rather than substituted. An agent constructed with a default tool that also received
    /// a per-request one would therefore present the model two tools of the same name.
    /// </remarks>
    /// <param name="chatClient">The model, canned or real.</param>
    /// <param name="toolForCaller">
    /// Builds the tool for one verified subject. The offline path returns
    /// <see cref="Tools.MyBookings"/> closed over that subject; the Catalyst path returns
    /// <see cref="Tools.AccountSummary"/>, which takes no subject at all and ignores the argument.
    /// </param>
    /// <param name="loggerFactory">Receives both the framework's and this class's diagnostics.</param>
    /// <returns>The agent.</returns>
    public static IdentityAgent Create(
        IChatClient chatClient,
        Func<string, AIFunction> toolForCaller,
        ILoggerFactory loggerFactory)
    {
        ArgumentNullException.ThrowIfNull(chatClient);
        ArgumentNullException.ThrowIfNull(toolForCaller);
        ArgumentNullException.ThrowIfNull(loggerFactory);

        var agent = chatClient.AsAIAgent(
            instructions: Instructions,
            name: AgentName,
            tools: null,
            loggerFactory: loggerFactory);

        return new IdentityAgent(agent, toolForCaller, loggerFactory.CreateLogger<IdentityAgent>());
    }

    /// <summary>
    /// Runs the agent on behalf of the verified caller.
    /// </summary>
    /// <remarks>
    /// <paramref name="verifiedSubject"/> travels as per-invocation configuration — the tool
    /// instance the run is handed — and not as a message the model could rewrite. That is the whole
    /// security point: a model can request anybody's bookings, and only the verified caller's are
    /// ever served.
    /// </remarks>
    /// <param name="task">What the caller asked for.</param>
    /// <param name="verifiedSubject">The subject the middleware verified.</param>
    /// <param name="cancellationToken">Cancels the run.</param>
    /// <returns>
    /// The conversation as text: the task, then every tool result and model answer the run
    /// produced, in order.
    /// </returns>
    public async Task<IReadOnlyList<string>> RunAsync(
        string task,
        string verifiedSubject,
        CancellationToken cancellationToken)
    {
        _logger.LogInformation("[IDENTITY] tool call for subject={Subject}", verifiedSubject);

        var runOptions = new ChatClientAgentRunOptions(new ChatOptions
        {
            Tools = [_toolForCaller(verifiedSubject)],
        });

        var response = await _agent.RunAsync(task, null, runOptions, cancellationToken);

        // The task first, then what the run produced. AgentResponse.Messages carries only the
        // messages the agent generated — the assistant's turns and the tool results — so the
        // caller's own question has to be put back for the reply to read as a conversation.
        var transcript = new List<string> { task };
        foreach (var content in response.Messages.SelectMany(message => message.Contents))
        {
            // The empty assistant message that carries only a function call is dropped.
            var text = content switch
            {
                // A tool result may arrive as the string the tool returned or as the JSON the
                // framework round-tripped it through, depending on the invoker. Unwrap the JSON
                // spelling, or the transcript reads back with the quotes still on.
                FunctionResultContent result => result.Result switch
                {
                    JsonElement { ValueKind: JsonValueKind.String } json => json.GetString(),
                    var other => other?.ToString(),
                },
                TextContent textContent => textContent.Text,
                _ => null,
            };
            if (!string.IsNullOrWhiteSpace(text))
            {
                transcript.Add(text);
            }
        }

        return transcript;
    }
}

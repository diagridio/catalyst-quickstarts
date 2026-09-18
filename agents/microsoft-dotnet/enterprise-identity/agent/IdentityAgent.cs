using System.Text.Json;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace EnterpriseIdentity;

/// <summary>
/// The Microsoft Agent Framework agent this quickstart runs: an ordinary
/// <see cref="ChatClientAgent"/>. Nothing here imports anything from Diagrid and no tool reads a
/// header — identity is handled in the HTTP layer and reaches the agent as a plain string.
/// </summary>
public sealed class IdentityAgent
{
    /// <summary>The agent name, which is also the App ID in <c>dev-enterprise-identity.yaml</c>.</summary>
    public const string AgentName = "identity-agent";

    /// <summary>
    /// The instructions a real provider runs on. They say nothing about who is calling, because the
    /// model is not consulted on that question.
    /// </summary>
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
    /// Builds the agent with no default tools: per-run <see cref="ChatOptions.Tools"/> are UNIONED
    /// with the agent's own, so a default tool would be presented to the model twice.
    /// </summary>
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
    /// Runs the agent on behalf of the verified caller. <paramref name="verifiedSubject"/> travels
    /// as per-invocation configuration — the tool instance the run is handed — and not as a message
    /// the model could rewrite: the model can ask for anybody's bookings, and only the verified
    /// caller's are ever served.
    /// </summary>
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

        // AgentResponse.Messages carries only what the agent generated, so the task goes back in.
        var transcript = new List<string> { task };
        foreach (var content in response.Messages.SelectMany(message => message.Contents))
        {
            var text = content switch
            {
                // A tool result may arrive as a raw string or as JSON the framework round-tripped
                // it through; unwrap the JSON, or the transcript keeps its quotes.
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

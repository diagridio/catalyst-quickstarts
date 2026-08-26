using System.Diagnostics;
using Dapr.Workflow;
using Diagrid.AI.Microsoft.AgentFramework.Abstractions;
using Diagrid.AI.Microsoft.AgentFramework.Hosting;
using Diagrid.AI.Microsoft.AgentFramework.Catalyst;
using Diagrid.AI.Microsoft.AgentFramework.Runtime;
using Microsoft.Extensions.AI;
using OpenAI;

var builder = WebApplication.CreateBuilder(args);

var apiKey = Environment.GetEnvironmentVariable("OPENAI_API_KEY")
    ?? throw new InvalidOperationException("OPENAI_API_KEY environment variable is required.");

// How long step_two_compare takes. This is the window you kill the app in, so it has to be
// long enough for a human to aim a second terminal at: three instantaneous tools give you
// nothing to interrupt.
var delaySeconds = int.TryParse(Environment.GetEnvironmentVariable("CRASH_DELAY_SECONDS"), out var seconds)
    ? seconds
    : 30;

// The TOOL ORDER is the design. Each tool call is a separate Dapr workflow activity, so
// step_one_search completes and Catalyst records its result before the slow step_two_compare
// starts. The crash therefore lands between two known points, and after the restart
// step_one_search's lines must NOT appear again: that absence is what proves the replay used
// the recorded result. Make the FIRST tool the slow one and the crash lands before anything
// has completed, the run restarts from nothing, and the demo proves nothing at all.
var tools = new List<AITool>
{
    AIFunctionFactory.Create((string city) =>
    {
        Console.WriteLine($">>> TOOL 1: Searching venues in '{city}'...");
        Console.WriteLine(">>> TOOL 1 COMPLETE: Found 3 venues");
        return $"Found 3 venues in {city}. Now call step_two_compare.";
    }, "step_one_search", "Search for event venues in a city. This is the first step."),

    AIFunctionFactory.Create(async (string data) =>
    {
        Console.WriteLine($">>> TOOL 2: Comparing venues over ~{delaySeconds}s. KILL THE APP NOW to"
            + " test crash recovery (POST /crash/kill, or kill -9). It resumes on restart.");
        await Task.Delay(TimeSpan.FromSeconds(delaySeconds));
        Console.WriteLine(">>> TOOL 2 COMPLETE: Grand Ballroom is the best option");
        return "Grand Ballroom is the best option. Now call step_three_confirm.";
    }, "step_two_compare", "Compare the venue options. This is the second step."),

    AIFunctionFactory.Create((string selection) =>
    {
        Console.WriteLine(">>> TOOL 3: Confirming booking...");
        Console.WriteLine(">>> TOOL 3 COMPLETE: Booking confirmed for Grand Ballroom");
        return "Booking confirmed for Grand Ballroom. All steps complete!";
    }, "step_three_confirm", "Confirm the venue booking. This is the third and final step."),
};

builder.Services.AddDaprAgents(registrations: options =>
    {
        // Registering our own workflow is what gives the caller the instance ID.
        // IDaprAgentInvoker.RunAgentAsync mints its own, so a demo built on it could not tell
        // you which execution to watch.
        options.RegisterWorkflow<CrashRecoveryWorkflow>();
    })
    .WithAgent(sp =>
    {
        IChatClient chatClient = new OpenAIClient(apiKey)
            .GetChatClient("gpt-4.1-2025-04-14")
            .AsIChatClient();
        return chatClient.AsAIAgent(
            instructions: """
                You are an event planner. Call all three tools in sequence:
                1. First call step_one_search with the city name
                2. Then call step_two_compare with the result from step 1
                3. Finally call step_three_confirm with the result from step 2
                Do NOT skip any steps.
                """,
            name: "event-planner",
            tools: tools);
    })
    .WithCatalyst(
        new DiagridCatalystOptions
        {
            Registry = new RegistryMetadata
            {
                ResourceName = "agent-registry",
            },
        });

var app = builder.Build();

app.MapPost("/run", async (IDaprAgentInvoker invoker, RunRequest req, CancellationToken ct) =>
{
    var agent = invoker.GetAgent("event-planner");
    var result = await invoker.RunAgentAsync(agent, req.Prompt, cancellationToken: ct);
    return Results.Ok(new { response = result.Text });
});

// ── Crash-recovery demo ──────────────────────────────────────────────────────
// The wait budget for the blocking /crash/run. Kept comfortably above tool 2's default 30s
// so the first call is still blocked when you kill the app.
var crashWait = TimeSpan.FromSeconds(180);

// Run the agent under a workflow instance ID you choose, and block until it finishes
// POST /crash/run
// Body: { "id": "gala-42", "prompt": "Find a venue in Austin for a company gala" }
// Returns: 200 with the agent's answer, or 202 with the ID if the wait budget elapses
//
// Re-issuing this with the same ID attaches to the existing run rather than starting a
// second one. That is what the caller-owned ID buys, and it is the point of the demo.
app.MapPost("/crash/run", async (CrashRunRequest req, DaprWorkflowClient workflowClient) =>
{
    var id = req.Id;
    try
    {
        if (await workflowClient.GetWorkflowStateAsync(instanceId: id) == null)
        {
            app.Logger.LogInformation("Starting crash-recovery run {id}", id);
            await workflowClient.ScheduleNewWorkflowAsync(
                name: nameof(CrashRecoveryWorkflow),
                input: req.Prompt,
                instanceId: id);
        }
        else
        {
            app.Logger.LogInformation("Attaching to the existing run {id}", id);
        }

        // WaitForWorkflowCompletionAsync takes no timeout of its own, so the wait budget
        // arrives as a cancellation token.
        using var budget = new CancellationTokenSource(crashWait);
        var state = await workflowClient.WaitForWorkflowCompletionAsync(
            instanceId: id, getInputsAndOutputs: true, cancellation: budget.Token);

        return Results.Ok(new { id, response = state.ReadOutputAs<string>() });
    }
    catch (OperationCanceledException)
    {
        // Not a failure: the run is still going. Re-issue the same request with the same ID
        // to attach and collect the result.
        return Results.Accepted(value: new
        {
            id,
            message = $"still running as {id}, re-issue POST /crash/run with the same id to attach",
        });
    }
});

// Simulate a crash: kill this process outright, like SIGKILL. Demo only.
// POST /crash/kill
// Returns: nothing. The process is gone before a response can be written, so the caller
// sees a connection reset.
app.MapPost("/crash/kill", () =>
{
    app.Logger.LogWarning(">>> /crash/kill: killing this process to simulate a worker crash");
    // Kill(), not Environment.Exit(): Exit runs the ProcessExit handlers, which makes it a
    // controlled shutdown wearing a crash's name. Kill() is TerminateProcess on Windows and
    // SIGKILL on Unix, which is the thing this demo is simulating.
    Process.GetCurrentProcess().Kill();
});

await app.RunAsync();

record RunRequest(string Prompt);

record CrashRunRequest(string Id, string Prompt = "Find a venue in Austin for a company gala");

/// <summary>
/// Runs the event-planner agent inside a workflow the caller names.
///
/// This exists for one reason: the instance ID. IDaprAgentInvoker.RunAgentAsync mints the
/// workflow instance ID itself, so nothing outside the process can be told which execution to
/// watch. Scheduling this workflow instead lets the caller supply the ID, while
/// WorkflowContext.RunAgentAsync keeps the agent run itself durable: every LLM call and every
/// tool call is still a separate activity, so a completed activity is not replayed after a crash.
/// </summary>
public sealed class CrashRecoveryWorkflow : Workflow<string, string>
{
    public override async Task<string> RunAsync(WorkflowContext context, string prompt)
    {
        var agent = context.GetAgent("event-planner");
        var response = await context.RunAgentAsync(agent, prompt);
        return response.Text;
    }
}

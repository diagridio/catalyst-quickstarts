using System.Diagnostics;
// For JsonPropertyName on CrashRunRequest: `id` and `prompt` bind by the default
// case-insensitive match, but `kill_after_seconds` does not, so that one field is named
// explicitly rather than renamed on the wire to suit C#.
using System.Text.Json.Serialization;
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
        // Two messages, because the reader's next move differs. Un-armed, the window is theirs
        // to aim at and they have to crash the app themselves. Armed, the app does that for them
        // at a known point, so the instruction would be wrong and the ~delay would be read as
        // the wait.
        var armed = SelfKill.Seconds;
        Console.WriteLine(armed > 0
            ? $">>> TOOL 2: Comparing venues over ~{delaySeconds}s, but this process kills itself"
                + $" {armed}s into the run, as asked by kill_after_seconds. It resumes on restart."
            : $">>> TOOL 2: Comparing venues over ~{delaySeconds}s. KILL THE APP NOW to"
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
// Body: { "id": "gala-42", "prompt": "Find a venue in Austin for a company gala", "kill_after_seconds": 8 }
// Returns: 200 with the agent's answer, or 202 with the ID if the wait budget elapses
//
// Re-issuing this with the same ID attaches to the existing run rather than starting a
// second one. That is what the caller-owned ID buys, and it is the point of the demo.
//
// kill_after_seconds is optional. Send it and the app crashes itself that many seconds in,
// so the whole demo runs in two terminals with no window to aim at; leave it out and nothing
// changes, and you crash the app yourself from a second terminal with POST /crash/kill.
app.MapPost("/crash/run", async (CrashRunRequest req, DaprWorkflowClient workflowClient) =>
{
    var id = req.Id;
    if (string.IsNullOrWhiteSpace(id))
    {
        return Results.Json(new { id, result = (string?)null, message = "id is required" }, statusCode: 400);
    }

    try
    {
        // Exists, not a null check. GetWorkflowStateAsync always returns a WorkflowState:
        // for an instance that is not there it returns one whose Exists is false. Comparing
        // the result to null is therefore always false, which would skip the schedule below
        // and leave the wait asking about an instance nobody created.
        var existing = await workflowClient.GetWorkflowStateAsync(instanceId: id);
        if (!existing.Exists)
        {
            app.Logger.LogInformation("Starting crash-recovery run {id}", id);
            await workflowClient.ScheduleNewWorkflowAsync(
                name: nameof(CrashRecoveryWorkflow),
                input: req.Prompt,
                instanceId: id);

            // Armed here and nowhere else: only on the branch that actually scheduled a run,
            // and only after the schedule call returned. In the else branch below it would kill
            // the app every time the reader tried to read the answer.
            if (req.KillAfterSeconds is int killAfter and > 0)
            {
                ArmSelfKill(killAfter);
            }
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

        // The wait returns on ANY terminal state, so a failed or terminated run would
        // otherwise be reported as a 200 carrying a null result.
        if (state.RuntimeStatus != WorkflowRuntimeStatus.Completed)
        {
            app.Logger.LogError("Crash-recovery run {id} ended as {status}", id, state.RuntimeStatus);
            return Results.Json(
                new { id, result = (string?)null, message = $"run {id} ended as {state.RuntimeStatus}" },
                statusCode: 500);
        }

        return Results.Ok(new { id, result = state.ReadOutputAs<string>(), message = (string?)null });
    }
    catch (OperationCanceledException)
    {
        // Not a failure: the run is still going. Re-issue the same request with the same ID
        // to attach and collect the result.
        return Results.Accepted(value: new
        {
            id,
            result = (string?)null,
            message = $"still running as {id}, re-issue POST /crash/run with the same id to attach",
        });
    }
    catch (Exception ex)
    {
        // Every sibling crash demo returns a 500 with this shape. Without this the exception
        // escapes the endpoint and the reader gets a framework error page instead.
        app.Logger.LogError("Error running the crash-recovery run {id}: {error}", id, ex.Message);
        return Results.Json(new { id, result = (string?)null, message = ex.Message }, statusCode: 500);
    }
});

// Kill this process `delaySeconds` from now, on a background task.
//
// What lets the demo run in two terminals instead of three. /crash/run blocks for the length
// of tool 2, so the shell that starts a run cannot also stop the app, and the kill has always
// needed a terminal of its own. Arming it here removes that terminal AND the race: the crash
// lands at a known point inside the window rather than wherever the reader's reflexes put it.
static void ArmSelfKill(int delaySeconds)
{
    // Tell tool 2, so the line it prints names this delay rather than the delay it was going to
    // wait out. That second number is the one the reader used to see, and it is not the one they
    // wait: the app dies partway through it.
    SelfKill.Note(delaySeconds);

    // Discarded on purpose: this task is a fuse, not something to await. Nothing can observe
    // its completion, because its last act is to end the process.
    _ = Task.Run(async () =>
    {
        await Task.Delay(TimeSpan.FromSeconds(delaySeconds));
        // Console.WriteLine plus an explicit flush, for the reason /crash/kill gives below.
        Console.WriteLine($">>> crash: killing this process {delaySeconds}s into the run, as asked by kill_after_seconds");
        Console.Out.Flush();
        Process.GetCurrentProcess().Kill();
    });
}

// Simulate a crash: kill this process outright, like SIGKILL. Demo only.
// POST /crash/kill
// Returns: nothing. The process is gone before a response can be written, so the caller
// sees a connection reset.
app.MapPost("/crash/kill", () =>
{
    // Console.WriteLine plus an explicit flush, not app.Logger: the default console logger
    // hands the line to a background thread, and the kill below beats that thread to it, so
    // the one line telling you the kill landed is the one line that never prints.
    Console.WriteLine(">>> /crash/kill: killing this process to simulate a worker crash");
    Console.Out.Flush();
    // Kill(), not Environment.Exit(): Exit runs the ProcessExit handlers, which makes it a
    // controlled shutdown wearing a crash's name. Kill() is TerminateProcess on Windows and
    // SIGKILL on Unix, which is the thing this demo is simulating.
    Process.GetCurrentProcess().Kill();
});

await app.RunAsync();

record RunRequest(string Prompt);

// KillAfterSeconds is optional: send it and the app crashes itself that many seconds into the
// run, so the whole demo needs two terminals and no window to aim at. Leave it out and nothing
// changes, and you crash the app yourself from a second terminal with POST /crash/kill.
// Nullable rather than defaulted to 0, so "absent" and "zero" stay distinguishable.
record CrashRunRequest(
    string Id,
    string Prompt = "Find a venue in Austin for a company gala",
    [property: JsonPropertyName("kill_after_seconds")] int? KillAfterSeconds = null);

/// <summary>
/// Whether POST /crash/run has armed the app to kill itself, and how far into the run.
///
/// Read only to compose tool 2's log line, which has to name the wait the reader actually gets:
/// with a self-kill armed the tool never reaches the end of its delay, so announcing that delay
/// on its own puts a number in the log that nothing honours.
///
/// A type rather than a captured local, because ArmSelfKill is a static local function and
/// cannot capture. One armed kill takes the whole process down, so there is nothing to key by
/// run, and the fresh process after the restart starts at 0 again, which is right: nothing is
/// armed on the replay.
///
/// volatile, and an int rather than an int?: the write happens on a request thread and the read
/// on a workflow worker thread, and a single int cannot be read half-written the way a nullable
/// struct's two fields can. 0 is unambiguous as "not armed" because the arm site already rejects
/// a non-positive value.
/// </summary>
static class SelfKill
{
    static volatile int seconds;

    /// <summary>Seconds into the run at which the app kills itself, or 0 when nothing is armed.</summary>
    public static int Seconds => seconds;

    /// <summary>
    /// Record that this process will kill itself, so tool 2 can say so.
    ///
    /// Called just after the schedule, and tool 2 cannot normally log before that: the worker has
    /// to be handed the work item and run tool 1 first. If it ever did win the race the line would
    /// read as though nothing were armed, which is a stale message rather than a broken demo.
    /// </summary>
    public static void Note(int delaySeconds) => seconds = delaySeconds;
}

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

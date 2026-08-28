/*
 * Dapr Workflow Quickstart - C# Implementation
 * 
 * This application demonstrates a simple order processing workflow using Dapr Workflows.
 * The workflow includes inventory checking, payment processing, and inventory updates.
 * 
 * Workflow Steps:
 * 1. Notify user of order receipt
 * 2. Reserve inventory for the order
 * 3. Process payment for the order
 * 4. Update inventory after successful payment
 * 5. Notify user of completion
 * 
 * For more information, visit: https://docs.diagrid.io/getting-started/quickstarts/workflow/
 */


using System.Diagnostics;
using System.Text.Json;
using Dapr.Workflow;
using Microsoft.AspNetCore.Mvc;
using WorkflowApp.Activities;
using WorkflowApp.Workflows;
using WorkflowApp.Models;

var builder = WebApplication.CreateBuilder(args);

builder.Services.Configure<Microsoft.AspNetCore.Http.Json.JsonOptions>(options =>
{
    options.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;
    options.SerializerOptions.PropertyNameCaseInsensitive = true;
});

// Add Dapr workflow services
// This registers all workflow components with the Dapr workflow runtime
builder.Services.AddDaprWorkflow(options =>
{
    options.RegisterWorkflow<OrderProcessingWorkflow>();
    options.RegisterWorkflow<CrashRecoveryWorkflow>();
    options.RegisterActivity<NotifyActivity>();
    options.RegisterActivity<ReserveInventoryActivity>();
    options.RegisterActivity<ProcessPaymentActivity>();
    options.RegisterActivity<UpdateInventoryActivity>();
    options.RegisterActivity<CommitReservationActivity>();
});

var app = builder.Build();

// Health check endpoint - verifies the service is running
app.MapGet("/", () =>
{
    var healthMessage = "Health check passed. Everything is running smoothly!";
    app.Logger.LogInformation("Health check result: {Message}", healthMessage);
    return Results.Ok(new { message = healthMessage });
});

// Start new workflow - creates and schedules a new order processing workflow
// POST /workflow/start
// Body: { "name": "Car", "quantity": 2 }
// Returns: { "instance_id": "uuid" }
app.MapPost("/workflow/start", async (
    [FromBody] OrderPayload order,
    [FromServices] DaprWorkflowClient workflowClient) =>
{
    var guid = Guid.NewGuid();
    try
    {
        await workflowClient.ScheduleNewWorkflowAsync(
            name: nameof(OrderProcessingWorkflow),
            input: order,
            instanceId: guid.ToString());

        return Results.Ok(new WorkflowStartResponse(guid.ToString()));
    }
    catch (Exception ex)
    {
        app.Logger.LogError("Error starting workflow: {Error}", ex.Message);
        return Results.Problem(detail: ex.Message, statusCode: 500);
    }
});

// Get workflow status - retrieves the current state of a workflow instance
// GET /workflow/status/{id}
// Returns: WorkflowState object or 204 if not found
app.MapGet("/workflow/status/{id}", async (
    [FromRoute] string id,
    [FromServices] DaprWorkflowClient workflowClient) =>
{
    try
    {
        // GetWorkflowStateAsync always hands back a WorkflowState, never null: a missing
        // instance comes back as a wrapper whose Exists is false. Test Exists, not null.
        var state = await workflowClient.GetWorkflowStateAsync(instanceId: id);
        if (state.Exists)
        {
            app.Logger.LogInformation("Retrieved workflow status for {id}.", id);
            var result = state.ReadOutputAs<OrderResult>();
            return Results.Ok(new {state, result});
        }
        else
        {
            app.Logger.LogInformation("Workflow with id {id} does not exist", id);
            return Results.NoContent();
        }
    }
    catch (Exception ex)
    {
        app.Logger.LogError("Error occurred while getting the status of the workflow: {id}. Exception: {exception}", id, ex.InnerException);
        return Results.Problem(detail: ex.Message, statusCode: 500);
    }
});

// Terminate workflow - stops a running workflow instance
// POST /workflow/terminate/{id}
// Returns: Updated WorkflowState object
app.MapPost("/workflow/terminate/{id}", async (
    [FromRoute] string id,
    [FromServices] DaprWorkflowClient workflowClient) =>
{
    try
    {
        // Check current state first to provide accurate messaging. A missing instance is
        // a WorkflowState with Exists false, not a null, so test Exists.
        var currentState = await workflowClient.GetWorkflowStateAsync(instanceId: id);
        if (!currentState.Exists)
        {
            app.Logger.LogInformation("Workflow with id {id} does not exist", id);
            return Results.NoContent();
        }

        // If already in a terminal state, just return the current state
        var terminalStatuses = new[]
        {
            WorkflowRuntimeStatus.Completed,
            WorkflowRuntimeStatus.Failed,
            WorkflowRuntimeStatus.Terminated
        };

        if (terminalStatuses.Contains(currentState.RuntimeStatus))
        {
            app.Logger.LogInformation("Workflow with id {id} is already in terminal state {status}", id, currentState.RuntimeStatus);
            return Results.Ok(currentState);
        }

        // Terminate the workflow
        await workflowClient.TerminateWorkflowAsync(id, "dapr");
        app.Logger.LogInformation("Terminated workflow with id {id}.", id);

        // Return the updated state
        var updatedState = await workflowClient.GetWorkflowStateAsync(instanceId: id);
        return Results.Ok(updatedState);
    }
    catch (Exception ex)
    {
        app.Logger.LogError("Error occurred while terminating the workflow: {id}. Exception: {exception}", id, ex.InnerException);
        return Results.Problem(detail: ex.Message, statusCode: 500);
    }
});

// ── Crash-recovery demo ──────────────────────────────────────────────────────
// The wait budget for the blocking /crash/run. Kept comfortably above the slow
// activity's default 30s so the first call is still blocked when you kill the app.
// Overridable through CRASH_WAIT_SECONDS, which is how the e2e suite exercises the
// 202 branch without waiting two minutes for it.
var crashWait = TimeSpan.FromSeconds(
    int.TryParse(Environment.GetEnvironmentVariable("CRASH_WAIT_SECONDS"), out var waitSeconds)
        ? waitSeconds
        : 120);

// Run the crash-recovery workflow under an instance ID the caller owns
// POST /crash/run
// Body: { "id": "trip-42", "reference": "ABC123", "kill_after_seconds": 8 }
// Returns: 200 with the confirmation, or 202 with the ID if the wait budget elapses
//
// Re-issuing this with the same ID attaches to the existing run rather than reserving
// a second time. That is what the caller-owned ID buys, and it is the point of the demo.
//
// kill_after_seconds is optional. Send it and the app crashes itself that many seconds in,
// so the whole demo runs in two terminals with no window to aim at; leave it out and nothing
// changes, and you crash the app yourself from a second terminal with POST /crash/kill.
app.MapPost("/crash/run", async (
    [FromBody] CrashRunRequest request,
    [FromServices] DaprWorkflowClient workflowClient) =>
{
    var id = request.Id;
    if (string.IsNullOrWhiteSpace(id))
    {
        return Results.Json(new CrashRunResponse(id, null, "id is required"), statusCode: 400);
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
            app.Logger.LogInformation(
                "Starting crash-recovery workflow {id} for reservation {reference}", id, request.Reference);
            await workflowClient.ScheduleNewWorkflowAsync(
                name: nameof(CrashRecoveryWorkflow),
                input: request.Reference,
                instanceId: id);

            // Armed here and nowhere else: only on the branch that actually scheduled a run,
            // and only after the schedule call returned. In the else branch below it would kill
            // the app every time the reader tried to read the answer.
            if (request.KillAfterSeconds is int killAfter and > 0)
            {
                ArmSelfKill(killAfter);
            }
        }
        else
        {
            app.Logger.LogInformation("Attaching to existing crash-recovery workflow {id}", id);
        }

        // WaitForWorkflowCompletionAsync takes no timeout of its own, so the wait budget
        // arrives as a cancellation token.
        using var budget = new CancellationTokenSource(crashWait);
        var state = await workflowClient.WaitForWorkflowCompletionAsync(
            instanceId: id, getInputsAndOutputs: true, cancellation: budget.Token);

        // The wait returns on ANY terminal state, so a failed or terminated instance would
        // otherwise be reported as a 200 carrying a null result.
        if (state.RuntimeStatus != WorkflowRuntimeStatus.Completed)
        {
            app.Logger.LogError("Crash-recovery workflow {id} ended as {status}", id, state.RuntimeStatus);
            return Results.Json(
                new CrashRunResponse(id, null, $"workflow {id} ended as {state.RuntimeStatus}"),
                statusCode: 500);
        }

        return Results.Ok(new CrashRunResponse(id, state.ReadOutputAs<string>(), null));
    }
    catch (OperationCanceledException)
    {
        // Not a failure: the run is still going. Re-issue the same request with the same
        // ID to attach and collect the result.
        return Results.Accepted(value: new CrashRunResponse(id, null,
            $"still running as {id}, re-issue POST /crash/run with the same id to attach"));
    }
    catch (Exception ex)
    {
        app.Logger.LogError("Error running the crash-recovery workflow {id}: {error}", id, ex.Message);
        return Results.Json(new CrashRunResponse(id, null, ex.Message), statusCode: 500);
    }
});

// Kill this process `delaySeconds` from now, on a background task.
//
// What lets the demo run in two terminals instead of three. /crash/run blocks for the length
// of the slow activity, so the shell that starts a run cannot also stop the app, and the kill
// has always needed a terminal of its own. Arming it here removes that terminal AND the race:
// the crash lands at a known point inside the window rather than wherever the reader's
// reflexes put it.
//
// A local function declared before its call sites would be tidier, but top-level statements
// run in order and MapPost's lambda only runs later, so declaring it here is fine and keeps it
// beside the /crash/kill it mirrors.
static void ArmSelfKill(int delaySeconds)
{
    // Tell the slow activity, so the line it prints names this delay rather than the delay it
    // was going to wait out. That second number is the one the reader used to see, and it is
    // not the one they wait: the app dies partway through it.
    CommitReservationActivity.NoteSelfKill(delaySeconds);

    // Discarded on purpose: this task is a fuse, not something to await. Nothing can observe
    // its completion, because its last act is to end the process.
    _ = Task.Run(async () =>
    {
        await Task.Delay(TimeSpan.FromSeconds(delaySeconds));
        // Console.WriteLine plus an explicit flush, for the reason /crash/kill gives below:
        // the default console logger hands the line to a background thread and the kill beats
        // it, so the one line explaining the death is the one line that never prints.
        Console.WriteLine($">>> crash: killing this process {delaySeconds}s into the run, as asked by kill_after_seconds");
        Console.Out.Flush();
        // Kill(), matching /crash/kill: Environment.Exit runs the ProcessExit handlers, which
        // makes it a controlled shutdown wearing a crash's name.
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

app.Run();


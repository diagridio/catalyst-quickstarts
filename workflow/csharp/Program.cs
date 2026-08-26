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
        var state = await workflowClient.GetWorkflowStateAsync(instanceId: id);
        if (state != null)
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
        // Check current state first to provide accurate messaging
        var currentState = await workflowClient.GetWorkflowStateAsync(instanceId: id);
        if (currentState == null)
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
var crashWait = TimeSpan.FromSeconds(120);

// Run the crash-recovery workflow under an instance ID the caller owns
// POST /crash/run
// Body: { "id": "trip-42", "reference": "ABC123" }
// Returns: 200 with the confirmation, or 202 with the ID if the wait budget elapses
//
// Re-issuing this with the same ID attaches to the existing run rather than reserving
// a second time. That is what the caller-owned ID buys, and it is the point of the demo.
app.MapPost("/crash/run", async (
    [FromBody] CrashRunRequest request,
    [FromServices] DaprWorkflowClient workflowClient) =>
{
    var id = request.Id;
    try
    {
        if (await workflowClient.GetWorkflowStateAsync(instanceId: id) == null)
        {
            app.Logger.LogInformation(
                "Starting crash-recovery workflow {id} for reservation {reference}", id, request.Reference);
            await workflowClient.ScheduleNewWorkflowAsync(
                name: nameof(CrashRecoveryWorkflow),
                input: request.Reference,
                instanceId: id);
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
        return Results.Problem(detail: ex.Message, statusCode: 500);
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

app.Run();


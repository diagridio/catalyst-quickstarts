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
 * For more information, visit: https://docs.diagrid.io/catalyst/quickstart/workflow
 */


using System.Text.Json;
using Dapr.Workflow;
using Microsoft.AspNetCore.Mvc;
using WorkflowApp.Activities;
using WorkflowApp.Workflows;
using WorkflowApp.Models;

var builder = WebApplication.CreateBuilder(args);

// Configure JSON serialization for camelCase
builder.Services.Configure<Microsoft.AspNetCore.Http.Json.JsonOptions>(options =>
{
    options.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;
    options.SerializerOptions.PropertyNameCaseInsensitive = true;
});

// Configure Dapr client with JSON serialization options
builder.Services.AddDaprClient(daprBuilder =>
{
    daprBuilder.UseJsonSerializationOptions(new JsonSerializerOptions
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        PropertyNameCaseInsensitive = true
    });
});

// Add Dapr workflow services
// This registers all workflow components with the Dapr workflow runtime
builder.Services.AddDaprWorkflow(options =>
{
    options.RegisterWorkflow<OrderProcessingWorkflow>();
    options.RegisterActivity<NotifyActivity>();
    options.RegisterActivity<ReserveInventoryActivity>();
    options.RegisterActivity<ProcessPaymentActivity>();
    options.RegisterActivity<UpdateInventoryActivity>();
});

var app = builder.Build();
var workflowClient = app.Services.GetRequiredService<DaprWorkflowClient>();

// Dapr will send serialized event object vs. being raw CloudEvent
app.UseCloudEvents();

#region Workflow API

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
app.MapPost("/workflow/start", async (OrderPayload order) =>
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
app.MapGet("/workflow/status/{id}", async ([FromRoute] string id) =>
{
    try
    {
        WorkflowState state = await workflowClient.GetWorkflowStateAsync(instanceId: id);
        if (state != null)
        {
            app.Logger.LogInformation("Retrieved workflow status for {id}.", id);
            return Results.Ok(state);
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
app.MapPost("/workflow/terminate/{id}", async ([FromRoute] string id) =>
{
    try
    {
        // Check current state first to provide accurate messaging
        WorkflowState currentState = await workflowClient.GetWorkflowStateAsync(instanceId: id);
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
        WorkflowState updatedState = await workflowClient.GetWorkflowStateAsync(instanceId: id);
        return Results.Ok(updatedState);
    }
    catch (Exception ex)
    {
        app.Logger.LogError("Error occurred while terminating the workflow: {id}. Exception: {exception}", id, ex.InnerException);
        return Results.Problem(detail: ex.Message, statusCode: 500);
    }
});

#endregion

app.Run();


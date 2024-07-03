using System.Text.Json;
using System.Text.Json.Serialization;
using Dapr.Client;
using Dapr.Workflow;
using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.AspNetCore.Mvc;
using WorkflowConsoleApp.Activities;
using WorkflowConsoleApp.Models;
using WorkflowConsoleApp.Workflows;

var builder = WebApplication.CreateBuilder(args);

// Add Dapr workflow services
builder.Services.AddDaprWorkflow(options =>
{
    options.RegisterWorkflow<OrderProcessingWorkflow>();
    options.RegisterActivity<NotifyActivity>();
    options.RegisterActivity<ReserveInventoryActivity>();
    options.RegisterActivity<ProcessPaymentActivity>();
    options.RegisterActivity<UpdateInventoryActivity>();
});

var app = builder.Build();

var client = new DaprClientBuilder().Build();
var workflowClient = app.Services.GetRequiredService<DaprWorkflowClient>();

// Dapr will send serialized event object vs. being raw CloudEvent
app.UseCloudEvents();

#region Workflow API

// Start new workflow
app.MapPost("/workflow/start", async (OrderPayload order) =>
{
    var guid = Guid.NewGuid();
    try
    {
        await workflowClient.ScheduleNewWorkflowAsync(
            name: nameof(OrderProcessingWorkflow),
            input: order,
            instanceId: guid.ToString());

        return Results.Ok(new { WorkflowId = guid });
    }
    catch (Exception ex)
    {
        return Results.Problem(ex.Message);
    }
});

// Get workflow status
app.MapGet("/workflow/status/{id}", async ([FromRoute] string id) =>
{
    try
    {
        WorkflowState state = await workflowClient.GetWorkflowStateAsync(instanceId: id);
        app.Logger.LogInformation("STATE: {state}", state.ToString());
        if (state != null)
        {
            app.Logger.LogInformation("Get Workflow status successful. Workflow Runtime Status is: {status} ", state.RuntimeStatus);
            return Results.Ok(state);
        }
        else
        {
            app.Logger.LogInformation("Workflow with id {id} does not exist", id);
            return Results.StatusCode(204);
        }
    }
    catch (Exception ex)
    {
        app.Logger.LogError("Error occurred while getting the status of the workflow: {id}. Exception: {exception}", id, ex.InnerException);
        return Results.StatusCode(500);
    }
});

// Get completed workflow output
app.MapGet("/workflow/output/{id}", async ([FromRoute] string id) =>
{
    try
    {
        WorkflowState state = await workflowClient.GetWorkflowStateAsync(id);
        if (state != null)
        {
            app.Logger.LogInformation("Retrieved workflow state for {id}.", id);
            var output = state.ReadOutputAs<OrderResult>();
            app.Logger.LogInformation("Workflow output is: {output} ", output);
            return Results.Ok(output.Message);
        }
        else
        {
            app.Logger.LogInformation("Workflow with id {id} does not exist", id);
            return Results.StatusCode(204);
        }
    }
    catch (Exception ex)
    {
        app.Logger.LogError("Error occurred while getting the output of the workflow: {id}. Exception: {exception}", id, ex.InnerException);
        return Results.StatusCode(500);
    }
});

#endregion

app.Run();

public record Order(int OrderId);
public record OrderPayload(string Name, int Quantity);
public record OrderResult(bool Processed, string Message);


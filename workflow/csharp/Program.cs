using Dapr.Workflow;
using Microsoft.AspNetCore.Mvc;
using WorkflowApp.Activities;
using WorkflowApp.Workflows;

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
        if (state != null)
        {
            app.Logger.LogInformation("Retrieved workflow status for {id}.", id);
            app.Logger.LogInformation("Workflow Runtime Status is: {status} ", state.RuntimeStatus);
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

// Terminate workflow
app.MapPost("/workflow/terminate/{id}", async ([FromRoute] string id) =>
{
    try
    {
        await workflowClient.TerminateWorkflowAsync(id, "dapr");
        WorkflowState state = await workflowClient.GetWorkflowStateAsync(instanceId: id);
        if (state != null)
        {
            app.Logger.LogInformation("Terminated workflow with id {id}.", id);
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
        app.Logger.LogError("Error occurred while terminating the workflow: {id}. Exception: {exception}", id, ex.InnerException);
        return Results.StatusCode(500);
    }
});

#endregion

app.Run();

public record Order(int OrderId);
public record OrderPayload(string Name, int Quantity);
public record OrderResult(bool Processed, string Message);


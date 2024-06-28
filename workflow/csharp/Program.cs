using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Dapr.Client;
using Microsoft.AspNetCore.Mvc;
using Dapr.Workflow;
using BasicWorkflowSamples;

var builder = WebApplication.CreateBuilder(args);

// Add workflow 
builder.Services.AddDaprWorkflow(options =>
{
    options.RegisterWorkflow<HelloWorldWorkflow>();
    options.RegisterActivity<CreateGreetingActivity>();
});

var app = builder.Build();

// Catalyst: Ensure environment variable DAPR_GRPC_ENDPOINT and DAPR_API_TOKEN is set before this point
var client = new DaprClientBuilder().Build();
var workflowClient = app.Services.GetRequiredService<DaprWorkflowClient>();

var DaprApiToken = Environment.GetEnvironmentVariable("DAPR_API_TOKEN") ?? "";
var WorkflowStateStore = Environment.GetEnvironmentVariable("WORKFLOW_STORE") ?? "kvstore";

// Dapr will send serialized event object vs. being raw CloudEvent
app.UseCloudEvents();
#region Workflow API

// Start new workflow
app.MapPost("/workflow/start", async (Greeting greeting) =>
{
    // Store state in managed diagrid state store 
    var guid = Guid.NewGuid();
    try
    {
        await workflowClient.ScheduleNewWorkflowAsync(
            name: nameof(HelloWorldWorkflow),
            input: greeting.Input,
            instanceId: guid.ToString());
        
        app.Logger.LogInformation("Started a new HelloWorld Workflow with id {guid} and input {input}", guid, greeting.Input);
        return Results.Ok(guid);
    }
    catch (Exception ex)
    {
        app.Logger.LogError("Error occurred while starting workflow: {guid}. Exception: {exception}", guid, ex.InnerException);
        return Results.StatusCode(500);
    }
});

// Get workflow status
app.MapGet("/workflow/status/{id}", async ([FromRoute] string id) =>
{
    try
    {
        WorkflowState state = await workflowClient.GetWorkflowStateAsync(
            instanceId: id);
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
        WorkflowState state = await workflowClient.GetWorkflowStateAsync(
            instanceId: id);
        app.Logger.LogInformation("STATE: {state}", state.ToString());
        var output = state.ReadOutputAs<String>();
         if (state != null)
        {
            app.Logger.LogInformation("Get Workflow output successful. Workflow Output is: {output} ", output);
            return Results.Ok(output);
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

public record Order([property: JsonPropertyName("orderId")] int OrderId);
public record Greeting([property: JsonPropertyName("input")] string Input);

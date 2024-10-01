using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Dapr.Client;
using Microsoft.AspNetCore.Mvc;

var builder = WebApplication.CreateBuilder(args);

var app = builder.Build();

var client = new DaprClientBuilder().Build();

var stateStoreName = Environment.GetEnvironmentVariable("STATESTORE_NAME") ?? "kvstore";

// Health check endpoint
app.MapGet("/", () => 
{
    var healthMessage = "Health check passed. Everything is running smoothly! 🚀";
    app.Logger.LogInformation("Health check result: {Message}", healthMessage);
    return Results.Ok(healthMessage);
});

// Save state 
app.MapPost("/order", async (Order order) =>
{
    try
    {
        await client.SaveStateAsync(stateStoreName, order.OrderId.ToString(), order);
        app.Logger.LogInformation("Save state item successful. Order saved: {order}", order.OrderId);
        return Results.StatusCode(200);
    }
    catch (Exception ex)
    {
        app.Logger.LogError("Error occurred while saving state item: {orderId}. Exception: {exception}", order.OrderId, ex.InnerException);
        return Results.StatusCode(500);
    }
});


//Retrieve state
app.MapGet("/order/{orderId}", async ([FromRoute] int orderId) =>
{
    // Store state in managed diagrid state store 
    try
    {
        var kv = await client.GetStateAsync<Order>(stateStoreName, orderId.ToString());
        if (kv != null)
        {
            app.Logger.LogInformation("Get state item successful. Order retrieved: {order}", orderId.ToString());
            return Results.Ok(kv);
        }
        else
        {
            app.Logger.LogInformation("State item with key {key} does not exist", orderId.ToString());
            return Results.StatusCode(204);
        }
    }
    catch (Exception ex)
    {
        app.Logger.LogError("Error occurred while retrieving state item: {order}. Exception: {exception}", orderId.ToString(), ex.InnerException);
        return Results.StatusCode(500);
    }

});

// Delete state 
app.MapDelete("/order/{orderId}", async ([FromRoute] int orderId) =>
{
    // Store state in managed diagrid state store 
    try
    {
        await client.DeleteStateAsync(stateStoreName, orderId.ToString());
        app.Logger.LogInformation("Delete state item successful. Order deleted: {order}", orderId.ToString());
        return Results.StatusCode(200);
    }
    catch (Exception ex)
    {
        app.Logger.LogError("Error occurred while deleting state item: {order}. Exception: {exception}", orderId.ToString(), ex.InnerException);
        return Results.StatusCode(500);
    }
});

app.Run();

public record Order([property: JsonPropertyName("orderId")] int OrderId);
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Dapr.Client;
using Microsoft.AspNetCore.Mvc;

var builder = WebApplication.CreateBuilder(args);

var app = builder.Build();

var client = new DaprClientBuilder().Build();

var stateStoreName = Environment.GetEnvironmentVariable("STATESTORE_NAME") ?? "statestore";

// Health check endpoint
app.MapGet("/", () =>
{
    var healthMessage = "Health check passed. Everything is running smoothly!";
    app.Logger.LogInformation("Health check result: {Message}", healthMessage);
    return Results.Ok(new { status = "healthy", message = healthMessage });
});

// Save state 
app.MapPost("/order", async (Order order) =>
{
    try
    {
        await client.SaveStateAsync(stateStoreName, order.OrderId.ToString(), order);
        app.Logger.LogInformation("Save state item successful. Order saved: {order}", order.OrderId);
        return Results.Created($"/order/{order.OrderId}", new { id = order.OrderId, message = "Order created successfully" });
    }
    catch (Exception ex)
    {
        app.Logger.LogError("Error occurred while saving state item: {orderId}. Exception: {exception}", order.OrderId, ex.InnerException);
        return Results.Json(new { error = new { code = "INTERNAL_ERROR", message = "An internal server error occurred" } }, statusCode: 500);
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
            return Results.Ok(new { data = kv });
        }
        else
        {
            app.Logger.LogInformation("State item with key {key} does not exist", orderId.ToString());
            return Results.NotFound(new { error = new { code = "ORDER_NOT_FOUND", message = $"Order with id '{orderId}' not found" } });
        }
    }
    catch (Exception ex)
    {
        app.Logger.LogError("Error occurred while retrieving state item: {order}. Exception: {exception}", orderId.ToString(), ex.InnerException);
        return Results.Json(new { error = new { code = "INTERNAL_ERROR", message = "An internal server error occurred" } }, statusCode: 500);
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
        return Results.NoContent();
    }
    catch (Exception ex)
    {
        app.Logger.LogError("Error occurred while deleting state item: {order}. Exception: {exception}", orderId.ToString(), ex.InnerException);
        return Results.Json(new { error = new { code = "INTERNAL_ERROR", message = "An internal server error occurred" } }, statusCode: 500);
    }
});

app.Run();

public record Order([property: JsonPropertyName("orderId")] int OrderId);
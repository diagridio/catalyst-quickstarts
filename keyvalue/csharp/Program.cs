using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Dapr.Client;
using Microsoft.AspNetCore.Mvc;

var builder = WebApplication.CreateBuilder(args);

var app = builder.Build();

var client = new DaprClientBuilder().Build();

var KVStoreName = Environment.GetEnvironmentVariable("KVSTORE_NAME") ?? "kvstore";

// Save state 
app.MapPost("/kv/orders", async (Order order) =>
{
    // Store state in managed diagrid state store 
    try
    {
        await client.SaveStateAsync(KVStoreName, order.OrderId.ToString(), order);
        app.Logger.LogInformation("Save KV Successful.  Order saved: {order}", order.OrderId);
        return Results.StatusCode(200);
    }
    catch (Exception ex)
    {
        app.Logger.LogError("Error occurred while saving order: {orderId}. Exception: {exception}", order.OrderId, ex.InnerException);
        return Results.StatusCode(500);
    }
});


//Retrieve state
app.MapGet("/kv/orders/{orderId}", async ([FromRoute] int orderId) =>
{
    // Store state in managed diagrid state store 
    try
    {
        var kv = await client.GetStateAsync<Order>(KVStoreName, orderId.ToString());
        if (kv != null)
        {
            app.Logger.LogInformation("Get KV Successful. Order retrieved: {order}", orderId.ToString());
            return Results.Ok(kv);
        }
        else
        {
            app.Logger.LogInformation("Key {key} does not exist", orderId.ToString());
            return Results.StatusCode(204);
        }
    }
    catch (Exception ex)
    {
        app.Logger.LogError("Error occurred while retrieving order: {order}. Exception: {exception}", orderId.ToString(), ex.InnerException);
        return Results.StatusCode(500);
    }

});

// Delete state 
app.MapDelete("/kv/orders/{orderId}", async ([FromRoute] int orderId) =>
{
    // Store state in managed diagrid state store 
    try
    {
        await client.DeleteStateAsync(KVStoreName, orderId.ToString());
        app.Logger.LogInformation("Delete KV Successful. Order deleted: {order}", orderId.ToString());
        return Results.StatusCode(200);
    }
    catch (Exception ex)
    {
        app.Logger.LogError("Error occurred while deleting order: {order}. Exception: {exception}", orderId.ToString(), ex.InnerException);
        return Results.StatusCode(500);
    }
});

app.Run();

public record Order([property: JsonPropertyName("orderId")] int OrderId);
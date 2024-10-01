using System.Text.Json.Serialization;
using Dapr.Client;

var builder = WebApplication.CreateBuilder(args);

var app = builder.Build();

var client = new DaprClientBuilder().Build();

var PubSubName = Environment.GetEnvironmentVariable("PUBSUB_NAME") ?? "pubsub";

#region Publish API 

// Health check endpoint
app.MapGet("/", () => 
{
    var healthMessage = "Health check passed. Everything is running smoothly! 🚀";
    app.Logger.LogInformation("Health check result: {Message}", healthMessage);
    return Results.Ok(healthMessage);
});

// Publish messages 
app.MapPost("/order", async (Order order) =>
{
    // Publish order to Diagrid pubsub, topic: orders 
    try
    {
        await client.PublishEventAsync(PubSubName, "orders", order);
        app.Logger.LogInformation("Publish Successful. Order published: {orderId}", order.OrderId);
        return Results.StatusCode(200);

    }
    catch (Exception ex)
    {
        app.Logger.LogError("Error occurred while publishing order: {orderId}. Exception: {exception}", order.OrderId, ex.InnerException);
        return Results.StatusCode(500);
    }
});

#endregion

app.Run();

public record Order([property: JsonPropertyName("orderId")] int OrderId);


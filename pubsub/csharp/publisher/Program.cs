using System.Text.Json.Serialization;
using Dapr.Client;

var builder = WebApplication.CreateBuilder(args);

var app = builder.Build();

var client = new DaprClientBuilder().Build();

var PubSubName = Environment.GetEnvironmentVariable("PUBSUB_NAME") ?? "pubsub";

#region Publish API 

// Publish messages 
app.MapPost("/pubsub/orders", async (Order order) =>
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


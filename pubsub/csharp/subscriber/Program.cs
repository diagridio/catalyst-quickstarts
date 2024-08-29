using System.Text.Json.Serialization;
using Dapr.Client;

var builder = WebApplication.CreateBuilder(args);

var app = builder.Build();

var client = new DaprClientBuilder().Build();

// Dapr will send serialized event object vs. being raw CloudEvent
app.UseCloudEvents();

#region Subscription Target Endpoint

// Subscribe to messages 
app.MapPost("/neworder", (Order order) =>
{
    app.Logger.LogInformation("Order received: {orderId}", order.OrderId);
    return Results.Ok(order);
});

#endregion

app.Run();

public record Order([property: JsonPropertyName("orderId")] int OrderId);
using System.Text.Json.Serialization;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

var logger = app.Logger;

app.MapPost("/neworder", (Order order) =>
{
    logger.LogInformation("Invocation received with data: {OrderId}", order.OrderId);
    return Results.Ok(new { message = "Order received successfully", orderId = order.OrderId });
});

// Health check endpoint
app.MapGet("/", () =>
{
    var healthMessage = "Health check passed. Everything is running smoothly!";
    app.Logger.LogInformation("Health check result: {Message}", healthMessage);
    return Results.Ok(new { status = "healthy", message = healthMessage });
});

app.Run();

public record Order([property: JsonPropertyName("orderId")] int OrderId);


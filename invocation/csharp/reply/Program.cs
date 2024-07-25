using System.Text.Json.Serialization;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

var logger = app.Logger;

app.MapPost("/invoke/neworders", (Order order) =>
{
    logger.LogInformation("Request received: {OrderId}", order.OrderId);
    return Results.Ok(order);
});

app.Run();

public record Order([property: JsonPropertyName("orderId")] int OrderId);


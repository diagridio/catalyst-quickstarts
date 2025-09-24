using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Dapr.Client;
using Microsoft.AspNetCore.Mvc;

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

var client = new DaprClientBuilder().Build();

var DaprApiToken = Environment.GetEnvironmentVariable("DAPR_API_TOKEN") ?? "";
var InvokeAppId = Environment.GetEnvironmentVariable("INVOKE_APPID") ?? "server";

// Health check endpoint
app.MapGet("/", () =>
{
    var healthMessage = "Health check passed. Everything is running smoothly!";
    app.Logger.LogInformation("Health check result: {Message}", healthMessage);
    return Results.Ok(new { status = "healthy", message = healthMessage });
});

app.MapPost("/order", async (Order order) =>
{
    try
    {
        var httpClient = DaprClient.CreateInvokeHttpClient(InvokeAppId);
        httpClient.DefaultRequestHeaders.Add("dapr-api-token", DaprApiToken);
        var orderJson = JsonSerializer.Serialize(order);
        var content = new StringContent(orderJson, Encoding.UTF8, "application/json");

        var response = await httpClient.PostAsync("/neworder", content);

        if (response.IsSuccessStatusCode)
        {
            app.Logger.LogInformation("Invocation successful with status code {statusCode}", response.StatusCode);
            return Results.Ok(new { message = "Invocation successful", orderId = order.OrderId, targetApp = InvokeAppId });
        }
        else
        {
            app.Logger.LogError("Invocation unsuccessful with status code {statusCode}", response.StatusCode);
            return Results.Json(new { error = new { code = "INVOCATION_ERROR", message = "Failed to invoke service" } }, statusCode: 500);
        }
    }
    catch (Exception ex)
    {
        app.Logger.LogError("Error occurred while invoking {appID}: {exception}", InvokeAppId, ex.InnerException);
        return Results.Json(new { error = new { code = "INVOCATION_ERROR", message = "Failed to invoke service" } }, statusCode: 500);
    }
});

app.Run();

public record Order([property: JsonPropertyName("orderId")] int OrderId);

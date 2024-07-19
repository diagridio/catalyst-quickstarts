using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Dapr.Client;
using Microsoft.AspNetCore.Mvc;

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

var client = new DaprClientBuilder().Build();

var DaprApiToken = Environment.GetEnvironmentVariable("DAPR_API_TOKEN") ?? "";
var InvokeTargetAppID = Environment.GetEnvironmentVariable("INVOKE_APPID") ?? "target";

// Invoke another service
app.MapPost("/invoke/orders", async (Order order) =>
{
    try
    {
        // Create invoke client for the "target" App ID
        var httpClient = DaprClient.CreateInvokeHttpClient(InvokeTargetAppID);
        httpClient.DefaultRequestHeaders.Add("dapr-api-token", DaprApiToken);
        var orderJson = JsonSerializer.Serialize(order);
        var content = new StringContent(orderJson, Encoding.UTF8, "application/json");

        var response = await httpClient.PostAsync("/invoke/neworders", content);

        if (response.IsSuccessStatusCode)
        {
            app.Logger.LogInformation("Invocation successful with status code {statusCode}", response.StatusCode);
            return Results.StatusCode(200);
        }
        else
        {
            app.Logger.LogError("Invocation unsuccessful with status code {statusCode}", response.StatusCode);
            return Results.StatusCode(500);
        }
    }
    catch (Exception ex)
    {
        app.Logger.LogError("Error occurred while invoking App ID: {exception}", ex.InnerException);
        return Results.StatusCode(500);
    }
});

app.MapPost("/invoke/neworders", (Order order) =>
{
    app.Logger.LogInformation("Request received : {order}", order);
    return Results.Ok(order);
});

app.Run();

public record Order([property: JsonPropertyName("orderId")] int OrderId);
public record Greeting([property: JsonPropertyName("input")] string Input);




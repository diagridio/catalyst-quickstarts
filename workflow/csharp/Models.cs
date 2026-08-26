using System.Text.Json.Serialization;

namespace WorkflowApp.Models
{
    public record OrderPayload(
        [property: JsonPropertyName("name")] string Name,
        [property: JsonPropertyName("quantity")] int Quantity);

    public record InventoryRequest(
        [property: JsonPropertyName("requestId")] string RequestId,
        [property: JsonPropertyName("itemName")] string ItemName,
        [property: JsonPropertyName("quantity")] int Quantity);

    public record InventoryItem(
        [property: JsonPropertyName("name")] string Name,
        [property: JsonPropertyName("quantity")] int Quantity);

    public record InventoryResult(
        [property: JsonPropertyName("success")] bool Success,
        [property: JsonPropertyName("item")] InventoryItem? Item = null);

    public record PaymentRequest(
        [property: JsonPropertyName("requestId")] string RequestId,
        [property: JsonPropertyName("itemName")] string ItemName,
        [property: JsonPropertyName("quantity")] int Quantity);

    public record OrderResult(
        [property: JsonPropertyName("processed")] bool Processed,
        [property: JsonPropertyName("message")] string Message);

    public record Notification(
        [property: JsonPropertyName("message")] string Message);

    public record WorkflowStartResponse(
        [property: JsonPropertyName("instanceId")] string InstanceId);

    // Request body of POST /crash/run: the instance ID the caller owns, and the reference
    // the confirmation code is derived from.
    public record CrashRunRequest(
        [property: JsonPropertyName("id")] string Id,
        [property: JsonPropertyName("reference")] string Reference = "ABC123");

    // Response body of POST /crash/run, and the one shape every crash demo in this repo
    // returns. All three fields are always present: a 200 carries Result, while a 202, a 400
    // and a 500 carry Message instead.
    public record CrashRunResponse(
        [property: JsonPropertyName("id")] string Id,
        [property: JsonPropertyName("result")] string? Result,
        [property: JsonPropertyName("message")] string? Message);
}

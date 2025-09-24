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
}
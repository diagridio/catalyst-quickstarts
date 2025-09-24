using System.Text.Json.Serialization;

namespace WorkflowApp.Models
{
    public record OrderPayload(
        [property: JsonPropertyName("name")] string Name,
        [property: JsonPropertyName("quantity")] int Quantity);

    public record InventoryRequest(string RequestId, string ItemName, int Quantity);
    public record InventoryItem(string Name, int Quantity);
    public record InventoryResult(bool Success, InventoryItem? Item = null);
    public record PaymentRequest(string RequestId, string ItemName, int Quantity);
    public record OrderResult(bool Processed, string Message);
    public record Notification(string Message);

    public record WorkflowStartResponse(
        [property: JsonPropertyName("instance_id")] string InstanceId);
}



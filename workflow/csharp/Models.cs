namespace WorkflowApp.Models
{
    public record OrderPayload(string Name, int Quantity);
    public record InventoryRequest(string RequestId, string ItemName, int Quantity);
    public record InventoryResult(bool Success);
    public record PaymentRequest(string RequestId, string ItemBeingPurchased, int Amount);
    public record OrderResult(bool Processed, string Message);
    public record Notification(string Message);
}



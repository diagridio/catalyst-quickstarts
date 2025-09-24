package io.dapr.quickstarts.workflows.models;

public class PaymentRequest {
  private String requestId;
  private String itemName;
  private int quantity;

  public String getRequestId() {
    return requestId;
  }

  public void setRequestId(String requestId) {
    this.requestId = requestId;
  }

  public String getItemName() {
    return itemName;
  }

  public void setItemName(String itemName) {
    this.itemName = itemName;
  }

  public String getItemBeingPurchased() {
    return itemName;
  }

  public void setItemBeingPurchased(String itemBeingPurchased) {
    this.itemName = itemBeingPurchased;
  }

  public int getQuantity() {
    return quantity;
  }

  public void setQuantity(int quantity) {
    this.quantity = quantity;
  }

  @Override
  public String toString() {
    return "PaymentRequest [requestId=" + requestId + ", itemName=" + itemName
        + ", quantity=" + quantity + "]";
  }
}

package io.dapr.quickstarts.workflows.models;

public class PaymentRequest {
  private String requestId;
  private int quantity;
  private String itemBeingPurchased;

  public String getRequestId() {
    return requestId;
  }

  public void setRequestId(String requestId) {
    this.requestId = requestId;
  }

  public int getQuantity() {
    return quantity;
  }

  public void setQuantity(int quantity) {
    this.quantity = quantity;
  }

  public String getItemBeingPurchased() {
    return itemBeingPurchased;
  }

  public void setItemBeingPurchased(String itemBeingPurchased) {
    this.itemBeingPurchased = itemBeingPurchased;
  }

  @Override
  public String toString() {
    return "PaymentRequest [requestId=" + requestId + ", itemBeingPurchased=" + itemBeingPurchased
        + ", quantity=" + quantity + "]";
  }
}

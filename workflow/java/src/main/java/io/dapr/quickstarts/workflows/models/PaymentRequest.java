package io.dapr.quickstarts.workflows.models;

import com.fasterxml.jackson.annotation.JsonProperty;

public class PaymentRequest {
  @JsonProperty("requestId")
  private String requestId;
  @JsonProperty("itemName")
  private String itemName;
  @JsonProperty("quantity")
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

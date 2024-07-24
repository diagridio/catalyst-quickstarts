package io.dapr.quickstarts.workflows.models;

import com.fasterxml.jackson.annotation.JsonProperty;

public class OrderPayload {

  @JsonProperty("Name")
  private String itemName;
  
  @JsonProperty("Quantity")
  private int quantity;

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
    return "OrderPayload [itemName=" + itemName + ", quantity=" + quantity + "]";
  }

}

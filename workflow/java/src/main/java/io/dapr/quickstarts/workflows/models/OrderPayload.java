package io.dapr.quickstarts.workflows.models;

import com.fasterxml.jackson.annotation.JsonProperty;

public class OrderPayload {

  @JsonProperty("name")
  private String name;
  
  @JsonProperty("quantity")
  private int quantity;

  public String getName() {
    return name;
  }

  public void setName(String name) {
    this.name = name;
  }

  public int getQuantity() {
    return quantity;
  }

  public void setQuantity(int quantity) {
    this.quantity = quantity;
  }

  @Override
  public String toString() {
    return "OrderPayload [name=" + name + ", quantity=" + quantity + "]";
  }

}

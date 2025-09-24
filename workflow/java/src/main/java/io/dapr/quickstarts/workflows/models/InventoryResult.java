package io.dapr.quickstarts.workflows.models;

import com.fasterxml.jackson.annotation.JsonProperty;

public class InventoryResult {
  @JsonProperty("success")
  private boolean success;
  @JsonProperty("item")
  private InventoryItem item;

  public boolean isSuccess() {
    return success;
  }

  public void setSuccess(boolean success) {
    this.success = success;
  }

  public InventoryItem getItem() {
    return item;
  }

  public void setItem(InventoryItem item) {
    this.item = item;
  }
  
  @Override
  public String toString() {
    return "InventoryResult [success=" + success + ", item=" + item + "]";
  }
}

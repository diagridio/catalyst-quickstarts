package io.dapr.quickstarts.workflows.models;

public class InventoryResult {
  private boolean success;
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

  public InventoryItem getInventoryItem() {
    return item;
  }

  public void setInventoryItem(InventoryItem inventoryItem) {
    this.item = inventoryItem;
  }

  @Override
  public String toString() {
    return "InventoryResult [success=" + success + ", item=" + item + "]";
  }
}

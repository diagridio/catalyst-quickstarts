package io.dapr.quickstarts.workflows.models;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.HashMap;
import java.util.Map;

public class InventoryItem {
  @JsonProperty("name")
  private String name;
  @JsonProperty("quantity")
  private int quantity;

  // Mock in-memory inventory
  private static final Map<String, InventoryItem> inventory = new HashMap<>();

  static {
    inventory.put("Car", new InventoryItem("Car", 50));
  }

  public InventoryItem(String name, int quantity) {
    this.name = name;
    this.quantity = quantity;
  }

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

  public static Map<String, InventoryItem> getInventory() {
    return inventory;
  }

  public static InventoryItem getItem(String name) {
    return inventory.get(name);
  }

  public static void updateItem(String name, int quantity) {
    InventoryItem item = inventory.get(name);
    if (item != null) {
      item.setQuantity(quantity);
    }
  }

  @Override
  public String toString() {
    return "InventoryItem [name=" + name + ", quantity=" + quantity + "]";
  }
}

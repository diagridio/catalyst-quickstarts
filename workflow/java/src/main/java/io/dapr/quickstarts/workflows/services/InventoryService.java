package io.dapr.quickstarts.workflows.services;

import io.dapr.quickstarts.workflows.models.InventoryItem;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;

@Service
public class InventoryService {

  private Map<String, InventoryItem> inventory = new HashMap<>();

  public InventoryService() {
    inventory.put("Car", new InventoryItem("Car", 50));
  }

  public InventoryItem getItem(String name) {
    return inventory.get(name);
  }

  public void updateItem(String name, int quantity) {
    InventoryItem item = inventory.get(name);
    if (item != null) {
      item.setQuantity(quantity);
    }
    else {
      inventory.put(name, new InventoryItem(name, quantity));
    }
  }

  public Map<String, InventoryItem> getAllItems() {
    return inventory;
  }

}

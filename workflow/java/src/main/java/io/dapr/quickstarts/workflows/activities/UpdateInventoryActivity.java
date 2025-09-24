package io.dapr.quickstarts.workflows.activities;

import io.dapr.workflows.WorkflowActivity;
import io.dapr.workflows.WorkflowActivityContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import io.dapr.quickstarts.workflows.models.*;

@Component
public class UpdateInventoryActivity implements WorkflowActivity {

  private static final Logger logger = LoggerFactory.getLogger(UpdateInventoryActivity.class);

  @Override
  public Object run(WorkflowActivityContext ctx) {
    InventoryRequest inventoryRequest = ctx.getInput(InventoryRequest.class);
    logger.info("Updating inventory for order {}: {} {}", inventoryRequest.getRequestId(),
        inventoryRequest.getQuantity(), inventoryRequest.getItemName());

    InventoryItem inventoryItem = InventoryItem.getItem(inventoryRequest.getItemName());
    if (inventoryItem == null) {
      logger.info("Item {} not found in inventory.", inventoryRequest.getItemName());
      InventoryResult result = new InventoryResult();
      result.setSuccess(false);
      return result;
    }

    int available = inventoryItem.getQuantity();
    if (available >= inventoryRequest.getQuantity()) {
      InventoryItem.updateItem(inventoryRequest.getItemName(), available - inventoryRequest.getQuantity());
      logger.info("Updated {} inventory to {} remaining.", inventoryRequest.getItemName(),
          available - inventoryRequest.getQuantity());
      InventoryResult result = new InventoryResult();
      result.setSuccess(true);
      result.setItem(new InventoryItem(inventoryItem.getName(), available - inventoryRequest.getQuantity()));
      return result;
    }

    logger.info("Not enough {} in inventory for the request: only {} remaining.", inventoryRequest.getItemName(),
        available);
    InventoryResult result = new InventoryResult();
    result.setSuccess(false);
    result.setItem(new InventoryItem(inventoryItem.getName(), available));
    return result;
  }
}

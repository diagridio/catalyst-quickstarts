package io.dapr.quickstarts.workflows;

import org.springframework.stereotype.Service;
import io.dapr.workflows.Workflow;
import io.dapr.workflows.WorkflowStub;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import io.dapr.quickstarts.workflows.models.*;
import io.dapr.quickstarts.workflows.activities.*;

@Service
public class OrderProcessingWorkflow extends Workflow {

  private static final Logger logger = LoggerFactory.getLogger(OrderProcessingWorkflow.class);

  @Override
  public WorkflowStub create() {
    return ctx -> {
      String orderId = ctx.getInstanceId();
      OrderPayload order = ctx.getInput(OrderPayload.class);
      OrderResult orderResult = new OrderResult();
      orderResult.setProcessed(false);

      // Notify the user that an order has come through
      Notification notification = new Notification();
      notification.setMessage("Received Order: " + order.toString());
      ctx.callActivity(NotifyActivity.class.getName(), notification).await();

      // Determine if there is enough of the item available for purchase by checking
      // the inventory
      InventoryRequest inventoryRequest = new InventoryRequest();
      inventoryRequest.setRequestId(orderId);
      inventoryRequest.setItemName(order.getItemName());
      inventoryRequest.setQuantity(order.getQuantity());
      InventoryResult inventoryResult = ctx
          .callActivity(ReserveInventoryActivity.class.getName(), inventoryRequest, InventoryResult.class).await();

      // If there is insufficient inventory, fail and let the user know
      if (!inventoryResult.isSuccess()) {
        notification.setMessage("Insufficient inventory for order: " + order.getItemName());
        ctx.callActivity(NotifyActivity.class.getName(), notification).await();
        ctx.complete(orderResult);
        return;
      }

      // There is enough inventory available so the user can purchase the item(s).
      // Process their payment
      PaymentRequest paymentRequest = new PaymentRequest();
      paymentRequest.setRequestId(orderId);
      paymentRequest.setItemBeingPurchased(order.getItemName());
      paymentRequest.setQuantity(order.getQuantity());
      boolean isOK = ctx.callActivity(ProcessPaymentActivity.class.getName(), paymentRequest, boolean.class).await();
      if (!isOK) {
        notification.setMessage("Payment failed for order: " + orderId);
        ctx.callActivity(NotifyActivity.class.getName(), notification).await();
        ctx.complete(orderResult);
        return;
      }

      // Update the inventory
      inventoryResult = ctx
          .callActivity(UpdateInventoryActivity.class.getName(), inventoryRequest, InventoryResult.class).await();
      if (!inventoryResult.isSuccess()) {
        // If there is an error updating the inventory, let the user know
        notification.setMessage("Order failed to update inventory! : " + orderId);
        ctx.callActivity(NotifyActivity.class.getName(), notification).await();
        ctx.complete(orderResult);
        return;
      }

      // Let user know their order was processed
      notification.setMessage("Order completed! : " + orderId);
      ctx.callActivity(NotifyActivity.class.getName(), notification).await();

      // Complete the workflow with order result is processed
      orderResult.setProcessed(true);
      ctx.complete(orderResult);
    };
  }
}

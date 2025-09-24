package io.dapr.quickstarts.workflows;

import org.springframework.stereotype.Service;
import io.dapr.workflows.Workflow;
import io.dapr.workflows.WorkflowStub;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import io.dapr.quickstarts.workflows.models.*;
import io.dapr.quickstarts.workflows.activities.*;

@Service
public class OrderProcessingWorkflow implements Workflow {

  private static final Logger logger = LoggerFactory.getLogger(OrderProcessingWorkflow.class);

  @Override
  public WorkflowStub create() {
    return ctx -> {
      String orderId = ctx.getInstanceId();
      OrderPayload order = ctx.getInput(OrderPayload.class);
      OrderResult orderResult = new OrderResult(false, "");

      // Notify the user that an order has come through
      Notification notification = new Notification();
      notification.setMessage("Received order " + orderId + " for " + order.getQuantity() + " " + order.getName());
      ctx.callActivity(NotifyActivity.class.getCanonicalName(), notification).await();

      // Determine if there is enough of the item available for purchase by checking
      // the inventory
      InventoryRequest inventoryRequest = new InventoryRequest();
      inventoryRequest.setRequestId(orderId);
      inventoryRequest.setItemName(order.getName());
      inventoryRequest.setQuantity(order.getQuantity());
      InventoryResult inventoryResult = ctx.callActivity(ReserveInventoryActivity.class.getCanonicalName(), inventoryRequest, InventoryResult.class).await();

      // If there is insufficient inventory, fail and let the user know
      if (!inventoryResult.isSuccess()) {
        notification.setMessage("Insufficient inventory for " + order.getName());
        orderResult.setMessage("Order failed due to insufficient inventory");
        ctx.callActivity(NotifyActivity.class.getCanonicalName(), notification).await();
        ctx.complete(orderResult);
        return;
      }

      // There is enough inventory available so the user can purchase the item(s).
      // Process their payment
      PaymentRequest paymentRequest = new PaymentRequest();
      paymentRequest.setRequestId(orderId);
      paymentRequest.setItemName(order.getName());
      paymentRequest.setQuantity(order.getQuantity());
      boolean isOK = ctx.callActivity(ProcessPaymentActivity.class.getCanonicalName(), paymentRequest, boolean.class).await();
      if (!isOK) {
        notification.setMessage("Order " + orderId + " Failed! You are now getting a refund");
        orderResult.setMessage("Order failed during payment processing");
        ctx.callActivity(NotifyActivity.class.getCanonicalName(), notification).await();
        ctx.complete(orderResult);
        return;
      }

      // Update the inventory
      inventoryResult = ctx.callActivity(UpdateInventoryActivity.class.getCanonicalName(), inventoryRequest, InventoryResult.class).await();
      if (!inventoryResult.isSuccess()) {
        // If there is an error updating the inventory, let the user know
        notification.setMessage("Order " + orderId + " Failed! You are now getting a refund");
        orderResult.setMessage("Order failed during inventory update");
        ctx.callActivity(NotifyActivity.class.getCanonicalName(), notification).await();
        ctx.complete(orderResult);
        return;
      }

      // Let user know their order was processed
      notification.setMessage("Order " + orderId + " has completed!");
      ctx.callActivity(NotifyActivity.class.getCanonicalName(), notification).await();

      // Complete the workflow with order result is processed
      orderResult.setProcessed(true);
      orderResult.setMessage("Order has completed!");
      ctx.complete(orderResult);
    };
  }
}

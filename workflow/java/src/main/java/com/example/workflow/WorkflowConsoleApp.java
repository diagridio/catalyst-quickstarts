package io.dapr.quickstarts.workflows;

import java.time.Duration;
import java.util.concurrent.TimeoutException;

import io.dapr.quickstarts.workflows.activities.NotifyActivity;
import io.dapr.quickstarts.workflows.activities.ProcessPaymentActivity;
import io.dapr.quickstarts.workflows.activities.ReserveInventoryActivity;
import io.dapr.quickstarts.workflows.activities.UpdateInventoryActivity;
import io.dapr.quickstarts.workflows.models.OrderPayload;
import io.dapr.workflows.client.DaprWorkflowClient;
import io.dapr.workflows.client.WorkflowInstanceStatus;
import io.dapr.workflows.runtime.WorkflowRuntime;
import io.dapr.workflows.runtime.WorkflowRuntimeBuilder;

public class WorkflowConsoleApp {

  /**
   * The main method of this console app.
   *
   * @param args The port the app will listen on.
   */
  public static void main(String[] args) {
    try {
      System.out.println("*** Welcome to the Dapr Workflow console app sample!");
      System.out.println("*** Using this app, you can place orders that start workflows.");
      // Wait for the sidecar to become available
      Thread.sleep(5000); // 5 seconds

      // Register the OrderProcessingWorkflow and its activities with the builder.
      WorkflowRuntimeBuilder builder = new WorkflowRuntimeBuilder().registerWorkflow(OrderProcessingWorkflow.class);
      builder.registerActivity(NotifyActivity.class);
      builder.registerActivity(ProcessPaymentActivity.class);
      builder.registerActivity(ReserveInventoryActivity.class);
      builder.registerActivity(UpdateInventoryActivity.class);

      // Build and then start the workflow runtime pulling and executing tasks
      try (WorkflowRuntime runtime = builder.build()) {
        System.out.println("Start workflow runtime");
        runtime.start(false);
      }

      // Prepare inventory and execute the workflow
      prepareInventory();
      executeWorkflow();
    } catch (InterruptedException e) {
      System.err.println("Main thread interrupted");
    } catch (Exception e) {
      System.err.println("An unexpected exception occurred: " + e.getMessage());
      e.printStackTrace();
    }
  }

  private static void executeWorkflow() {
    System.out.println("========== Begin the purchase of item ==========");
    String itemName = "cars";
    int orderQuantity = 10;
    OrderPayload order = new OrderPayload();
    order.setItemName(itemName);
    order.setQuantity(orderQuantity);

    try (DaprWorkflowClient workflowClient = new DaprWorkflowClient()) {
      String instanceId = workflowClient.scheduleNewWorkflow(OrderProcessingWorkflow.class, order);
      System.out.printf("Scheduled new workflow instance of OrderProcessingWorkflow with instance ID: %s%n",
          instanceId);

      try {
        workflowClient.waitForInstanceStart(instanceId, Duration.ofSeconds(10), false);
        System.out.printf("Workflow instance %s started%n", instanceId);
      } catch (TimeoutException e) {
        System.out.printf("Workflow instance %s did not start within 10 seconds%n", instanceId);
      }

      try {
        WorkflowInstanceStatus workflowStatus = workflowClient.waitForInstanceCompletion(instanceId,
            Duration.ofSeconds(30), true);
        if (workflowStatus != null) {
          System.out.printf("Workflow instance completed, output is: %s%n", workflowStatus.getSerializedOutput());
        } else {
          System.out.printf("Workflow instance %s not found%n", instanceId);
        }
      } catch (TimeoutException e) {
        System.out.printf("Workflow instance %s did not complete within 30 seconds%n", instanceId);
      }
    } catch (Exception e) {
      System.err.println("Failed to create or operate DaprWorkflowClient: " + e.getMessage());
    }
  }

  private static void prepareInventory() {
    OrderProcessingWorkflow.inventory.put("cars", new java.util.concurrent.atomic.AtomicInteger(50));
    System.out.println("Inventory prepared with 50 cars.");
  }
}

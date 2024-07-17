package io.dapr.quickstarts.workflows;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import io.dapr.workflows.runtime.WorkflowRuntime;
import io.dapr.workflows.runtime.WorkflowRuntimeBuilder;
import io.dapr.workflows.client.DaprWorkflowClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;


import io.dapr.quickstarts.workflows.models.*;
import io.dapr.quickstarts.workflows.activities.*;

@SpringBootApplication
@RestController
public class WorkflowApp {

  private static final Logger logger = LoggerFactory.getLogger(NotifyActivity.class);

  public static void main(String[] args) {
    SpringApplication.run(WorkflowApp.class, args);
  }

  @PostMapping("/workflow/start")
  public ResponseEntity<String> startWorkflow(@RequestBody OrderPayload order) {
    logger.info(String.format("Received request to start workflow for item: %s with quantity: %d",
        order.getItemName(), order.getQuantity()));

    // Register
    WorkflowRuntimeBuilder builder = new WorkflowRuntimeBuilder().registerWorkflow(OrderProcessingWorkflow.class);
    builder.registerActivity(NotifyActivity.class);
    builder.registerActivity(ProcessPaymentActivity.class);
    builder.registerActivity(ReserveInventoryActivity.class);
    builder.registerActivity(UpdateInventoryActivity.class);

    try (WorkflowRuntime runtime = builder.build()) {
      logger.info("Start workflow runtime");
      runtime.start(false);
    }

    DaprWorkflowClient workflowClient = new DaprWorkflowClient();

    // Run the workflow
    try {
      // orderProcessingWorkflow.executeWorkflow(order);
      String instanceId = workflowClient.scheduleNewWorkflow(OrderProcessingWorkflow.class, order);
      logger.info("Workflow execution started successfully for item: {}", order.getItemName());
      return ResponseEntity.ok("Workflow started successfully.");
    } catch (Exception e) {
      logger.error("Error starting workflow for item: {}", order.getItemName(), e);
      return ResponseEntity.internalServerError().body("Failed to start workflow: " + e.getMessage());
    }
  }
}

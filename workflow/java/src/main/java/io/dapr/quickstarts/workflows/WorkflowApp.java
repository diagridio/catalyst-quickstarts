/*
 * Dapr Workflow Quickstart - Java Implementation
 * 
 * This application demonstrates a simple order processing workflow using Dapr Workflows.
 * The workflow includes inventory checking, payment processing, and inventory updates.
 * 
 * Workflow Steps:
 * 1. Notify user of order receipt
 * 2. Reserve inventory for the order
 * 3. Process payment for the order
 * 4. Update inventory after successful payment
 * 5. Notify user of completion
 * 
 * For more information, visit: https://docs.diagrid.io/catalyst/quickstart/workflow
 */

package io.dapr.quickstarts.workflows;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;
import io.dapr.workflows.client.DaprWorkflowClient;
import io.dapr.workflows.client.WorkflowInstanceStatus;
import io.dapr.spring.workflows.config.EnableDaprWorkflows;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.json.JSONObject;

import io.dapr.quickstarts.workflows.models.*;

/**
 * Main Spring Boot application class for the Dapr Workflow Quickstart.
 * This class provides REST endpoints to interact with the order processing workflow.
 */
@SpringBootApplication
@RestController
@EnableDaprWorkflows
public class WorkflowApp {

  private static final Logger logger = LoggerFactory.getLogger(WorkflowApp.class);

  @Autowired
  private DaprWorkflowClient workflowClient;

  private String instanceId;

  /**
   * Health check endpoint - verifies the service is running
   * GET /
   * Returns: { "message": "Health check passed. Everything is running smoothly!" }
   */
  @GetMapping("/")
  public ResponseEntity<Object> readRoot() {
    String healthMessage = "Health check passed. Everything is running smoothly!";
    logger.info("Health check result: {}", healthMessage);
    JSONObject response = new JSONObject();
    response.put("message", healthMessage);
    return ResponseEntity.ok(response.toMap());
  }

  /**
   * Start new workflow - creates and schedules a new order processing workflow
   * POST /workflow/start
   * Body: { "name": "Car", "quantity": 2 }
   * Returns: { "instanceId": "uuid" }
   */
  @PostMapping("/workflow/start")
  public ResponseEntity<Object> startWorkflow(@RequestBody OrderPayload order) {
    logger.info("Received request to start workflow for item: {} with quantity: {}", order.getName(), order.getQuantity());

    try {
      instanceId = workflowClient.scheduleNewWorkflow(OrderProcessingWorkflow.class, order);
      logger.info("Workflow execution started successfully for item: {} {}", order.getQuantity(), order.getName());
      java.util.Map<String, Object> response = new java.util.HashMap<>();
      response.put("instanceId", instanceId);
      return ResponseEntity.ok(response);
    } catch (Exception e) {
      logger.error("Error starting workflow for item: {} {}", order.getQuantity(), order.getName(), e);
      return ResponseEntity.internalServerError().body("Failed to start workflow: " + e.getMessage());
    }
  }

  /**
   * Get workflow status - retrieves the current state of a workflow instance
   * GET /workflow/status/{instanceId}
   * Returns: WorkflowInstanceStatus object or 204 if not found
   */
  @GetMapping("/workflow/status/{instanceId}")
  public ResponseEntity<Object> getWorkflowStatus(@PathVariable String instanceId) {
    try {
      WorkflowInstanceStatus status = workflowClient.getInstanceState(instanceId, true);
      if (status != null) {
        logger.info("Retrieved workflow status for {}.", instanceId);
        return ResponseEntity.ok(status);
      } else {
        logger.info("Workflow with id {} does not exist", instanceId);
        return ResponseEntity.status(204).build();
      }
    } catch (Exception e) {
      logger.error("Error occurred while getting the status of the workflow: {}. Exception: {}", instanceId, e.getMessage());
      return ResponseEntity.status(500).build();
    }
  }

  /**
   * Terminate workflow - stops a running workflow instance
   * POST /workflow/terminate/{instanceId}
   * Returns: Updated WorkflowInstanceStatus object
   */
  @PostMapping("/workflow/terminate/{instanceId}")
  public ResponseEntity<Object> terminateWorkflow(@PathVariable String instanceId) {
    try {
      // Check current state first to provide accurate messaging
      WorkflowInstanceStatus currentStatus = workflowClient.getInstanceState(instanceId, true);
      if (currentStatus == null) {
        logger.info("Workflow with id {} does not exist", instanceId);
        return ResponseEntity.status(204).build();
      }

      // If already in a terminal state, just return the current state
      var terminalStatuses = java.util.Set.of("COMPLETED", "FAILED", "TERMINATED");
      if (terminalStatuses.contains(currentStatus.getRuntimeStatus().toString())) {
        logger.info("Workflow with id {} is already in terminal state {}", instanceId, currentStatus.getRuntimeStatus());
        return ResponseEntity.ok(currentStatus);
      }

      // Terminate the workflow
      workflowClient.terminateWorkflow(instanceId, "dapr");
      logger.info("Terminated workflow with id {}.", instanceId);
      
      // Return the updated state
      WorkflowInstanceStatus updatedStatus = workflowClient.getInstanceState(instanceId, true);
      return ResponseEntity.ok(updatedStatus);
    } catch (Exception e) {
      logger.error("Error occurred while terminating the workflow: {}. Exception: {}", instanceId, e.getMessage());
      return ResponseEntity.status(500).build();
    }
  }

  public static void main(String[] args) {
    SpringApplication.run(WorkflowApp.class, args);
  }
}

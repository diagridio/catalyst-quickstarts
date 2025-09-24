/*
 * Dapr Workflow Quickstart - JavaScript Implementation
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

import express from "express";
import bodyParser from "body-parser";
import { v4 as uuidv4 } from "uuid";
import { WorkflowRuntime, DaprWorkflowClient } from "@dapr/dapr";
import {
  orderProcessingWorkflow,
  notifyActivity,
  reserveInventoryActivity,
  processPaymentActivity,
  updateInventoryActivity,
} from "./workflow.js";

const app = express();
const port = process.env.PORT ?? 5001;

app.use(bodyParser.json());

console.log("Starting workflow runtime...");

// Initialize Dapr workflow client and runtime
const workflowClient = new DaprWorkflowClient();
const workflowRuntime = new WorkflowRuntime();

// Register all workflow components with the runtime
workflowRuntime
  .registerWorkflow(orderProcessingWorkflow)
  .registerActivity(notifyActivity)
  .registerActivity(reserveInventoryActivity)
  .registerActivity(processPaymentActivity)
  .registerActivity(updateInventoryActivity);

// Start the workflow runtime
(async () => {
  try {
    await workflowRuntime.start();
    console.log("Workflow runtime started successfully");
  } catch (error) {
    console.error("Error starting workflow runtime:", error);
  }
})();

// Health check endpoint - verifies the service is running
// GET /
// Returns: { "message": "Health check passed. Everything is running smoothly!" }
app.get("/", (_req, res) => {
  console.log(
    "Health check result: Health check passed. Everything is running smoothly!"
  );
  res
    .status(200)
    .json({ message: "Health check passed. Everything is running smoothly!" });
});

// Start new workflow - creates and schedules a new order processing workflow
// POST /workflow/start
// Body: { "name": "Car", "quantity": 2 }
// Returns: { "instance_id": "uuid" }
app.post("/workflow/start", async (req, res) => {
  try {
    const order = req.body;
    const instanceId = uuidv4();

    console.log(
      `Starting workflow for order ${instanceId}: ${order.quantity} ${order.name}`
    );

    await workflowClient.scheduleNewWorkflow(
      orderProcessingWorkflow,
      order,
      instanceId
    );

    console.log(
      `Workflow execution started successfully for order ${instanceId}`
    );
    res.json({
      instance_id: instanceId,
    });
  } catch (e) {
    console.error(`Error starting workflow: ${e.message}`);
    res.status(500).json({ error: e.message });
  }
});

// Get workflow status - retrieves the current state of a workflow instance
// GET /workflow/status/:instance_id
// Returns: WorkflowState object or 204 if not found
app.get("/workflow/status/:instance_id", async (req, res) => {
  const instanceId = req.params.instance_id;
  try {
    const state = await workflowClient.getWorkflowState(instanceId);
    if (!state) {
      console.log(`Workflow with id ${instanceId} does not exist`);
      return res.status(204).send();
    } else {
      console.log(`Retrieved workflow status for ${instanceId}.`);
      res.json(state);
    }
  } catch (e) {
    console.error(
      `Error occurred while getting the status of the workflow: ${instanceId}. Exception: ${e.message}`
    );
    res.status(500).json({ error: e.message });
  }
});

// Terminate workflow - stops a running workflow instance
// POST /workflow/terminate/:instance_id
// Returns: Updated WorkflowState object

app.post("/workflow/terminate/:instance_id", async (req, res) => {
  try {
    const instanceId = req.params.instance_id;

    // Check current state first to provide accurate messaging
    const currentState = await workflowClient.getWorkflowState(
      instanceId,
      false
    );
    if (!currentState) {
      console.log(`Workflow with id ${instanceId} does not exist`);
      return res.status(204).send();
    }

    // Terminate the workflow
    await workflowClient.terminateWorkflow(instanceId, "dapr");
    console.log(`Terminated workflow with id ${instanceId}.`);

    // Return the updated state
    const updatedState = await workflowClient.getWorkflowState(
      instanceId,
      false
    );
    res.json(updatedState);
  } catch (e) {
    console.error(
      `Error occurred while terminating the workflow: ${instanceId}. Exception: ${e.message}`
    );
    res.status(500).json({ error: e.message });
  }
});

app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});

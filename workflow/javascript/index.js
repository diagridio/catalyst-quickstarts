import express from 'express';
import bodyParser from 'body-parser';
import { WorkflowRuntime, DaprWorkflowClient } from '@dapr/dapr';
import {
  orderProcessingWorkflow,
  notifyActivity,
  reserveInventoryActivity,
  processPaymentActivity,
  updateInventoryActivity,
} from './workflow.js';

const app = express();
const port = process.env.PORT ?? 5001;

app.use(bodyParser.json());

console.log('Starting workflow runtime...');

const workflowClient = new DaprWorkflowClient();
const workflowRuntime = new WorkflowRuntime();

workflowRuntime
  .registerWorkflow(orderProcessingWorkflow)
  .registerActivity(notifyActivity)
  .registerActivity(reserveInventoryActivity)
  .registerActivity(processPaymentActivity)
  .registerActivity(updateInventoryActivity);

(async () => {
  try {
    await workflowRuntime.start();
    console.log('Workflow runtime started successfully');
  } catch (error) {
    console.error('Error starting workflow runtime:', error);
  }
})();

app.get('/', (_req, res) => {
  res.json({ message: 'Workflow is running' });
});

app.post('/workflow/start', async (req, res) => {
  try {
    const order = req.body;

    const workflowId = await workflowClient.scheduleNewWorkflow(orderProcessingWorkflow, order);
    console.log(`Workflow scheduled with ID: ${workflowId}`);

    res.json({
      message: 'Workflow started successfully',
      workflow_id: workflowId,
    });
  } catch (e) {
    console.error(`Failed to start workflow: ${e}`);
    res.status(500).json({ error: e.message });
  }
});

app.get('/workflow/status/:workflow_id', async (req, res) => {
  try {
    const workflowId = req.params.workflow_id;
    const state = await workflowClient.getWorkflowState(workflowId);
    if (!state) {
      res.json({ error: 'Workflow not found', workflow_id: workflowId });
    } else {
      res.json({
        workflow_id: workflowId,
        status: state.runtimeStatus,
      });
    }
  } catch (e) {
    console.error(`Failed to get workflow status: ${e}`);
    res.status(500).json({ error: e.message });
  }
});

app.post('/workflow/terminate/:workflow_id', async (req, res) => {
  try {
    const workflowId = req.params.workflow_id;
    await workflowClient.terminateWorkflow(workflowId);
    res.json({ message: 'Workflow terminated successfully' });
  } catch (e) {
    console.error(`Failed to terminate workflow: ${e}`);
    res.status(500).json({ error: e.message });
  }
});

app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});

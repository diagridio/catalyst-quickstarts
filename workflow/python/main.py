"""
Dapr Workflow Quickstart - Python Implementation

This application demonstrates a simple order processing workflow using Dapr Workflows.
The workflow includes inventory checking, payment processing, and inventory updates.

Workflow Steps:
1. Notify user of order receipt
2. Reserve inventory for the order
3. Process payment for the order
4. Update inventory after successful payment
5. Notify user of completion

For more information, visit: https://docs.diagrid.io/catalyst/quickstart/workflow
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
import logging
import uvicorn
import uuid
from dapr.ext.workflow import WorkflowRuntime, DaprWorkflowClient
from workflow import order_processing_workflow, notify_activity, reserve_inventory_activity, process_payment_activity, update_inventory_activity
from model import OrderPayload

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Starting workflow runtime...")

# Initialize and configure the Dapr workflow runtime
workflow_runtime = WorkflowRuntime()
workflow_runtime.register_workflow(order_processing_workflow)
workflow_runtime.register_activity(notify_activity)
workflow_runtime.register_activity(reserve_inventory_activity)
workflow_runtime.register_activity(process_payment_activity)
workflow_runtime.register_activity(update_inventory_activity)
workflow_runtime.start()

# Initialize the Dapr workflow client for API operations
workflow_client = DaprWorkflowClient()

# Health check endpoint - verifies the service is running
# GET /
# Returns: { "message": "Health check passed. Everything is running smoothly!" }
@app.get('/')
async def read_root():
    health_message = "Health check passed. Everything is running smoothly!"
    logger.info("Health check result: %s", health_message)
    return {"message": health_message}

# Start new workflow - creates and schedules a new order processing workflow
# POST /workflow/start
# Body: { "name": "Car", "quantity": 2 }
# Returns: { "instance_id": "uuid" }
@app.post("/workflow/start")
def start_workflow(order: OrderPayload):
    try:
        instance_id = str(uuid.uuid4())
        logger.info(f"Starting workflow for order {instance_id}: {order.quantity} {order.name}")
        
        workflow_client.schedule_new_workflow(workflow=order_processing_workflow, input=order.dict(), instance_id=instance_id)
        
        logger.info(f"Workflow execution started successfully for order {instance_id}")
        return {"instanceId": instance_id}
    except Exception as e:
        logger.error(f"Error starting workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Get workflow status - retrieves the current state of a workflow instance
# GET /workflow/status/{instance_id}
# Returns: WorkflowState object or 204 if not found
@app.get("/workflow/status/{instance_id}")
def get_workflow_status(instance_id: str):
    try:
        state = workflow_client.get_workflow_state(instance_id=instance_id)
        if not state:
            logger.info(f"Workflow with id {instance_id} does not exist")
            return Response(status_code=204)
        logger.info(f"Retrieved workflow status for {instance_id}.")
        logger.info(f"Workflow Runtime Status is: {state.runtime_status}")
        return state
    except Exception as e:
        logger.error(f"Error occurred while getting the status of the workflow: {instance_id}. Exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Terminate workflow - stops a running workflow instance
# POST /workflow/terminate/{instance_id}
# Returns: Updated WorkflowState object
@app.post("/workflow/terminate/{instance_id}")
def terminate_workflow(instance_id: str):
    try:
        # Check current state first to provide accurate messaging
        current_state = workflow_client.get_workflow_state(instance_id=instance_id)
        if not current_state:
            logger.info(f"Workflow with id {instance_id} does not exist")
            return Response(status_code=204)
        
        # If already in a terminal state, just return the current state
        # The status comes as WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, etc.
        status_str = str(current_state.runtime_status)
        if "COMPLETED" in status_str or "FAILED" in status_str or "TERMINATED" in status_str:
            logger.info(f"Workflow with id {instance_id} is already in terminal state {current_state.runtime_status}")
            return current_state
        
        # Terminate the workflow
        workflow_client.terminate_workflow(instance_id=instance_id)
        logger.info(f"Terminated workflow with id {instance_id}.")
        
        # Return the updated state
        updated_state = workflow_client.get_workflow_state(instance_id=instance_id)
        return updated_state
    except Exception as e:
        logger.error(f"Error occurred while terminating the workflow: {instance_id}. Exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)


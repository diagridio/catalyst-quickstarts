from fastapi import FastAPI, HTTPException
import logging
import uvicorn
from dapr.ext.workflow import WorkflowRuntime, DaprWorkflowClient
from workflow import order_processing_workflow, notify_activity, reserve_inventory_activity, process_payment_activity, update_inventory_activity
from model import OrderPayload

app = FastAPI()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

workflowName = "order_processing_workflow"
workflowComponent = "dapr"

logging.info("Starting workflow runtime...")
workflow_runtime = WorkflowRuntime()
workflow_runtime.register_workflow(order_processing_workflow)
workflow_runtime.register_activity(notify_activity)
workflow_runtime.register_activity(reserve_inventory_activity)
workflow_runtime.register_activity(process_payment_activity)
workflow_runtime.register_activity(update_inventory_activity)
workflow_runtime.start()

workflow_client = DaprWorkflowClient()

@app.get('/')
async def read_root():
    return {"message": "Workflow is running"}

@app.post("/workflow/start")
def start_workflow(order: OrderPayload):
    try:
        order_dict = order.dict(by_alias=True)
        workflow_id = workflow_client.schedule_new_workflow(workflow=order_processing_workflow, input=order_dict)
        return {"message": "Workflow started successfully", "workflow_id": workflow_id}
    except Exception as e:
        logger.error(f"Failed to start workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/workflow/status/{workflow_id}")
def get_workflow_status(workflow_id: str):
    try:
        state = workflow_client.get_workflow_state(instance_id=workflow_id)
        if not state:
            return {"error": "Workflow not found", "workflow_id": workflow_id}
        return {"workflow_id": workflow_id, "status": state.runtime_status}
    except Exception as e:
        logger.error(f"Failed to get workflow status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/workflow/terminate/{workflow_id}")
def terminate_workflow(workflow_id: str):
    try:
        workflow_client.terminate_workflow(instance_id=workflow_id)
        return {"message": "Workflow terminated successfully"}
    except Exception as e:
        logger.error(f"Failed to terminate workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/workflow/pause/{workflow_id}")
def pause_workflow(workflow_id: str):
    try:
        workflow_client.pause_workflow(instance_id=workflow_id)
        return {"message": "Workflow paused successfully"}
    except Exception as e:
        logger.error(f"Failed to pause workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/workflow/resume/{workflow_id}")
def resume_workflow(workflow_id: str):
    try:
        workflow_client.resume_workflow(instance_id=workflow_id)
        return {"message": "Workflow resumed successfully"}
    except Exception as e:
        logger.error(f"Failed to resume workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)


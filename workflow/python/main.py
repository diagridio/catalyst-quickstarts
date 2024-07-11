from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json
import logging
from dapr.clients import DaprClient
from dapr.ext.workflow import WorkflowRuntime
from workflow import order_processing_workflow, notify_activity, reserve_inventory_activity, process_payment_activity, update_inventory_activity
from model import OrderPayload

app = FastAPI()

@app.post("/workflow/start")
def start_workflow(order: OrderPayload):
    try:
        with DaprClient() as d:
            order_dict = order.model_dump(by_alias=True)
            resp = d.start_workflow(workflow_component="dapr", workflow_name="OrderProcessingWorkflow", input=order_dict)
        return {"message": "Workflow started successfully", "workflow_id": resp.instance_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/workflow/status/{workflow_id}")
def get_workflow_status(workflow_id: str):
    try:
        with DaprClient() as d:
            state = d.get_workflow(instance_id=workflow_id, workflow_component="dapr")
            if not state:
                return {"error": "Workflow not found", "workflow_id": workflow_id}
            return {"workflow_id": workflow_id, "status": state.runtime_status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
def startup_event():
    workflowRuntime = WorkflowRuntime()
    workflowRuntime.register_workflow(order_processing_workflow)
    workflowRuntime.register_activity(notify_activity)
    workflowRuntime.register_activity(reserve_inventory_activity)
    workflowRuntime.register_activity(process_payment_activity)
    workflowRuntime.register_activity(update_inventory_activity)
    workflowRuntime.start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)

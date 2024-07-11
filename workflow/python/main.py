from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from uuid import uuid4
import json
import logging
from dapr.clients import DaprClient
from dapr.ext.workflow import WorkflowRuntime
from workflow import order_processing_workflow, notify_activity, reserve_inventory_activity, process_payment_activity, update_inventory_activity

app = FastAPI()

class OrderPayload(BaseModel):
    item_name: str
    quantity: int

@app.post("/workflow/start")
def start_workflow(order: OrderPayload):
    workflow_id = str(uuid4())
    try:
        with DaprClient() as d:
            d.start_workflow(workflow_component="dapr", workflow_name="order_processing_workflow", input=order.json())
        return {"message": "Workflow started successfully", "workflow_id": workflow_id}
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


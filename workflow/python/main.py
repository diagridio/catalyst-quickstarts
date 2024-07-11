from fastapi import FastAPI, HTTPException
import json
import logging
from time import sleep
from dapr.clients import DaprClient
from dapr.ext.workflow import WorkflowRuntime
from workflow import order_processing_workflow, notify_activity, reserve_inventory_activity, process_payment_activity, update_inventory_activity
from model import OrderPayload
from contextlib import asynccontextmanager
from uuid import uuid4

app = FastAPI()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

workflowName = "order_processing_workflow"
workflowComponent = "dapr"
instanceId = str(uuid4())

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    workflow_runtime = WorkflowRuntime()
    workflow_runtime.register_workflow(order_processing_workflow)
    workflow_runtime.register_activity(notify_activity)
    workflow_runtime.register_activity(reserve_inventory_activity)
    workflow_runtime.register_activity(process_payment_activity)
    workflow_runtime.register_activity(update_inventory_activity)
    workflow_runtime.start()
    sleep(2)

    yield

@app.post("/workflow/start")
def start_workflow(order: OrderPayload):
    try:
        with DaprClient() as d:
            order_dict = json.dumps(order.model_dump(by_alias=True))
            resp = d.start_workflow(workflow_component=workflowComponent, workflow_name=workflowName, input=order_dict, instance_id=instanceId)
            return {"message": "Workflow started successfully", "workflow_id": resp.instance_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/workflow/status/{workflow_id}")
def get_workflow_status(workflow_id: str):
    try:
        with DaprClient() as d:
            state = d.get_workflow(instance_id=instanceId, workflow_component=workflowComponent)
            if not state:
                return {"error": "Workflow not found", "workflow_id": workflow_id}
            return {"workflow_id": workflow_id, "status": state.runtime_status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/workflow/terminate/{workflow_id}")
def terminate_workflow():
    try:
        with DaprClient() as d:
            d.terminate_workflow(instance_id=instanceId, workflow_component=workflowComponent)
            return {"message": "Workflow terminated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/workflow/pause/{workflow_id}")
def pause_workflow():
    try:
        with DaprClient() as d:
            d.pause_workflow(instance_id=instanceId, workflow_component=workflowComponent)
            return {"message": "Workflow paused successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/workflow/resume/{workflow_id}")
def resume_workflow():
    try:
        with DaprClient() as d:
            d.resume_workflow(instance_id=instanceId, workflow_component=workflowComponent)
            return {"message": "Workflow resumed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



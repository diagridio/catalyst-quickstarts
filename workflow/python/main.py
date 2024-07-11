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

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    workflow_runtime = WorkflowRuntime()
    workflow_runtime.register_workflow(order_processing_workflow)
    workflow_runtime.register_activity(notify_activity)
    workflow_runtime.register_activity(reserve_inventory_activity)
    workflow_runtime.register_activity(process_payment_activity)
    workflow_runtime.register_activity(update_inventory_activity)
    workflow_runtime.start()

    yield

@app.post("/workflow/start")
def start_workflow(order: OrderPayload):
    try:
        with DaprClient() as d:
            order_dict = json.dumps(order.model_dump(by_alias=True))
            resp = d.start_workflow(workflow_component="dapr", workflow_name="order_processing_workflow", input=order_dict)
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

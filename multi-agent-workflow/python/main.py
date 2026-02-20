import json
import logging
import uuid
from time import sleep

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

import dapr.ext.workflow as wf
from dapr.ext.workflow import WorkflowRuntime, DaprWorkflowClient

# ------------- MODELS -------------
class SupportRequest(BaseModel):
    customer: str
    issue: str


# ------------- WORKFLOW DEFINITION -------------
# Initialize Workflow runtime BEFORE defining workflows
workflow_runtime = WorkflowRuntime()


def _extract_content(response: dict) -> str:
    if isinstance(response, dict):
        content = response.get("content")
        if isinstance(content, str):
            return content
    return ""


def _parse_json_or_text(content: str) -> dict:
    if not content:
        return {}
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else {"content": content}
    except json.JSONDecodeError:
        return {"content": content}


@workflow_runtime.workflow(name="customer_support_workflow")
def customer_support_workflow(ctx: wf.DaprWorkflowContext, input_data: dict):
    name = input_data.get("customer")
    issue = input_data.get("issue")
    triage_response = yield ctx.call_child_workflow(
        workflow="agent_workflow",
        input={
            "task": (
                f"Customer: {name}. Issue: {issue}. "
                "Assess entitlement and urgency."
            )
        },
        app_id="triage-agent",
    )
    triage_content = _extract_content(triage_response)
    triage_result = _parse_json_or_text(triage_content)
    if not triage_result.get("entitled"):
        return {"status": "rejected", "reason": "No entitlement"}

    expert_response = yield ctx.call_child_workflow(
        workflow="agent_workflow",
        input={
            "task": (
                f"Customer: {name}. Issue: {issue}. "
                f"Urgency: {triage_result.get('urgency', 'normal')}. "
                "Retrieve customer environment and propose a resolution. "
                "Return a clear message formatted for customer communication."
            )
        },
        app_id="expert-agent",
    )
    expert_content = _extract_content(expert_response)
    expert_result = _parse_json_or_text(expert_content)
    return {"status": "completed", "result": expert_result}


# ------------- FASTAPI SETUP -------------
app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Start workflow runtime (already initialized above with decorators)
workflow_runtime.start()
sleep(3)

workflow_client = DaprWorkflowClient()


# ------------- SINGLE REST ENTRYPOINT -------------
@app.post("/workflow/start")
def start_workflow(request: SupportRequest):
    try:
        instance_id = str(uuid.uuid4())
        logger.info(f"Starting customer support workflow for {request.customer}")
        workflow_client.schedule_new_workflow(
            workflow=customer_support_workflow,
            input=request.dict(),
            instance_id=instance_id,
        )
        logger.info(f"Workflow started with ID: {instance_id}")
        return {"instanceId": instance_id}
    except Exception as e:
        logger.error(f"Failed to start workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ------------- MAIN -------------
if __name__ == "__main__":
    import uvicorn

    load_dotenv()
    uvicorn.run(app, host="0.0.0.0", port=8003)

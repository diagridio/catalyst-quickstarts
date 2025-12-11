import logging
import asyncio
import uuid
from time import sleep
from concurrent.futures import ThreadPoolExecutor
import threading
from fastapi import FastAPI, HTTPException
from dapr.ext.workflow import WorkflowRuntime, DaprWorkflowClient
import dapr.ext.workflow as wf
from dapr_agents import Agent, tool
from dapr_agents.llm.dapr import DaprChatClient
from dapr_agents.memory import ConversationDaprStateMemory
from dotenv import load_dotenv
from pydantic import BaseModel
from dapr_agents.storage.daprstores.stateservice import StateStoreService

from dapr_agents.agents.configs import (
    AgentMemoryConfig,
    AgentRegistryConfig,
)

# Thread pool for running async agent code
thread_pool = ThreadPoolExecutor(max_workers=5)

# Thread-local storage for event loops
_thread_local = threading.local()

# ------------- MODELS -------------
class SupportRequest(BaseModel):
    customer: str
    issue: str


# ------------- TRIAGE AGENT -------------
@tool
def check_entitlement(customer_name: str) -> bool:
    """Return True if customer has entitlement."""
    return customer_name.strip().lower() == "alice"


triage_agent = Agent(
    name="Triage Agent",
    role="Customer Support Triage Assistant",
    goal="Assess entitlement and urgency based on issue description.",
    instructions=[
        "1. Use the tool to check entitlement by name.",
        "2. If the customer has entitlement, classify urgency: "
        "if the issue affects production, mark as URGENT, otherwise NORMAL.",
        "3. Return a JSON object with keys: entitled (bool) and urgency (string).",
    ],
    llm=DaprChatClient(component_name="llm-provider"),
    tools=[check_entitlement],
    memory = AgentMemoryConfig(
        store=ConversationDaprStateMemory(
            store_name="statestore",
            session_id=f"session-triage-{uuid.uuid4().hex[:8]}"
        )
    ),

    registry = AgentRegistryConfig(
        store=StateStoreService(store_name="statestore"),
    ),
)


# ------------- EXPERT AGENT -------------
@tool
def get_customer_environment(customer_name: str) -> dict:
    """Return hardcoded environment details for a given customer."""
    return {
        "customer": customer_name,
        "kubernetes_version": "1.34.0",
        "region": "us-west-2",
    }

expert_agent = Agent(
    name="Expert Agent",
    role="Technical Troubleshooting Specialist",
    goal="Diagnose and summarize a customer issue into a professional response message.",
    instructions=[
        "Use the tool to fetch the customer's environment info.",
        "Based on the environment and issue description, provide a short, actionable resolution proposal.",
        "Summarize the resolution in a customer-friendly message format, including urgency.",
        "Output a JSON with fields: environment, resolution, and customer_message.",
    ],
    llm=DaprChatClient(component_name="llm-provider"),
    tools=[get_customer_environment],
    memory = AgentMemoryConfig(
        store=ConversationDaprStateMemory(
            store_name="statestore",
            session_id=f"session-expert-{uuid.uuid4().hex[:8]}"
        )
    ),

    registry = AgentRegistryConfig(
        store=StateStoreService(store_name="statestore"),
    ),
)


# ------------- WORKFLOW DEFINITION -------------
# Initialize Workflow runtime BEFORE defining workflows
workflow_runtime = WorkflowRuntime()

@workflow_runtime.workflow(name="customer_support_workflow")
def customer_support_workflow(ctx: wf.DaprWorkflowContext, input_data: dict):
    triage_result = yield ctx.call_activity(triage_activity, input=input_data)
    if not triage_result.get("entitled"):
        return {"status": "rejected", "reason": "No entitlement"}
    expert_response = yield ctx.call_activity(expert_activity, input=triage_result)
    return {"status": "completed", "result": expert_response}


def _run_async_in_thread(coro):
    """Helper to run async code in a thread with a persistent event loop."""
    # Get or create event loop for this thread
    if not hasattr(_thread_local, 'loop'):
        _thread_local.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_thread_local.loop)
    
    return _thread_local.loop.run_until_complete(coro)

@workflow_runtime.activity(name="triage_activity")
def triage_activity(ctx, input_data: dict):
    name = input_data.get("customer")
    issue = input_data.get("issue")
    
    # Run agent in a separate thread with its own event loop
    future = thread_pool.submit(
        _run_async_in_thread,
        triage_agent.run(f"Customer: {name}. Issue: {issue}. Assess entitlement and urgency.")
    )
    response = future.result()
    if not response or not getattr(response, "content", None):
        raise ValueError("Triage Agent returned no response.")

    print(f"Triage result: {response.content}")
    entitled = "true" in response.content.lower() or "yes" in response.content.lower()
    urgency = "urgent" if "urgent" in response.content.lower() else "normal"
    return {"customer": name, "issue": issue, "entitled": entitled, "urgency": urgency}


@workflow_runtime.activity(name="expert_activity")
def expert_activity(ctx, triage_result: dict):
    name = triage_result.get("customer")
    issue = triage_result.get("issue")
    urgency = triage_result.get("urgency")
    
    # Run agent in a separate thread with its own event loop
    future = thread_pool.submit(
        _run_async_in_thread,
        expert_agent.run(
            f"Customer: {name}. Issue: {issue}. Urgency: {urgency}. "
            f"Retrieve customer environment and propose a resolution. "
            f"Return a clear message formatted for customer communication."
        )
    )
    response = future.result()
    
    print(f"Expert response: {response.content}")
    return {"customer": name, "urgency": urgency, "resolution": response.content}


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
    uvicorn.run(app, host="0.0.0.0", port=5001)

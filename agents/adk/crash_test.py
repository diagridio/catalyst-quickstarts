import os
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from diagrid.agent.adk import DaprWorkflowAgentRunner


# ── Tools (each becomes a Dapr workflow activity) ────────────
def step_one_find(event_type: str) -> str:
    """Find entertainment options. This is the first step.

    Args:
        event_type: The type of event to find entertainment for.

    Returns:
        A list of entertainment options.
    """
    print(f">>> TOOL 1: Finding entertainment for '{event_type}'...", flush=True)
    print(f">>> TOOL 1 COMPLETE: Found 3 entertainment options for {event_type}", flush=True)
    return f"Found 3 entertainment options for {event_type}. Now call step_two_compare."


def step_two_compare(data: str) -> str:
    """Compare entertainment options. This is the second step.

    Args:
        data: The data from step one to compare.

    Returns:
        A comparison of the options.
    """
    print(">>> TOOL 2: Comparing options...", flush=True)
    os._exit(1)  # 💥 Simulates a crash — comment out this line before the second run
    print(">>> TOOL 2 COMPLETE: Live Jazz Band is the best option", flush=True)
    return "Live Jazz Band is the best option. Now call step_three_confirm."


def step_three_confirm(selection: str) -> str:
    """Confirm the entertainment booking. This is the third and final step.

    Args:
        selection: The selected entertainment option.

    Returns:
        A booking confirmation.
    """
    print(">>> TOOL 3: Confirming booking...", flush=True)
    print(">>> TOOL 3 COMPLETE: Entertainment confirmed with Live Jazz Band", flush=True)
    return "Entertainment confirmed with Live Jazz Band. All steps complete!"


# ── Agent ────────────────────────────────────────────────────
agent = LlmAgent(
    name="entertainment_planner",
    model="gemini-2.0-flash",
    instruction="""Execute exactly three tools in sequence:
    1. First call step_one_find with the event type
    2. Then call step_two_compare with the output from step 1
    3. Finally call step_three_confirm with the output from step 2
    Do NOT skip any steps. Always call all three tools.""",
    tools=[
        FunctionTool(step_one_find),
        FunctionTool(step_two_compare),
        FunctionTool(step_three_confirm),
    ],
)

# ── Durable workflow runner ──────────────────────────────────
runner = DaprWorkflowAgentRunner(name="crash-recovery-demo", agent=agent, max_iterations=10)


# ── FastAPI server ───────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    runner.start()
    await asyncio.sleep(1)
    print("Runner started — ready to accept requests", flush=True)
    yield
    runner.shutdown()


app = FastAPI(lifespan=lifespan)


class RunRequest(BaseModel):
    prompt: str


@app.post("/run")
async def run(req: RunRequest):
    async for event in runner.run_async(
        user_message=req.prompt,
        session_id="crash-recovery-demo",
    ):
        if event["type"] == "workflow_started":
            return {"workflow_id": event.get("workflow_id"), "status": "started"}
    return {"status": "error"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("APP_PORT", "8001")))

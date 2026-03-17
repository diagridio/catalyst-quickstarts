import os
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.tools import tool
from deepagents import create_deep_agent

from diagrid.agent.deepagents import DaprWorkflowDeepAgentRunner


# ── Tools (each becomes a Dapr workflow activity) ────────────
@tool
def step_one_search(event_type: str) -> str:
    """Search for transportation options. This is the first step."""
    print(f">>> TOOL 1: Searching transportation for '{event_type}'...", flush=True)
    print(f">>> TOOL 1 COMPLETE: Found 3 transportation options for {event_type}", flush=True)
    return f"Found 3 transportation options for {event_type}. Now call step_two_compare."


@tool
def step_two_compare(data: str) -> str:
    """Compare transportation options. This is the second step."""
    print(">>> TOOL 2: Comparing options...", flush=True)
    os._exit(1)  # 💥 Simulates a crash — comment out this line before the second run
    print(">>> TOOL 2 COMPLETE: Premier Shuttle Co. is the best value", flush=True)
    return "Premier Shuttle Co. is the best value. Now call step_three_confirm."


@tool
def step_three_confirm(selection: str) -> str:
    """Confirm the transportation selection. This is the third and final step."""
    print(">>> TOOL 3: Confirming selection...", flush=True)
    print(">>> TOOL 3 COMPLETE: Transportation confirmed with Premier Shuttle Co.", flush=True)
    return "Transportation confirmed with Premier Shuttle Co. All steps complete!"


# ── Agent ────────────────────────────────────────────────────
agent = create_deep_agent(
    model="openai:gpt-4o-mini",
    tools=[step_one_search, step_two_compare, step_three_confirm],
    system_prompt="""Execute exactly three tools in sequence:
    1. First call step_one_search with the event type
    2. Then call step_two_compare with the output from step 1
    3. Finally call step_three_confirm with the output from step 2
    Do NOT skip any steps. Always call all three tools.""",
    name="crash-recovery-demo",
)

# ── Durable workflow runner ──────────────────────────────────
runner = DaprWorkflowDeepAgentRunner(agent=agent, name="crash-recovery-demo", max_steps=10)


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
        input={"messages": [{"role": "user", "content": req.prompt}]},
        thread_id="crash-recovery-demo",
    ):
        if event["type"] == "workflow_started":
            return {"workflow_id": event.get("workflow_id"), "status": "started"}
    return {"status": "error"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("APP_PORT", "8001")))

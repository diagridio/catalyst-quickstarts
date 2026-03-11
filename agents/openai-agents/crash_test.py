import os
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from agents import Agent, function_tool

from diagrid.agent.openai_agents import DaprWorkflowAgentRunner


# ── Tools (each becomes a Dapr workflow activity) ────────────
@function_tool
def step_one_search(cuisine: str) -> str:
    """Search for catering options. This is the first step."""
    print(f">>> TOOL 1: Searching catering for '{cuisine}'...", flush=True)
    return f"Found 3 {cuisine} catering options. Now call step_two_compare."


@function_tool
def step_two_compare(data: str) -> str:
    """Compare catering options. This is the second step."""
    print(">>> TOOL 2: Comparing options...", flush=True)
    os._exit(1)  # 💥 Simulates a crash — comment out this line before the second run
    return "Farm Fresh Events is the best value. Now call step_three_confirm."


@function_tool
def step_three_confirm(selection: str) -> str:
    """Confirm the catering selection. This is the third and final step."""
    print(">>> TOOL 3: Confirming selection...", flush=True)
    return "Catering confirmed with Farm Fresh Events. All steps complete!"


# ── Agent ────────────────────────────────────────────────────
agent = Agent(
    name="catering-coordinator",
    model="gpt-4o-mini",
    instructions="""Execute exactly three tools in sequence:
    1. First call step_one_search with the cuisine type
    2. Then call step_two_compare with the output from step 1
    3. Finally call step_three_confirm with the output from step 2
    Do NOT skip any steps. Always call all three tools.""",
    tools=[step_one_search, step_two_compare, step_three_confirm],
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

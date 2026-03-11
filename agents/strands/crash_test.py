import os
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from strands import Agent, tool
from strands.models.openai import OpenAIModel

from diagrid.agent.strands import DaprWorkflowAgentRunner


# ── Tools (each becomes a Dapr workflow activity) ────────────
@tool
def step_one_calculate(items: str) -> str:
    """Calculate initial budget from cost items. This is the first step.

    Args:
        items: A comma-separated list of cost items.

    Returns:
        The initial budget estimate.
    """
    print(f">>> TOOL 1: Calculating budget for '{items}'...", flush=True)
    return "Estimated budget: $8,550. Now call step_two_analyze."


@tool
def step_two_analyze(data: str) -> str:
    """Analyze the budget for cost savings. This is the second step.

    Args:
        data: The budget data from step one.

    Returns:
        Analysis of potential savings.
    """
    print(">>> TOOL 2: Analyzing costs...", flush=True)
    os._exit(1)  # 💥 Simulates a crash — comment out this line before the second run
    return "Found $1,200 in potential savings. Now call step_three_finalize."


@tool
def step_three_finalize(analysis: str) -> str:
    """Finalize the budget report. This is the third and final step.

    Args:
        analysis: The cost analysis from step two.

    Returns:
        The final budget report.
    """
    print(">>> TOOL 3: Finalizing budget...", flush=True)
    return "Final budget: $7,350 (saved $1,200). All steps complete!"


# ── Agent ────────────────────────────────────────────────────
agent = Agent(
    model=OpenAIModel(model_id="gpt-4o-mini"),
    tools=[step_one_calculate, step_two_analyze, step_three_finalize],
    system_prompt="""Execute exactly three tools in sequence:
    1. First call step_one_calculate with the budget items
    2. Then call step_two_analyze with the output from step 1
    3. Finally call step_three_finalize with the output from step 2
    Do NOT skip any steps. Always call all three tools.""",
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
        task=req.prompt,
        session_id="crash-recovery-demo",
    ):
        if event["type"] == "workflow_started":
            return {"workflow_id": event.get("workflow_id"), "status": "started"}
    return {"status": "error"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("APP_PORT", "8001")))

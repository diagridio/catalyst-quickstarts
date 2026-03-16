import os
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from crewai import Agent, Task
from crewai.tools import tool

from diagrid.agent.crewai import DaprWorkflowAgentRunner


# ── Tools (each becomes a Dapr workflow activity) ────────────
@tool("Step 1 - Search venues")
def step_one_search(city: str) -> str:
    """Search for event venues in a city. This is the first step."""
    print(f">>> TOOL 1: Searching venues in '{city}'...", flush=True)
    print(f">>> TOOL 1 COMPLETE: Found 3 venues in {city}", flush=True)
    return f"Found 3 venues in {city}. Now call step_two___compare_venues."


@tool("Step 2 - Compare venues")
def step_two_compare(data: str) -> str:
    """Compare the venue options. This is the second step."""
    print(">>> TOOL 2: Comparing venues...", flush=True)
    os._exit(1)  # 💥 Simulates a crash — comment out this line before the second run
    print(">>> TOOL 2 COMPLETE: Grand Ballroom is the best option", flush=True)
    return "Grand Ballroom is the best option. Now call step_three___confirm_booking."


@tool("Step 3 - Confirm booking")
def step_three_confirm(selection: str) -> str:
    """Confirm the venue booking. This is the third and final step."""
    print(">>> TOOL 3: Confirming booking...", flush=True)
    print(">>> TOOL 3 COMPLETE: Booking confirmed for Grand Ballroom", flush=True)
    return "Booking confirmed for Grand Ballroom. All steps complete!"


# ── Agent ────────────────────────────────────────────────────
agent = Agent(
    role="Event Planner",
    goal="Execute exactly three tools in sequence: step_one, step_two, step_three",
    backstory="""You are an event planner. Call all three tools in sequence:
    1. First call step_one___search_venues with the city name
    2. Then call step_two___compare_venues with the output from step 1
    3. Finally call step_three___confirm_booking with the output from step 2
    Do NOT skip any steps.""",
    tools=[step_one_search, step_two_compare, step_three_confirm],
    llm="gpt-4o-mini",
    verbose=True,
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
    task = Task(
        description=req.prompt,
        expected_output="A summary confirming all three steps completed.",
        agent=agent,
    )
    async for event in runner.run_async(
        task=task,
        session_id="crash-recovery-demo",
    ):
        if event["type"] == "workflow_started":
            return {"workflow_id": event.get("workflow_id"), "status": "started"}
    return {"status": "error"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("APP_PORT", "8001")))

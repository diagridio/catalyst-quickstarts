import os
import asyncio
from typing import List, TypedDict
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END

from diagrid.agent.langgraph import DaprWorkflowGraphRunner


# ── Graph state ──────────────────────────────────────────────
class PlannerState(TypedDict):
    topic: str
    results: List[str]


# ── Graph nodes (each becomes a Dapr workflow activity) ──────
def check_venues(state: PlannerState) -> dict:
    print(f">>> STEP 1: Checking venue availability for '{state['topic']}'...", flush=True)
    result = "Grand Ballroom available on March 15 (2PM-6PM, 6PM-11PM)"
    print(f">>> STEP 1 COMPLETE: {result}", flush=True)
    return {"results": state["results"] + [result]}


def compare_options(state: PlannerState) -> dict:
    print(">>> STEP 2: Comparing venue options...", flush=True)
    os._exit(1)  # 💥 Simulates a crash — comment out this line before the second run
    result = "Grand Ballroom (6PM-11PM) is the best option for 200 guests"
    print(f">>> STEP 2 COMPLETE: {result}", flush=True)
    return {"results": state["results"] + [result]}


def confirm_booking(state: PlannerState) -> dict:
    print(">>> STEP 3: Confirming booking...", flush=True)
    result = "Booking confirmed: Grand Ballroom, March 15, 6PM-11PM"
    print(f">>> STEP 3 COMPLETE: {result}", flush=True)
    return {"results": state["results"] + [result]}


# ── Build graph ──────────────────────────────────────────────
graph = StateGraph(PlannerState)
graph.add_node("check_venues", check_venues)
graph.add_node("compare_options", compare_options)
graph.add_node("confirm_booking", confirm_booking)
graph.add_edge(START, "check_venues")
graph.add_edge("check_venues", "compare_options")
graph.add_edge("compare_options", "confirm_booking")
graph.add_edge("confirm_booking", END)

# ── Durable workflow runner ──────────────────────────────────
runner = DaprWorkflowGraphRunner(
    graph=graph.compile(),
    name="crash-recovery-demo",
)


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
    topic: str


@app.post("/run")
async def run(req: RunRequest):
    async for event in runner.run_async(
        input={"topic": req.topic, "results": []},
        thread_id="crash-recovery-demo",
    ):
        if event["type"] == "workflow_started":
            return {"workflow_id": event.get("workflow_id"), "status": "started"}
    return {"status": "error"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("APP_PORT", "8001")))

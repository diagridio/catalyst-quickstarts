import os
import asyncio
import json
import time
from typing import List, Optional, TypedDict
from contextlib import asynccontextmanager

import uvicorn
from dapr.ext.workflow import DaprWorkflowClient
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END

from diagrid.agent.langgraph import DaprWorkflowGraphRunner


# ── Graph state ──────────────────────────────────────────────
class PlannerState(TypedDict):
    topic: str
    results: List[str]


# ── Graph nodes (each becomes a Dapr workflow activity) ──────
# The node ORDER is the design, not an accident. Step 1 finishes in milliseconds, so
# Catalyst has persisted its result before step 2 starts, and the crash therefore lands
# between two known points. After the restart, step 1's lines must NOT appear again:
# that absence is what proves the replay used the recorded result instead of re-running
# the node. Put the slow node first and the crash lands before anything has completed,
# the run restarts from nothing, and the demo proves nothing at all.
def check_venues(state: PlannerState) -> dict:
    print(f">>> STEP 1: Checking venue availability for '{state['topic']}'...", flush=True)
    result = "Grand Ballroom available on March 15 (2PM-6PM, 6PM-11PM)"
    print(f">>> STEP 1 COMPLETE: {result}", flush=True)
    return {"results": state["results"] + [result]}


def compare_options(state: PlannerState) -> dict:
    # The delay is what makes the crash aimable. Without it all three nodes finish in
    # single-digit milliseconds and there is no window for POST /crash/kill to land in.
    delay = int(os.environ.get("CRASH_DELAY_SECONDS", "30"))
    print(f">>> STEP 2: Comparing venue options over ~{delay}s. KILL THE APP NOW to test "
          "crash recovery (POST /crash/kill, or kill -9). It resumes on restart.", flush=True)
    time.sleep(delay)
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
    name="schedule-planner",
)

# Used to wait on a run by its instance ID, which is what lets a re-issued request
# attach to the run started before the crash instead of starting a second one.
# DaprWorkflowGraphRunner.run_async always schedules, so it cannot express "attach
# to an existing instance" and this client is the only way to do it.
#
# Note where dapr-ext-workflow comes from: it is not in pyproject.toml. It arrives
# as an unconditional dependency of diagrid 0.4.3, the same package that provides
# DaprWorkflowGraphRunner above, so it is always installed here. Declaring it
# directly would be more honest but would force a uv.lock regeneration. If a future
# diagrid release drops it, this file breaks with an ImportError and no manifest
# change will have warned anyone.
workflow_client = DaprWorkflowClient()

# The wait budget for the blocking POST /crash/run. Kept comfortably above step 2's
# default 30s so the first call is still blocked when you kill the app.
CRASH_WAIT_SECONDS = 120


# ── FastAPI server ───────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    runner.start()
    # The runner registers with Catalyst on a background thread. Give it a moment before
    # announcing readiness, so the first request cannot arrive at an unregistered worker.
    await asyncio.sleep(1)
    print("Runner started, ready to accept requests", flush=True)
    yield
    runner.shutdown()


app = FastAPI(lifespan=lifespan)


class CrashRunRequest(BaseModel):
    # Optional so the handler can reject a missing id with the same 400 and the same body
    # as the sibling crash demos. A required pydantic field would produce FastAPI's own
    # 422 in a different shape instead.
    id: Optional[str] = None
    topic: str = "company gala on March 15"


def crash_response(instance_id: str, result=None, message=None, status_code: int = 200):
    """The one response shape every crash demo in this repo returns. All three fields are
    always present: a 200 carries `result`, while a 400, a 202 and a 500 carry `message`."""
    return JSONResponse(
        status_code=status_code,
        content={"id": instance_id, "result": result, "message": message},
    )


# Run the graph under a workflow instance ID you choose, and block until it finishes
# POST /crash/run
# Body: { "id": "gala-42", "topic": "company gala on March 15" }
# Returns: 200 with the graph output, or 202 with the ID if the wait budget elapses
@app.post("/crash/run")
async def crash_run(req: CrashRunRequest):
    if not req.id or not req.id.strip():
        return crash_response(req.id, message="id is required", status_code=400)

    try:
        existing = await asyncio.to_thread(workflow_client.get_workflow_state, req.id)
        if existing is None:
            # run_async schedules the workflow and then polls it. Advance it once so the
            # scheduling happens, then close it: the wait below is the blocking part, and it
            # is the same wait a re-issued request uses.
            stream = runner.run_async(
                input={"topic": req.topic, "results": []},
                thread_id=req.id,
                workflow_id=req.id,
            )
            await anext(stream)
            await stream.aclose()
        else:
            print(f">>> Attaching to the existing run {req.id} instead of starting a second one",
                  flush=True)

        # to_thread, not a direct call: this blocks for the length of step 2, and blocking
        # the event loop here would leave POST /crash/kill unanswerable.
        state = await asyncio.to_thread(
            workflow_client.wait_for_workflow_completion, req.id,
            timeout_in_seconds=CRASH_WAIT_SECONDS,
        )
    except TimeoutError:
        # Not a failure: the run is still going. Re-issue the same request with the same
        # ID to attach and collect the result.
        return crash_response(
            req.id,
            message=f"still running as {req.id}, re-issue POST /crash/run "
                    "with the same id to attach",
            status_code=202,
        )
    except Exception as e:
        print(f">>> Error running the crash-recovery run {req.id}: {e}", flush=True)
        return crash_response(req.id, message=str(e), status_code=500)

    # The wait returns on ANY terminal state, and a failed or terminated run has no output at
    # all, so read the status before reading the output. json.loads(None) would otherwise
    # raise and surface as a JSON decoder error rather than the real cause.
    status_str = str(state.runtime_status) if state else ""
    if "COMPLETED" not in status_str:
        print(f">>> Crash-recovery run {req.id} ended as {status_str}", flush=True)
        return crash_response(
            req.id, message=f"run {req.id} ended as {status_str}", status_code=500
        )

    # `result` carries the graph's final output, matching the `result` field of the crash
    # demos in the workflow quickstarts. The graph's own `status` key is bookkeeping inside
    # that payload and is not part of this endpoint's contract.
    payload = json.loads(state.serialized_output)
    return crash_response(req.id, result=payload.get("output", payload))


# Simulate a crash: kill this process outright, like SIGKILL. Demo only.
# POST /crash/kill
# Returns: nothing. The process is gone before a response can be written, so the caller
# sees a connection reset.
@app.post("/crash/kill")
async def crash_kill():
    print(">>> /crash/kill: killing this process to simulate a worker crash", flush=True)
    # os._exit, not sys.exit: sys.exit raises SystemExit, which unwinds through uvicorn and
    # runs the shutdown paths on the way out. That is a controlled exit, which is the
    # opposite of what this demo simulates.
    os._exit(1)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("APP_PORT", "8001")))

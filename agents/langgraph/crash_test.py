import os
import asyncio
import json
import threading
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


# Seconds into the run at which POST /crash/run has armed the app to kill itself, or None
# when nothing is armed. Set by arm_self_kill below and read only to compose step 2's line,
# which has to name the wait the reader actually gets: with a self-kill armed the node never
# reaches the end of its sleep, so announcing that sleep on its own puts a number in the log
# that nothing honours.
#
# A plain module-level value is enough. One armed kill takes the whole process down, so there
# is nothing to key by run, and the fresh process after the restart starts at None again,
# which is right: nothing is armed on the replay.
_self_kill_seconds: Optional[int] = None


def compare_options(state: PlannerState) -> dict:
    # The delay is what makes the crash aimable. Without it all three nodes finish in
    # single-digit milliseconds and there is no window for POST /crash/kill to land in.
    delay = int(os.environ.get("CRASH_DELAY_SECONDS", "30"))
    # Two messages, because the reader's next move differs. Un-armed, the window is theirs to
    # aim at and they have to crash the app themselves. Armed, the app does that for them at a
    # known point, so the instruction would be wrong and the ~delay would be read as the wait.
    if _self_kill_seconds:
        print(f">>> STEP 2: Comparing venue options over ~{delay}s, but this process kills "
              f"itself {_self_kill_seconds}s into the run, as asked by kill_after_seconds. "
              "It resumes on restart.", flush=True)
    else:
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
    # Seconds after scheduling at which the app kills ITSELF, so the crash needs neither a
    # second caller nor a human racing step 2's window.
    #
    # Optional, and absent means today's behaviour exactly: nothing is armed and you crash
    # the app yourself with POST /crash/kill from another terminal. Ignored on the attach
    # branch, because a re-issue is how you collect the result of a run that survived.
    kill_after_seconds: Optional[int] = None


def arm_self_kill(delay_seconds: int) -> None:
    """Kill this process `delay_seconds` from now, on a background thread.

    What lets the demo run in two terminals instead of three. POST /crash/run blocks for the
    length of step 2, so the shell that starts a run cannot also stop the app, and the kill
    has always needed a terminal of its own. Arming it here removes that terminal AND the
    race: the crash lands at a known point inside the window rather than wherever the
    reader's reflexes put it.

    The same os._exit(1) that /crash/kill uses, deliberately. A gentler exit would make this
    a controlled shutdown wearing a crash's name.

    A plain daemon thread rather than an asyncio task: os._exit needs no event loop, and a
    daemon thread can never hold the process open if the reader Ctrl+Cs during the countdown.
    """
    # Tell step 2, so the line it prints names this delay rather than the sleep it was going
    # to take. That sleep is the number the reader used to see, and it is not the one they
    # wait: the app dies partway through it.
    #
    # Armed just after the schedule, and step 2 cannot normally log before that: the worker
    # has to be handed the work item and run step 1 first. If it ever did win the race the
    # line would read as though nothing were armed, which is a stale message, not a break.
    global _self_kill_seconds
    _self_kill_seconds = delay_seconds

    def _kill() -> None:
        time.sleep(delay_seconds)
        print(
            f">>> crash: killing this process {delay_seconds}s into the run, as asked by kill_after_seconds",
            flush=True,
        )
        os._exit(1)

    threading.Thread(target=_kill, daemon=True).start()


def crash_response(instance_id: str, result=None, message=None, status_code: int = 200):
    """The one response shape every crash demo in this repo returns. All three fields are
    always present: a 200 carries `result`, while a 400, a 202 and a 500 carry `message`."""
    return JSONResponse(
        status_code=status_code,
        content={"id": instance_id, "result": result, "message": message},
    )


# Run the graph under a workflow instance ID you choose, and block until it finishes
# POST /crash/run
# Body: { "id": "gala-42", "topic": "company gala on March 15", "kill_after_seconds": 8 }
# Returns: 200 with the graph output, or 202 with the ID if the wait budget elapses
#
# `kill_after_seconds` is optional. Send it and the app crashes itself that many seconds in,
# so the whole demo runs in two terminals with no window to aim at; leave it out and nothing
# changes, and you crash the app yourself from a second terminal with POST /crash/kill.
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
            # Armed here and nowhere else: only on the branch that actually scheduled a run.
            # On the attach branch below it would kill the app every time the reader tried to
            # read the answer.
            if req.kill_after_seconds and req.kill_after_seconds > 0:
                arm_self_kill(req.kill_after_seconds)
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

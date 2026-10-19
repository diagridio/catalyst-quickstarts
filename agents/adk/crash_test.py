import os
import asyncio
import json
import threading
import time
from typing import Optional
from contextlib import asynccontextmanager

import uvicorn
from dapr.ext.workflow import DaprWorkflowClient
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import FunctionTool

from diagrid.agent.adk import DaprWorkflowAgentRunner


# ── Tools (each becomes a Dapr workflow activity) ────────────
# The tool ORDER is the design, not an accident. Step 1 finishes in milliseconds, so
# Catalyst has persisted its result before step 2 starts, and the crash therefore lands
# between two known points. After the restart, step 1's lines must NOT appear again:
# that absence is what proves the replay used the recorded result instead of re-running
# the tool. Put the slow tool first and the crash lands before anything has completed,
# the run restarts from nothing, and the demo proves nothing at all.
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


# Seconds into STEP 2's own run at which the app should kill itself, or None when nothing is
# asked for. Set by note_self_kill below, then read by step_two_compare both to compose its log
# line (which has to name the wait the reader actually gets) and to start the timer.
#
# A plain module-level value is enough. One armed kill takes the whole process down, so there
# is nothing to key by run, and the fresh process after the restart starts at None again. That
# reset is what makes the replay safe: the resumed step 2 re-runs from the start, and it must
# not arm a second kill when it does.
_self_kill_seconds: Optional[int] = None


def step_two_compare(data: str) -> str:
    """Compare entertainment options. This is the second step.

    Args:
        data: The data from step one to compare.

    Returns:
        A comparison of the options.
    """
    # The delay is what makes the crash aimable. Without it all three tools finish in
    # milliseconds and there is no window for POST /crash/kill to land in.
    delay = int(os.environ.get("CRASH_DELAY_SECONDS", "10"))
    # Two messages, because the reader's next move differs. Un-armed, the window is theirs to
    # aim at and they have to crash the app themselves. Armed, the app does that for them at a
    # known point, so the instruction would be wrong and the ~delay would be read as the wait.
    #
    # Read AND clear, so one recorded request arms exactly one execution. A call that records the
    # field but never gets here would otherwise leak the value into the next run in the same
    # process and kill an app that had never asked for it. The GIL makes this pair atomic enough.
    global _self_kill_seconds
    armed, _self_kill_seconds = _self_kill_seconds, None
    if armed:
        print(f">>> TOOL 2: Comparing options over ~{delay}s, but this process kills "
              f"itself {armed}s into the run, as asked by kill_after_seconds. "
              "It resumes on restart.", flush=True)
        # Armed here, where step 2 actually starts, and not at the request. This tool is a
        # durable activity, so it runs on a genuine first execution and not on an attach, and
        # the fresh process's None is what stops the resumed tool arming a second kill. It also
        # starts the clock after the model turn and step 1 rather than before them, so the
        # budget is measured against this tool's own sleep.
        _arm_self_kill(armed)
    else:
        print(f">>> TOOL 2: Comparing options over ~{delay}s. KILL THE APP NOW to test "
              "crash recovery (POST /crash/kill, or kill -9). It resumes on restart.", flush=True)
    time.sleep(delay)
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
    model=LiteLlm(model="openai/gpt-4o-mini"),
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
runner = DaprWorkflowAgentRunner(name="entertainment-planner", agent=agent, max_iterations=10)


# Used to wait on a run by its instance ID, which is what lets a re-issued request
# attach to the run started before the crash instead of starting a second one.
# DaprWorkflowAgentRunner.run_async always schedules, so it cannot express "attach
# to an existing instance" and this client is the only way to do it.
#
# Note where dapr-ext-workflow comes from: it is not in pyproject.toml. It arrives
# as an unconditional dependency of diagrid 0.5.0, the same package that provides
# DaprWorkflowAgentRunner above, so it is always installed here. Declaring it
# directly would be more honest but would force a uv.lock regeneration. If a future
# diagrid release drops it, this file breaks with an ImportError and no manifest
# change will have warned anyone.
workflow_client = DaprWorkflowClient()

# The wait budget for the blocking POST /crash/run. Kept comfortably above step 2's
# default 10s so the first call is still blocked when you kill the app.
# Overridable through CRASH_WAIT_SECONDS, which is how an automated run exercises the
# 202 branch without waiting two minutes for it.
CRASH_WAIT_SECONDS = int(os.environ.get("CRASH_WAIT_SECONDS", "120"))


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


# Health check endpoint - verifies the service is running
# GET /
# Returns: { "message": "Health check passed. Everything is running smoothly!" }
#
# It answers only once the lifespan above has run, so a 200 here means the
# workflow runner registered with Catalyst, not merely that the port is open.
@app.get("/")
async def read_root():
    return {"message": "Health check passed. Everything is running smoothly!"}


class CrashRunRequest(BaseModel):
    # Optional so the handler can reject a missing id with the same 400 and the same body
    # as the sibling crash demos. A required pydantic field would produce FastAPI's own
    # 422 in a different shape instead.
    id: Optional[str] = None
    prompt: str = "Find entertainment for a corporate holiday party"
    # Seconds after scheduling at which the app kills ITSELF, so the crash needs neither a
    # second caller nor a human racing step 2's window.
    #
    # Optional, and absent means today's behaviour exactly: nothing is armed and you crash
    # the app yourself with POST /crash/kill from another terminal. Ignored on the attach
    # branch, because a re-issue is how you collect the result of a run that survived.
    kill_after_seconds: Optional[int] = None


def note_self_kill(delay_seconds: Optional[int]) -> None:
    """Record how far into step 2 this process should kill itself, for step 2 to act on when it
    actually runs. Recording only: no timer starts here. Pass None to disarm.

    The timer starts inside the tool rather than at the request, for two reasons. The tool is a
    durable activity, so it is the one thing that runs on a genuine first execution and not on
    an attach: an attach to a finished run replays the recorded result instead of re-invoking
    it. And it starts the clock after the model turn and step 1, so the budget is measured
    against step 2's own sleep instead of having to cover everything that precedes it. A slow
    model provider used to be able to kill the app before any tool had completed, which leaves
    the replay with nothing to show.
    """
    global _self_kill_seconds
    _self_kill_seconds = delay_seconds


def _arm_self_kill(delay_seconds: int) -> None:
    """Kill this process `delay_seconds` from now, on a background thread.

    What lets the demo run in two terminals instead of three. POST /crash/run blocks for the
    length of step 2, so the shell that starts a run cannot also stop the app, and the kill
    has always needed a terminal of its own. Arming it removes that terminal AND the race: the
    crash lands at a known point inside the window rather than wherever the reader's reflexes
    put it.

    The same os._exit(1) that /crash/kill uses, deliberately. A gentler exit would make this
    a controlled shutdown wearing a crash's name.

    A plain daemon thread rather than an asyncio task: os._exit needs no event loop, and a
    daemon thread can never hold the process open if the reader Ctrl+Cs during the countdown.
    """
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


# Run the agent under a workflow instance ID you choose, and block until it finishes
# POST /crash/run
# Body: { "id": "party-42", "prompt": "Find entertainment...", "kill_after_seconds": 8 }
# Returns: 200 with the agent's final output, or 202 with the ID if the wait budget elapses
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
            # scheduling happens (its first event is workflow_started), then close it: the
            # wait below is the blocking part, and it is the same wait a re-issued request uses.
            stream = runner.run_async(
                user_message=req.prompt,
                session_id=req.id,
                workflow_id=req.id,
            )
            await anext(stream)
            await stream.aclose()
            # Runs after scheduling, which is safe: step 2 only starts after a model turn, so
            # the note is always in place before anything reads it.
            # Recorded here and nowhere else: only on the branch that actually scheduled a run,
            # so an attaching call cannot even leave a note behind. Recording only, though. The
            # timer starts inside step 2, which is the one place that runs on a first execution
            # and not on an attach. See note_self_kill.
            # Recorded on every scheduling call, and one without the field records None, which
            # disarms. The clear matters because a value left set by an earlier call would be
            # consumed by this run's step 2 and kill an app that had never asked for it.
            note_self_kill(
                req.kill_after_seconds
                if req.kill_after_seconds and req.kill_after_seconds > 0
                else None
            )
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

    # The workflow itself COMPLETED, but the agent may have failed inside it: an LLM error
    # gives status "error", and running out of iterations gives "max_iterations_reached",
    # both with `error` set and no final_response. Surface that instead of a 200 with a
    # null result.
    payload = json.loads(state.serialized_output)
    if payload.get("status") != "completed" or payload.get("error"):
        reason = payload.get("error") or payload.get("status")
        print(f">>> Crash-recovery run {req.id} failed: {reason}", flush=True)
        return crash_response(
            req.id, message=f"run {req.id} failed: {reason}", status_code=500
        )

    # `result` carries whatever the runner returns as the final agent output, which is the
    # `final_response` text of the serialized AgentWorkflowOutput, matching the `result` field
    # of the crash demos in the workflow quickstarts. The other keys (messages, iterations,
    # status) are bookkeeping inside that payload and are not part of this endpoint's contract.
    return crash_response(req.id, result=payload.get("final_response"))


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

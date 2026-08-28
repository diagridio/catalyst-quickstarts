"""
Dapr Workflow Quickstart - Python Implementation

This application demonstrates a simple order processing workflow using Dapr Workflows.
The workflow includes inventory checking, payment processing, and inventory updates.

Workflow Steps:
1. Notify user of order receipt
2. Reserve inventory for the order
3. Process payment for the order
4. Update inventory after successful payment
5. Notify user of completion

For more information, visit: https://docs.diagrid.io/catalyst/quickstart/workflow
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
import json
import logging
import os
import threading
import time
import uvicorn
import uuid
from dapr.ext.workflow import WorkflowRuntime, DaprWorkflowClient
from workflow import order_processing_workflow, notify_activity, reserve_inventory_activity, process_payment_activity, update_inventory_activity, crash_recovery_workflow, commit_reservation_activity
from model import OrderPayload, CrashRunRequest

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Starting workflow runtime...")

# Initialize and configure the Dapr workflow runtime
workflow_runtime = WorkflowRuntime()
workflow_runtime.register_workflow(order_processing_workflow)
workflow_runtime.register_workflow(crash_recovery_workflow)
workflow_runtime.register_activity(notify_activity)
workflow_runtime.register_activity(reserve_inventory_activity)
workflow_runtime.register_activity(process_payment_activity)
workflow_runtime.register_activity(update_inventory_activity)
workflow_runtime.register_activity(commit_reservation_activity)
workflow_runtime.start()

# Initialize the Dapr workflow client for API operations
workflow_client = DaprWorkflowClient()

# Health check endpoint - verifies the service is running
# GET /
# Returns: { "message": "Health check passed. Everything is running smoothly!" }
@app.get('/')
async def read_root():
    health_message = "Health check passed. Everything is running smoothly!"
    logger.info("Health check result: %s", health_message)
    return {"message": health_message}

# Start new workflow - creates and schedules a new order processing workflow
# POST /workflow/start
# Body: { "name": "Car", "quantity": 2 }
# Returns: { "instance_id": "uuid" }
@app.post("/workflow/start")
def start_workflow(order: OrderPayload):
    try:
        instance_id = str(uuid.uuid4())
        logger.info(f"Starting workflow for order {instance_id}: {order.quantity} {order.name}")
        
        workflow_client.schedule_new_workflow(workflow=order_processing_workflow, input=order.dict(), instance_id=instance_id)
        
        logger.info(f"Workflow execution started successfully for order {instance_id}")
        return {"instanceId": instance_id}
    except Exception as e:
        logger.error(f"Error starting workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Get workflow status - retrieves the current state of a workflow instance
# GET /workflow/status/{instance_id}
# Returns: WorkflowState object or 204 if not found
@app.get("/workflow/status/{instance_id}")
def get_workflow_status(instance_id: str):
    try:
        state = workflow_client.get_workflow_state(instance_id=instance_id)
        if not state:
            logger.info(f"Workflow with id {instance_id} does not exist")
            return Response(status_code=204)
        logger.info(f"Retrieved workflow status for {instance_id}.")
        logger.info(f"Workflow Runtime Status is: {state.runtime_status}")
        status_str = str(state.runtime_status)
        return {
            "exists": True,
            "isWorkflowRunning": "RUNNING" in status_str,
            "isWorkflowCompleted": "COMPLETED" in status_str,
            "createdAt": state.created_at.isoformat() if state.created_at else None,
            "lastUpdatedAt": state.last_updated_at.isoformat() if state.last_updated_at else None,
            "runtimeStatus": state.runtime_status.value if hasattr(state.runtime_status, "value") else state.runtime_status,
            "failureDetails": state.failure_details,
        }
    except Exception as e:
        logger.error(f"Error occurred while getting the status of the workflow: {instance_id}. Exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Terminate workflow - stops a running workflow instance
# POST /workflow/terminate/{instance_id}
# Returns: Updated WorkflowState object
@app.post("/workflow/terminate/{instance_id}")
def terminate_workflow(instance_id: str):
    try:
        # Check current state first to provide accurate messaging
        current_state = workflow_client.get_workflow_state(instance_id=instance_id)
        if not current_state:
            logger.info(f"Workflow with id {instance_id} does not exist")
            return Response(status_code=204)
        
        # If already in a terminal state, just return the current state
        # The status comes as WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, etc.
        status_str = str(current_state.runtime_status)
        if "COMPLETED" in status_str or "FAILED" in status_str or "TERMINATED" in status_str:
            logger.info(f"Workflow with id {instance_id} is already in terminal state {current_state.runtime_status}")
            return current_state
        
        # Terminate the workflow
        workflow_client.terminate_workflow(instance_id=instance_id)
        logger.info(f"Terminated workflow with id {instance_id}.")
        
        # Return the updated state
        updated_state = workflow_client.get_workflow_state(instance_id=instance_id)
        return updated_state
    except Exception as e:
        logger.error(f"Error occurred while terminating the workflow: {instance_id}. Exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── Crash-recovery demo ──────────────────────────────────────────────────────
# The wait budget for the blocking /crash/run. Kept comfortably above the slow
# activity's default 30s so the first call is still blocked when you kill the app.
# Overridable through CRASH_WAIT_SECONDS, which is how the e2e suite exercises the
# 202 branch without waiting two minutes for it.
CRASH_WAIT_SECONDS = int(os.environ.get('CRASH_WAIT_SECONDS', '120'))

def arm_self_kill(delay_seconds: int):
    """Kill this process `delay_seconds` from now, on a background thread.

    This is what lets the demo run in two terminals instead of three. /crash/run blocks for
    the length of the slow activity, so the shell that starts a run cannot also stop the app,
    and the kill has always needed a terminal of its own. Arming it here removes that
    terminal AND the race: the crash lands at a known point inside the window rather than
    wherever the reader's reflexes put it.

    Deliberately the same os._exit(1) that /crash/kill uses. A gentler exit would make this a
    controlled shutdown wearing a crash's name, which is the one thing this demo must not do.

    daemon=True so the timer can never hold the process open: a Ctrl+C during the countdown
    should still end the app rather than wait for a kill nobody wants any more.
    """
    def _kill():
        time.sleep(delay_seconds)
        logger.warning(
            f'>>> crash: killing this process {delay_seconds}s into the run, as asked by kill_after_seconds'
        )
        os._exit(1)

    threading.Thread(target=_kill, daemon=True).start()

def crash_response(instance_id: str, result=None, message=None, status_code: int = 200):
    """The one response shape every crash demo in this repo returns. All three fields are
    always present: a 200 carries `result`, while a 202 and a 500 carry `message` instead."""
    return JSONResponse(
        status_code=status_code,
        content={"id": instance_id, "result": result, "message": message},
    )

# Run the crash-recovery workflow under an instance ID you choose
# POST /crash/run
# Body: { "id": "trip-42", "reference": "ABC123", "kill_after_seconds": 8 }
# Returns: 200 with the confirmation, or 202 with the ID if the wait budget elapses
#
# `kill_after_seconds` is optional. Send it and the app crashes itself that many seconds in,
# so the whole demo runs in two terminals with no window to aim at; leave it out and nothing
# changes, and you crash the app yourself from a second terminal with POST /crash/kill.
#
# Defined with `def`, not `async def`: it blocks for the length of the slow
# activity, and FastAPI runs a plain `def` handler on a worker thread. An
# `async def` here would block the event loop, so the /crash/kill request the
# demo depends on could never be served.
@app.post("/crash/run")
def crash_run(req: CrashRunRequest):
    if not req.id or not req.id.strip():
        return crash_response(req.id, message="id is required", status_code=400)

    try:
        state = workflow_client.get_workflow_state(instance_id=req.id)
        if state is None:
            logger.info(f"Starting crash-recovery workflow {req.id} for reservation {req.reference}")
            workflow_client.schedule_new_workflow(
                workflow=crash_recovery_workflow, input=req.reference, instance_id=req.id
            )
            # Armed here and nowhere else: only on the branch that actually scheduled a run,
            # and only after the schedule call returned. On the attach branch below it would
            # kill the app every time the reader tried to read the answer.
            if req.kill_after_seconds and req.kill_after_seconds > 0:
                arm_self_kill(req.kill_after_seconds)
        else:
            # The instance already exists, so this call attaches to it rather than
            # booking a second time. That is the whole point of a caller-owned ID.
            logger.info(f"Attaching to existing crash-recovery workflow {req.id}")

        completed = workflow_client.wait_for_workflow_completion(
            req.id, timeout_in_seconds=CRASH_WAIT_SECONDS
        )

        # The wait returns on ANY terminal state, and a failed or terminated instance has no
        # output at all, so read the status before reading the output. json.loads(None) would
        # otherwise raise and surface as a JSON decoder error rather than the real cause.
        status_str = str(completed.runtime_status) if completed else ""
        if "COMPLETED" not in status_str:
            logger.error(f"Crash-recovery workflow {req.id} ended as {status_str}")
            return crash_response(
                req.id, message=f"workflow {req.id} ended as {status_str}", status_code=500
            )

        return crash_response(req.id, result=json.loads(completed.serialized_output))
    except TimeoutError:
        # Not a failure: the run is still going. Re-issue the same request with the
        # same ID to attach and collect the result.
        return crash_response(
            req.id,
            message=f"still running as {req.id}, re-issue POST /crash/run with the same id to attach",
            status_code=202,
        )
    except Exception as e:
        logger.error(f"Error running the crash-recovery workflow {req.id}: {e}")
        return crash_response(req.id, message=str(e), status_code=500)

# Simulate a crash: kill this process outright, like SIGKILL. Demo only.
# POST /crash/kill
# Returns: nothing. The process is gone before a response can be written, so the
# caller sees a connection reset.
#
# `async def`, unlike /crash/run above: os._exit needs no worker thread, and staying on the
# event loop means this can never queue behind an in-flight /crash/run for a thread.
@app.post("/crash/kill")
async def crash_kill():
    logger.warning(">>> /crash/kill: killing this process to simulate a worker crash")
    # os._exit, not sys.exit: sys.exit raises SystemExit, which unwinds through
    # uvicorn and runs the shutdown paths on the way out. That is a controlled exit,
    # which is the opposite of what this demo simulates.
    os._exit(1)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)


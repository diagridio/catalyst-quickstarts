import os
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from claude_agent_sdk import ClaudeAgentOptions, tool

from diagrid.agent.claude_agents import DaprWorkflowAgentRunner


# ── Tools (each becomes a Dapr workflow activity) ────────────
@tool("step_one_search", "Search for photography options. This is the first step.", {"event_type": str})
async def step_one_search(args):
    print(f">>> TOOL 1: Searching photography for '{args['event_type']}'...", flush=True)
    print(f">>> TOOL 1 COMPLETE: Found 3 {args['event_type']} photography options", flush=True)
    text = f"Found 3 {args['event_type']} photography options. Now call step_two_compare."
    return {"content": [{"type": "text", "text": text}]}


@tool("step_two_compare", "Compare photography options. This is the second step.", {"data": str})
async def step_two_compare(args):
    print(">>> TOOL 2: Comparing options...", flush=True)
    os._exit(1)  # 💥 Simulates a crash — comment out this line before the second run
    print(">>> TOOL 2 COMPLETE: Candid Frames is the best value", flush=True)
    text = "Candid Frames is the best value. Now call step_three_confirm."
    return {"content": [{"type": "text", "text": text}]}


@tool("step_three_confirm", "Confirm the photography selection. This is the third and final step.", {"selection": str})
async def step_three_confirm(args):
    print(">>> TOOL 3: Confirming selection...", flush=True)
    print(">>> TOOL 3 COMPLETE: Photography confirmed with Candid Frames", flush=True)
    text = "Photography confirmed with Candid Frames. All steps complete!"
    return {"content": [{"type": "text", "text": text}]}


# ── Agent ────────────────────────────────────────────────────
options = ClaudeAgentOptions(
    system_prompt="""Execute exactly three tools in sequence:
    1. First call step_one_search with the event type
    2. Then call step_two_compare with the output from step 1
    3. Finally call step_three_confirm with the output from step 2
    Do NOT skip any steps. Always call all three tools.""",
    model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
)

# ── Durable workflow runner ──────────────────────────────────
runner = DaprWorkflowAgentRunner(
    name="crash-recovery-demo",
    options=options,
    tools=[step_one_search, step_two_compare, step_three_confirm],
    max_iterations=10,
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

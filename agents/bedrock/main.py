import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)


def load_secrets() -> None:
    """Copy the keys of the JSON secret named by AGENT_SECRET_ARN into the environment.

    On AgentCore the Catalyst App ID token and the OpenAI key live in AWS Secrets
    Manager, and the runtime's execution role is allowed to read that one secret.
    Values already in the environment win, so `diagrid dev run` and `docker run -e`
    work without a secret.
    """
    secret_arn = os.environ.get("AGENT_SECRET_ARN")
    if not secret_arn:
        return

    import boto3

    region = secret_arn.split(":")[3]
    client = boto3.client("secretsmanager", region_name=region)
    secret = json.loads(client.get_secret_value(SecretId=secret_arn)["SecretString"])
    for key, value in secret.items():
        os.environ.setdefault(key, value)


# The Dapr SDK reads DAPR_GRPC_ENDPOINT and DAPR_API_TOKEN when it is first
# imported, so the secrets must be in the environment before the imports below.
load_secrets()

import grpc
import uvicorn
from dapr.ext.workflow import DaprWorkflowClient
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from strands import Agent, tool
from strands.models.openai import OpenAIModel
from diagrid.agent.strands import DaprWorkflowAgentRunner
from diagrid.agent.core.state import DaprStateStore


@tool
def calculate_budget(items: str) -> str:
    """Calculate total budget from a comma-separated list of cost items."""
    return (
        "Budget breakdown:\n"
        "- Venue: $3,500\n"
        "- Catering: $2,250\n"
        "- Entertainment: $1,500\n"
        "- Decorations: $800\n"
        "- Miscellaneous: $500\n"
        "Total: $8,550\n"
        "Recommended buffer (15%): $1,283\n"
        "Grand Total: $9,833"
    )


# Any OpenAI-compatible provider works: set OPENAI_BASE_URL to its endpoint and
# OPENAI_MODEL to a model it serves. Empty values fall back to OpenAI's defaults.
model = OpenAIModel(
    client_args={"base_url": os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"},
    model_id=os.environ.get("OPENAI_MODEL") or "gpt-4o-mini",
)

agent = Agent(
    model=model,
    tools=[calculate_budget],
    system_prompt="You are a budget analyst specializing in event planning. When asked to estimate costs, use the calculate_budget tool with a comma-separated list of cost items. Return the full budget breakdown with line items, totals, and recommended buffer. Always call the tool before responding. "
    "The user message is the conversation so far, as lines starting with 'User:' and 'Assistant:'. Answer the last 'User:' request.",
)

runner = DaprWorkflowAgentRunner(
    name="budget-planner",
    agent=agent,
    state_store=DaprStateStore(store_name="kvstore"),
)

# Each session runs one task at a time, as the workflow instance named after the
# session ID. Dapr refuses to start an instance whose ID is still running, which is
# what makes a second task busy, and it keeps a finished instance's output until the
# next task with that ID replaces it. That stored output is the session's last
# result, so it survives a restart of this process.

# Waits on a run by its instance ID. runner.run_async always schedules a new run,
# so collecting the result of a run that is already going needs this client.
workflow_client = DaprWorkflowClient()

# The transcript passed to the model keeps its most recent characters up to this size.
MAX_HISTORY_CHARS = 20000


def with_history(previous, payload: str) -> str:
    """Build the task for a new run as the session's transcript plus the new request.

    WORKAROUND: the diagrid 0.5.0 Strands runner starts every run with only the
    task as its message list, so the agent remembers nothing between runs. This
    carries the conversation in the task text instead: the previous run's task
    is already the transcript up to that run, so adding its answer and the new
    request gives the whole conversation, stored in Catalyst with the run.
    TODO: remove once the Strands runner in the diagrid SDK loads and saves the
    session's messages itself, as activities at the start and end of the workflow.
    """
    request = f"User: {payload}"
    if previous is None:
        return request
    transcript = json.loads(previous.serialized_input or "{}").get("task", "")
    if previous.runtime_status.name == "COMPLETED":
        answer = json.loads(previous.serialized_output or "{}").get("result")
        if answer:
            transcript += f"\nAssistant: {answer}"
    transcript = f"{transcript}\n{request}"
    if len(transcript) > MAX_HISTORY_CHARS:
        # Drop the oldest text, starting from the next whole line.
        tail = transcript[-MAX_HISTORY_CHARS:]
        transcript = tail[tail.find("\n") + 1:]
    return transcript


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Connects the workflow worker to Catalyst for as long as the server runs.
    runner.start()
    try:
        yield
    finally:
        runner.shutdown()


# AgentCore Runtime calls POST /invocations and GET /ping on port 8080.
app = FastAPI(lifespan=lifespan)


@app.get("/ping")
async def ping() -> dict:
    return {"status": "Healthy"}


def reply(session_id, status_code: int = 200, **fields) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"instance_id": session_id, **fields})


@app.post("/invocations")
async def invocations(request: Request):
    """Run the payload as the agent's task, or, with an empty payload, return the
    result of the session's current or last run. Either way, wait for the run to end."""
    payload = (await request.body()).decode().strip()
    # AgentCore sends its runtime session ID in this header.
    session_id = request.headers.get("x-amzn-bedrock-agentcore-runtime-session-id")
    if not session_id:
        return reply(session_id, 400, message="a session ID is required")

    if payload:
        previous = await asyncio.to_thread(workflow_client.get_workflow_state, session_id)
        task = with_history(previous, payload)
        try:
            # run_async schedules the workflow on its first step. The wait below
            # is shared with requests that only collect the result.
            stream = runner.run_async(task, session_id, workflow_id=session_id)
            await anext(stream)
            await stream.aclose()
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.ALREADY_EXISTS:
                return reply(session_id, 409, message="busy: a task is still running in this session")
            raise
    elif await asyncio.to_thread(workflow_client.get_workflow_state, session_id) is None:
        # Nothing has run in this session, so there is no result to return.
        return Response()

    state = await asyncio.to_thread(workflow_client.wait_for_workflow_completion, session_id)

    status = state.runtime_status.name
    if status != "COMPLETED":
        return reply(session_id, 500, status=status, message=f"the run ended as {status}")
    # The agent reports a failed model call as a result starting with "Error: ".
    output = json.loads(state.serialized_output)
    if not output.get("result") or output["result"].startswith("Error: "):
        return reply(session_id, 500, status=status, message=output.get("result") or "the agent gave no answer")
    return reply(session_id, status=status, result=output["result"], tool_calls=output.get("tool_calls", []))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("APP_PORT", "8080")))

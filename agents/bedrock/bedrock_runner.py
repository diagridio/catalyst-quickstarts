"""Serve a diagrid workflow agent runner on Amazon Bedrock AgentCore Runtime.

Import this module before anything that imports the Dapr SDK: importing it loads
the secrets the SDK reads from the environment when it is first imported.
"""

import json
import os


def load_secrets() -> None:
    """Copy the keys of the JSON secret named by AGENT_SECRET_ARN into the environment.

    On AgentCore the Catalyst App ID token and the model provider's key live in AWS
    Secrets Manager, and the runtime's execution role is allowed to read that one
    secret. Values already in the environment win, so `diagrid dev run` and
    `docker run -e` work without a secret.
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

import asyncio
import logging
from contextlib import asynccontextmanager

import grpc
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from diagrid.agent.core.workflow.runner import BaseWorkflowRunner
from diagrid.agent.strands import DaprWorkflowAgentRunner as StrandsRunner

# AgentCore sends its runtime session ID in this header.
SESSION_HEADER = "x-amzn-bedrock-agentcore-runtime-session-id"

# The workflow states of a run that has not ended.
UNFINISHED = ("RUNNING", "PENDING")

# The transcript passed to the model keeps its most recent characters up to this size.
MAX_HISTORY_CHARS = 20000

# Tells the model how to read the task with_history builds: the whole conversation
# in one message, of which only the last request is to be answered. The workflow
# reads the agent's system prompt in the worker, so the agent definition adds this
# to it, in every process.
TRANSCRIPT_INSTRUCTION = (
    "The user message is the conversation so far, as lines starting with 'User:' "
    "and 'Assistant:'. Answer the last 'User:' request."
)


class StrandsAdapter:
    """What BedrockRunner needs to know about diagrid's runner for Strands agents,
    diagrid.agent.strands.DaprWorkflowAgentRunner.

    A run takes the task as text, stores it as {"task": ...} in the
    workflow input, and stores the agent's answer as {"result": ...} in its output.
    """

    def start(self, runner, task: str, session_id: str):
        return runner.run_async(task, session_id, workflow_id=session_id)

    def task(self, state) -> str:
        return json.loads(state.serialized_input).get("task", "")

    def answer(self, state):
        return json.loads(state.serialized_output).get("result")


# The runner types BedrockRunner can serve. Supporting another framework means
# adding an adapter with the same three methods for its runner type.
ADAPTERS = {StrandsRunner: StrandsAdapter}


def with_history(adapter, previous, payload: str) -> str:
    """Build the task for a new run as the session's transcript plus the new request.

    WORKAROUND: the diagrid 0.5.3 Strands runner starts every run with only the
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
    transcript = adapter.task(previous)
    if previous.runtime_status.name == "COMPLETED":
        answer = adapter.answer(previous)
        if answer:
            transcript += f"\nAssistant: {answer}"
    transcript = f"{transcript}\n{request}"
    if len(transcript) > MAX_HISTORY_CHARS:
        # Drop the oldest text, starting from the next whole line.
        tail = transcript[-MAX_HISTORY_CHARS:]
        transcript = tail[tail.find("\n") + 1:]
    return transcript


def reply(session_id, status_code: int = 200, **fields) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"instance_id": session_id, **fields})


class BedrockRunner:
    """Serves a diagrid workflow agent runner on the AgentCore Runtime HTTP contract.

    Each session runs one task at a time, as the workflow instance named after the
    session ID. A request that arrives while the session's run is unfinished
    waits for that run and answers with its result, so a request after a restart
    resumes the interrupted run. Dapr keeps a finished instance until the next
    task with that ID replaces it. with_history builds the next task from that
    stored run, so the conversation survives a restart of this process.
    """

    def __init__(self, runner: BaseWorkflowRunner) -> None:
        adapter = next((a for t, a in ADAPTERS.items() if isinstance(runner, t)), None)
        if adapter is None:
            raise TypeError(f"BedrockRunner has no adapter for {type(runner).__module__}.{type(runner).__name__}")
        self._runner = runner
        self._adapter = adapter()
        # The session this container serves, from the last /invocations request.
        # AgentCore runs each session in its own microVM, so there is only one.
        self._session_id = None

    def serve(self, port: int | None = None) -> None:
        """Serve POST /invocations and GET /ping on 0.0.0.0, as AgentCore Runtime calls them.

        The port defaults to APP_PORT, or 8080, the port AgentCore Runtime calls.
        """
        uvicorn.run(self.app(), host="0.0.0.0", port=port or int(os.environ.get("APP_PORT", "8080")))

    def app(self) -> FastAPI:
        @asynccontextmanager
        async def lifespan(_app: FastAPI):
            # Connects to Catalyst for as long as the server runs: the workflow
            # client always, and the workflow worker unless WORKFLOW_WORKER
            # turns it off, when workers in other processes run the workflows.
            self._runner.start()
            try:
                yield
            finally:
                self._runner.shutdown()

        app = FastAPI(lifespan=lifespan)
        app.get("/ping")(self.ping)
        app.post("/invocations")(self.invocations)
        return app

    @property
    def _client(self):
        # The workflow client the runner creates in start().
        return self._runner._workflow_client

    async def ping(self) -> dict:
        # HealthyBusy keeps the AgentCore session alive while its workflow runs, even
        # when no request is waiting for it, so the idle timeout cannot stop the
        # worker in the middle of a run. A container that is not a worker has no
        # run to protect.
        if self._session_id and self._runner.is_worker:
            try:
                state = await asyncio.to_thread(self._client.get_workflow_state, self._session_id)
                if state is not None and state.runtime_status.name in UNFINISHED:
                    return {"status": "HealthyBusy"}
            except Exception:
                logging.exception("ping: could not read the workflow state of %s", self._session_id)
        return {"status": "Healthy"}

    async def invocations(self, request: Request):
        """Run the payload as the agent's task and wait for the run to end.

        If the session's run is unfinished, the payload is not run: the request
        waits for that run and answers with its result. An empty payload starts
        nothing: it answers with the result of the session's last run, waiting
        for it if it is unfinished, so a client that reconnects can collect it.
        """
        payload = (await request.body()).decode().strip()
        session_id = request.headers.get(SESSION_HEADER)
        if not session_id:
            return reply(session_id, 400, message="a session ID is required")
        self._session_id = session_id

        previous = await asyncio.to_thread(self._client.get_workflow_state, session_id)
        if not payload and previous is None:
            return reply(session_id, 400, message="a task is required: this session has no run yet")
        if payload and (previous is None or previous.runtime_status.name not in UNFINISHED):
            task = with_history(self._adapter, previous, payload)
            try:
                # The run is scheduled on the stream's first step. The wait below
                # follows it to the end.
                stream = self._adapter.start(self._runner, task, session_id)
                await anext(stream)
                await stream.aclose()
            except grpc.RpcError as e:
                # Another request started a run in this session after the read
                # above. The wait below follows that run instead.
                if e.code() != grpc.StatusCode.ALREADY_EXISTS:
                    raise

        state = await asyncio.to_thread(self._client.wait_for_workflow_completion, session_id)

        status = state.runtime_status.name
        if status != "COMPLETED":
            return reply(session_id, 500, status=status, message=f"the run ended as {status}")
        # The agent reports a failed model call as an answer starting with "Error: ".
        answer = self._adapter.answer(state)
        if not answer or answer.startswith("Error: "):
            return reply(session_id, 500, status=status, message=answer or "the agent gave no answer")
        return reply(session_id, status=status, result=answer)

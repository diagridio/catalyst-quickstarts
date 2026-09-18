import logging
import os

logging.basicConfig(level=logging.INFO)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.graph import StateGraph, START, MessagesState

from diagrid.identity import OAuthConfig, VerifiedUser
from diagrid.identity.asgi import OAuthMiddleware, verified_user
from fake_model import build_canned_model
from tools import (
    catalyst_tools,
    catalyst_tools_by_name,
    local_tools,
    local_tools_by_name,
)

LOCAL_REQUIRED_SCOPES = frozenset({"agent.invoke"})

# The offline issuer has no Catalyst project behind it, so it cannot reach an
# MCP server and the graph calls the in-process tool instead.
OFFLINE_IDENTITY = os.environ.get("DIAGRID_QUICKSTART_IDENTITY") == "local"
tools = local_tools if OFFLINE_IDENTITY else catalyst_tools
tools_by_name = local_tools_by_name if OFFLINE_IDENTITY else catalyst_tools_by_name


def build_model():
    """Real provider on request, canned model otherwise."""
    if os.environ.get("DIAGRID_QUICKSTART_MODEL") == "openai":
        from langchain_openai import ChatOpenAI

        logging.info("Using OpenAI (gpt-4.1-mini).")
        return ChatOpenAI(model="gpt-4.1-mini")

    logging.info(
        "Using the canned offline model: no API key needed and the answer is "
        "always the same. Set DIAGRID_QUICKSTART_MODEL=openai for a real provider."
    )
    return build_canned_model(offline=OFFLINE_IDENTITY)


model = build_model().bind_tools(tools)


def call_model(state: MessagesState) -> dict:
    response = model.invoke(state["messages"])
    return {"messages": [response]}


async def call_tools(state: MessagesState, config) -> dict:
    """Run the requested tools on behalf of the verified caller.

    The subject comes from the graph's config, filled in from the verified
    credential, and it overrides whatever subject the model asked for.
    """
    subject = config["configurable"].get("user_subject", "")
    last_message = state["messages"][-1]
    results = []
    for tc in last_message.tool_calls:
        tool = tools_by_name[tc["name"]]
        args = tc["args"]
        if "subject" in tool.args:
            args = {**args, "subject": subject}
        logging.info("[IDENTITY] tool call for subject=%s", subject)
        result = await tool.ainvoke(args)
        results.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
    return {"messages": results}


def should_use_tools(state: MessagesState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "__end__"


graph = StateGraph(MessagesState)
graph.add_node("agent", call_model)
graph.add_node("tools", call_tools)
graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", should_use_tools)
graph.add_edge("tools", "agent")
compiled = graph.compile()


def build_oauth_config() -> OAuthConfig:
    """The identity policy the middleware enforces on every request.

    Against Catalyst, issuer, audience and JWKS URI are all discovered, so the
    app configures none of them. Pass `OAuthConfig(scopes={"reports.read"})` to
    require a scope as well.
    """
    if OFFLINE_IDENTITY:
        from local_identity import start_local_issuer

        return start_local_issuer(LOCAL_REQUIRED_SCOPES)

    return OAuthConfig()


app = FastAPI()
# require_auth defaults to True, so every route is authenticated, app-wide and
# with no per-path exclusion.
app.add_middleware(OAuthMiddleware, config=build_oauth_config())


def _identity(user: VerifiedUser) -> dict:
    """The verified caller, as JSON.

    Claim names only, never claim values: `user.claims` is a real person's
    decoded credential and must not be echoed back.
    """
    return {
        "subject": user.subject,
        "tenant": user.tenant,
        "issuer_id": user.issuer_id,
        "scopes": sorted(user.scopes),
    }


@app.get("/whoami")
def whoami(request: Request) -> dict:
    """Who Catalyst says is calling."""
    user: VerifiedUser = verified_user(request)
    return _identity(user)


@app.post("/agent/run")
async def agent_run(request: Request):
    user: VerifiedUser = verified_user(request)
    logging.info(
        "[IDENTITY] verified caller subject=%s issuer=%s", user.subject, user.issuer_id
    )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": "bad_request", "detail": "body must be JSON"},
        )

    task = body.get("task") if isinstance(body, dict) else None
    if not isinstance(task, str) or not task.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "bad_request", "detail": "task must be a non-empty string"},
        )

    # The subject travels as config, not as a message the model could rewrite.
    result = await compiled.ainvoke(
        {"messages": [HumanMessage(content=task)]},
        config={"configurable": {"user_subject": user.subject}},
    )

    # Drop the empty-content AIMessage that carries only tool_calls.
    return {
        "user": _identity(user),
        "messages": [m.content for m in result["messages"] if m.content],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("APP_PORT", "8006")))

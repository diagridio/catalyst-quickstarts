import logging
import os

logging.basicConfig(level=logging.INFO)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.graph import StateGraph, START, MessagesState

from diagrid.identity import OAuthConfig, VerifiedUser
from diagrid.identity.asgi import OAuthMiddleware
from fake_model import build_canned_model
from tools import (
    catalyst_tools,
    catalyst_tools_by_name,
    local_tools,
    local_tools_by_name,
)

# Only the offline issuer demands a scope. Scopes come from your identity
# provider, and a Diagrid login carries `openid profile email offline_access`
# and nothing else, so requiring one on the Catalyst path would answer 403 for
# everybody. See "On scopes" in the README.
LOCAL_REQUIRED_SCOPES = frozenset({"agent.invoke"})

# Which identity plane the app trusts, and so which tool the graph can use.
# The offline issuer runs with no Catalyst project behind it, so there is no MCP
# server to reach and the graph calls the in-process tool instead. Against
# Catalyst the tool call leaves the agent and picks the caller up on the way.
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

    The subject comes from the graph's config, which the HTTP handler filled in
    from the middleware's VerifiedUser, and it overrides whatever subject the
    model asked for. A model can request anybody's bookings; only the verified
    caller's are ever served. Substituting beats validating here -- there is no
    version of this where the model's opinion of who is calling matters.
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


# An ordinary LangGraph graph. Note what is absent: there is no Diagrid import in
# any node, and no node reads a header or a credential. Identity is handled
# entirely in the ASGI layer below and reaches the graph as plain config.
graph = StateGraph(MessagesState)
graph.add_node("agent", call_model)
graph.add_node("tools", call_tools)
graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", should_use_tools)
graph.add_edge("tools", "agent")
compiled = graph.compile()


def build_oauth_config() -> OAuthConfig:
    """The identity policy the middleware enforces on every request.

    Against Catalyst this is one line -- issuer, audience and JWKS URI are all
    discovered from Catalyst, so the app configures none of them.

    To require a scope as well, pass one: `OAuthConfig(scopes={"reports.read"})`
    answers 403 for any verified caller without it. That needs an identity
    provider issuing the scope, which is why the walkthrough does not use it.

    DIAGRID_QUICKSTART_IDENTITY=local swaps in a throwaway offline issuer so the
    200, 403 and 401 responses are all reachable with no Catalyst project and no
    identity provider at all. See local_identity.py.
    """
    if OFFLINE_IDENTITY:
        from local_identity import start_local_issuer

        return start_local_issuer(LOCAL_REQUIRED_SCOPES)

    return OAuthConfig()


# --- The entire Catalyst identity integration ------------------------------
app = FastAPI()
app.add_middleware(OAuthMiddleware, config=build_oauth_config())
# ---------------------------------------------------------------------------
# require_auth stays at its default True, so every route is authenticated. That
# is why no health route is exposed and why dev-enterprise-identity.yaml
# sets enableAppHealthCheck: false -- an unauthenticated probe would only ever
# see the 401. There is no per-path exclusion; require_auth is app-wide.


def _identity(user: VerifiedUser) -> dict:
    """The verified caller, as JSON.

    Claim names only, never claim values: `user.claims` is a real person's
    decoded credential, and echoing it back would leak whatever the identity
    provider chose to put there.
    """
    return {
        "subject": user.subject,
        "tenant": user.tenant,
        "issuer_id": user.issuer_id,
        "scopes": sorted(user.scopes),
    }


@app.get("/whoami")
def whoami(request: Request) -> dict:
    """Who Catalyst says is calling. No model turn, so the 401/200 contrast is free."""
    user: VerifiedUser = request.state.diagrid_user  # set by OAuthMiddleware
    return _identity(user)


@app.post("/agent/run")
async def agent_run(request: Request):
    user: VerifiedUser = request.state.diagrid_user  # set by OAuthMiddleware
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

    # The verified subject travels as config, not as a message the model could
    # rewrite. LangGraph runs the graph's synchronous nodes off the event loop.
    result = await compiled.ainvoke(
        {"messages": [HumanMessage(content=task)]},
        config={"configurable": {"user_subject": user.subject}},
    )

    # Drop the empty-content AIMessage that carries only tool_calls.
    return {
        "user": _identity(user),
        "messages": [m.content for m in result["messages"] if m.content],
    }


# Guarded so this module can be imported without starting a server or binding a
# port. Importing it still installs the middleware and compiles the graph, which
# is why tools.py and fake_model.py hold the parts the tests assert against.
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("APP_PORT", "8006")))

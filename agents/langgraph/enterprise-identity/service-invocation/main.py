import logging
import os

logging.basicConfig(level=logging.INFO)

from fastapi import FastAPI, Request
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import START, MessagesState, StateGraph
from dapr.clients import DaprClient
from diagrid.identity import OAuthConfig
from diagrid.identity.asgi import OAuthMiddleware

AGENT_SERVICE_APP_ID = "agent-service"
SALESFORCE_QUERY_METHOD = "v1/diagrid/mcp/salesforce-mcp/tools/query"

model = ChatOpenAI(model="gpt-4.1-2025-04-14")


@tool
def query_salesforce(soql: str) -> str:
    """Query Salesforce on behalf of the calling user via the Diagrid sidecar.

    The sidecar performs the on-behalf-of (OBO) token exchange transparently;
    the user identity delivered on the inbound request propagates to the MCP
    tool call without any token handling in the graph.
    """
    with DaprClient() as d:
        response = d.invoke_method(
            AGENT_SERVICE_APP_ID,
            SALESFORCE_QUERY_METHOD,
            data={"soql": soql},
        )
        return response.text()


tools = [query_salesforce]
tools_by_name = {t.name: t for t in tools}
model_with_tools = model.bind_tools(tools)


def call_llm(state: MessagesState) -> dict:
    response = model_with_tools.invoke(state["messages"])
    return {"messages": [response]}


def call_mcp_tool(state: MessagesState) -> dict:
    last_message = state["messages"][-1]
    results = []
    for tc in last_message.tool_calls:
        result = tools_by_name[tc["name"]].invoke(tc["args"])
        results.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
    return {"messages": results}


def should_use_tools(state: MessagesState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "__end__"


# Build a normal LangGraph — no Diagrid awareness in the graph itself.
graph = StateGraph(MessagesState)
graph.add_node("agent", call_llm)
graph.add_node("tools", call_mcp_tool)
graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", should_use_tools)
graph.add_edge("tools", "agent")
compiled = graph.compile()

# ---- Diagrid identity setup — 3 lines ----
oauth = OAuthConfig(scopes={"agent.invoke"})
app = FastAPI()
app.add_middleware(OAuthMiddleware, config=oauth)


@app.post("/invoke")
def invoke(request: Request, body: dict):
    user = request.state.diagrid_user  # populated by OAuthMiddleware
    result = compiled.invoke(
        {"messages": [HumanMessage(content=body["prompt"])]},
        config={"configurable": {"user_subject": user.subject}},
    )
    return {"messages": [m.content for m in result["messages"]]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("APP_PORT", "8005")))

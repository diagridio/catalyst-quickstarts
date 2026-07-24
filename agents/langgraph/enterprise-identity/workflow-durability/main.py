import os

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, MessagesState
from langchain_openai import ChatOpenAI
from dapr.clients import DaprClient

from diagrid.identity import OAuthConfig
from diagrid.agent.identity import HITLConfig
from diagrid.agent.plugins import OAuthPlugin, HITLPlugin
from diagrid.agent.langgraph import DaprWorkflowGraphRunner
from dapr_agents.hooks import RequireApproval

APP_PORT = int(os.environ.get("APP_PORT", "8005"))
AGENT_SERVICE = "agent-service"
SALESFORCE_MCP = "salesforce-mcp"
APPROVER_SCOPE = "approver.dev"


@tool
def query_customers(soql: str) -> str:
    """Read Salesforce records matching a SOQL query."""
    with DaprClient() as d:
        resp = d.invoke_method(
            AGENT_SERVICE,
            f"v1/diagrid/mcp/{SALESFORCE_MCP}/tools/query",
            data={"soql": soql},
        )
    return resp.text()


@tool
def delete_customer(record_id: str) -> str:
    """Delete a Salesforce customer record. Requires human approval before it runs."""
    return RequireApproval(
        required_approver_scopes={APPROVER_SCOPE},
        reason=f"Delete customer records ({record_id}) — GDPR erasure flow",
    )


tools = [query_customers, delete_customer]
tools_by_name = {t.name: t for t in tools}
model = ChatOpenAI(model="gpt-4.1-2025-04-14").bind_tools(tools)


def call_model(state: MessagesState) -> dict:
    response = model.invoke(state["messages"])
    return {"messages": [response]}


def call_tools(state: MessagesState) -> dict:
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


graph = StateGraph(MessagesState)
graph.add_node("agent", call_model)
graph.add_node("tools", call_tools)
graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", should_use_tools)
graph.add_edge("tools", "agent")

oauth = OAuthConfig(scopes={"agent.invoke"})
hitl = HITLConfig(required_approver_scopes={APPROVER_SCOPE})

runner = DaprWorkflowGraphRunner(
    graph=graph.compile(),
    name="customer-ops",
    role="Customer Operations Agent",
    goal="Answer questions about customers and, with approval, erase records on request.",
    plugins=[OAuthPlugin(oauth), HITLPlugin(hitl)],
)

runner.serve(
    port=APP_PORT,
    input_mapper=lambda req: {"messages": [HumanMessage(content=req["prompt"])]},
)

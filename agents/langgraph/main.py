import logging
import os

logging.basicConfig(level=logging.DEBUG)

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END, MessagesState
from diagrid.agent.langgraph import DaprWorkflowGraphRunner
from diagrid.agent.core.chat import DaprChatModel


@tool
def check_availability(venue: str, date: str) -> str:
    """Check venue availability for a specific date."""
    return f"{venue} is available on {date}. Time slots: 9AM-1PM, 2PM-6PM, 6PM-11PM."


tools = [check_availability]
tools_by_name = {t.name: t for t in tools}
model = DaprChatModel(component_name="llm-provider").bind_tools(tools)


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

runner = DaprWorkflowGraphRunner(
    graph=graph.compile(),
    name="schedule-planner",
    role="Schedule Planner",
    goal="Check venue date and time availability using the check_availability tool. Provide available time slots for a given venue and date.",
)
runner.serve(
    port=int(os.environ.get("APP_PORT", "8005")),
    input_mapper=lambda req: {"messages": [HumanMessage(content=req["task"])]},
)

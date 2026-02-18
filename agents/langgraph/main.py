import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END, MessagesState
from diagrid.agent.langgraph import DaprWorkflowGraphRunner


@tool
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return f"Sunny in {city}, 72F"


tools = [get_weather]
tools_by_name = {t.name: t for t in tools}
model = ChatOpenAI(model="gpt-4o-mini").bind_tools(tools)


def call_model(state: MessagesState) -> dict:
    response = model.invoke(state["messages"])
    return {"messages": [response]}


def call_tools(state: MessagesState) -> dict:
    last_message = state["messages"][-1]
    results = []
    for tc in last_message.tool_calls:
        result = tools_by_name[tc["name"]].invoke(tc["args"])
        results.append(
            ToolMessage(content=str(result), tool_call_id=tc["id"])
        )
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

runner = DaprWorkflowGraphRunner(graph=graph.compile())
runner.serve(
    port=int(os.environ.get("APP_PORT", "5001")),
    input_mapper=lambda req: {"messages": [HumanMessage(content=req["task"])]},
)

import logging
import os

logging.basicConfig(level=logging.INFO)

from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.graph import StateGraph, START, MessagesState
from diagrid.agent.langgraph import DaprWorkflowGraphRunner
from fake_model import build_canned_model
from tools import tools, tools_by_name


def build_model():
    """Real provider on request, canned model otherwise."""
    if os.environ.get("DIAGRID_QUICKSTART_MODEL") == "openai":
        from langchain_openai import ChatOpenAI

        logging.info("Using OpenAI (gpt-4.1-2025-04-14).")
        return ChatOpenAI(model="gpt-4.1-2025-04-14")

    logging.info(
        "Using the canned offline model: no API key needed and the answer is "
        "always the same. Set DIAGRID_QUICKSTART_MODEL=openai for a real provider."
    )
    return build_canned_model()


model = build_model().bind_tools(tools)


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

# Guarded so this module can be imported without starting a server. The tests import
# check_availability from here to assert against the real tool rather than a copy of it.
if __name__ == "__main__":
    # State + PubSub: subscribe for incoming tasks, publish results
    runner.serve(
        port=int(os.environ.get("APP_PORT", "8005")),
        input_mapper=lambda req: {"messages": [HumanMessage(content=req["task"])]},
        pubsub_name="pubsub",
        subscribe_topic="schedule.requests",
        publish_topic="schedule.results",
    )

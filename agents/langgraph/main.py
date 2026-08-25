import logging
import os

logging.basicConfig(level=logging.INFO)

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, MessagesState
from diagrid.agent.langgraph import DaprWorkflowGraphRunner
from fake_model import CannedToolCallingModel


@tool
def check_availability(venue: str, date: str) -> str:
    """Check venue availability for a specific date."""
    return f"{venue} is available on {date}. Time slots: 9AM-1PM, 2PM-6PM, 6PM-11PM."


tools = [check_availability]
tools_by_name = {t.name: t for t in tools}


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
    return CannedToolCallingModel(
        first_turn=AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "check_availability",
                    "args": {"venue": "Grand Ballroom", "date": "March 15th"},
                    "id": "call_availability_1",
                    "type": "tool_call",
                }
            ],
        ),
        final_turn=AIMessage(
            content=(
                "Yes, the Grand Ballroom is available on March 15th. "
                "Open slots are 9AM-1PM, 2PM-6PM, and 6PM-11PM."
            )
        ),
    )


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

# State + PubSub: subscribe for incoming tasks, publish results
runner.serve(
    port=int(os.environ.get("APP_PORT", "8005")),
    input_mapper=lambda req: {"messages": [HumanMessage(content=req["task"])]},
    pubsub_name="pubsub",
    subscribe_topic="schedule.requests",
    publish_topic="schedule.results",
)

import os
from typing import List, TypedDict

from langgraph.graph import StateGraph, START, END
from diagrid.agent.langgraph import DaprWorkflowGraphRunner


class State(TypedDict):
    messages: List[str]


def process(state: State) -> dict:
    return {"messages": state["messages"] + ["processed"]}


graph = StateGraph(State)
graph.add_node("process", process)
graph.add_edge(START, "process")
graph.add_edge("process", END)

runner = DaprWorkflowGraphRunner(graph=graph.compile())
runner.serve(
    port=int(os.environ.get("APP_PORT", "5001")),
    input_mapper=lambda req: {"messages": [req["prompt"]]},
)

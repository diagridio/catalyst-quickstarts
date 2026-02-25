import logging
import os

logging.basicConfig(level=logging.DEBUG)

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from diagrid.agent.adk import DaprWorkflowAgentRunner
from diagrid.agent.core.state import DaprStateStore


def find_entertainment(event_type: str) -> str:
    """Find entertainment options for an event type."""
    return (
        f"Entertainment options for {event_type}:\n"
        f"1. Live Jazz Band 'Blue Notes' - $2,500 for 3 hours\n"
        f"2. DJ & Sound System - $1,200 for 4 hours\n"
        f"3. Stand-up Comedian - $1,800 for 1 hour set"
    )


agent = LlmAgent(
    name="entertainment_planner",
    instruction="You are an entertainment planner. When asked to find entertainment, use the find_entertainment tool with the event type. Return the available entertainment options with pricing and duration. Always call the tool before responding.",
    tools=[FunctionTool(find_entertainment)],
)

# State: persist agent memory across invocations
runner = DaprWorkflowAgentRunner(
    agent=agent,
    state_store=DaprStateStore(store_name="agent-memory"),
)

# PubSub: subscribe for incoming tasks, publish results
runner.serve(
    port=int(os.environ.get("APP_PORT", "8003")),
    pubsub_name="agent-pubsub",
    subscribe_topic="entertainment.requests",
    publish_topic="entertainment.results",
)

import logging
import os

logging.basicConfig(level=logging.DEBUG)

from agents import Agent, function_tool
from diagrid.agent.openai_agents import DaprWorkflowAgentRunner
from diagrid.agent.core.state import DaprStateStore


@function_tool
def search_catering(cuisine: str, guest_count: int) -> str:
    """Search for catering options by cuisine type and guest count."""
    return (
        f"Found catering options for {guest_count} guests ({cuisine}):\n"
        f"1. Elite Catering Co - ${guest_count * 45}/event, full service\n"
        f"2. Farm Fresh Events - ${guest_count * 35}/event, organic menu\n"
        f"3. Quick Bites Catering - ${guest_count * 25}/event, casual buffet"
    )


agent = Agent(
    name="catering-coordinator",
    instructions="You are a catering coordinator. When asked to find catering, use the search_catering tool with the cuisine type and number of guests. Return the available catering options with pricing. Always call the tool before responding.",
    tools=[search_catering],
)

# State: persist agent memory across invocations
runner = DaprWorkflowAgentRunner(
    agent=agent,
    state_store=DaprStateStore(store_name="agent-memory"),
)

# PubSub: subscribe for incoming tasks, publish results
runner.serve(
    port=int(os.environ.get("APP_PORT", "8002")),
    pubsub_name="agent-pubsub",
    subscribe_topic="catering.requests",
    publish_topic="catering.results",
)

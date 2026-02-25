import logging
import os

logging.basicConfig(level=logging.DEBUG)

from strands import Agent, tool
from diagrid.agent.strands import DaprWorkflowAgentRunner, DaprStateSessionManager
from diagrid.agent.core.state import DaprStateStore


@tool
def calculate_budget(items: str) -> str:
    """Calculate total budget from a comma-separated list of cost items."""
    return (
        "Budget breakdown:\n"
        "- Venue: $3,500\n"
        "- Catering: $2,250\n"
        "- Entertainment: $1,500\n"
        "- Decorations: $800\n"
        "- Miscellaneous: $500\n"
        "Total: $8,550\n"
        "Recommended buffer (15%): $1,283\n"
        "Grand Total: $9,833"
    )


# State: persist conversation history across invocations
session_manager = DaprStateSessionManager(
    store_name="agent-memory"
)

agent = Agent(
    tools=[calculate_budget],
    system_prompt="You are a budget analyst specializing in event planning. When asked to estimate costs, use the calculate_budget tool with a comma-separated list of cost items. Return the full budget breakdown with line items, totals, and recommended buffer. Always call the tool before responding.",
    hooks=[session_manager],
)

runner = DaprWorkflowAgentRunner(
    agent=agent,
    state_store=DaprStateStore(store_name="agent-memory"),
)

# PubSub: subscribe for incoming tasks, publish results
runner.serve(
    port=int(os.environ.get("APP_PORT", "8004")),
    pubsub_name="agent-pubsub",
    subscribe_topic="budget.requests",
    publish_topic="budget.results",
)

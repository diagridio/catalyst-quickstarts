import logging
import os

logging.basicConfig(level=logging.INFO)

from pydantic_ai import Agent
from diagrid.agent.pydantic_ai import DaprWorkflowAgentRunner
from diagrid.agent.core.state import DaprStateStore


def search_decorations(theme: str, venue_size: str) -> str:
    """Search for decoration packages by theme and venue size."""
    return (
        f"Found decoration packages for '{theme}' theme ({venue_size} venue):\n"
        f"1. Elegant Events Decor - Premium {theme} package, full setup & teardown\n"
        f"2. Budget Blooms - Affordable {theme} florals and centerpieces\n"
        f"3. Grand Occasions - Luxury {theme} decor with lighting and draping"
    )


agent = Agent(
    "openai:gpt-4o-mini",
    system_prompt=(
        "You are a decoration planner. When asked to find decorations, "
        "use the search_decorations tool with the theme and venue size. "
        "Return the available decoration packages. "
        "Always call the tool before responding."
    ),
    tools=[search_decorations],
)

# State: persist agent memory across invocations
runner = DaprWorkflowAgentRunner(
    name="decoration-planner",
    agent=agent,
    state_store=DaprStateStore(store_name="agent-memory"),
)

# PubSub: subscribe for incoming tasks, publish results
runner.serve(
    port=int(os.environ.get("APP_PORT", "8008")),
    pubsub_name="agent-pubsub",
    subscribe_topic="decorations.requests",
    publish_topic="decorations.results",
)

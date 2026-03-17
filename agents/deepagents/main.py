import logging
import os

logging.basicConfig(level=logging.INFO)

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from deepagents import create_deep_agent
from diagrid.agent.deepagents import DaprWorkflowDeepAgentRunner


@tool
def search_transportation(event_type: str, guest_count: str) -> str:
    """Search for transportation options by event type and guest count."""
    return (
        f"Found transportation options for '{event_type}' ({guest_count} guests):\n"
        f"1. Premier Shuttle Co. - Fleet of luxury shuttles, seats up to 50 per vehicle\n"
        f"2. City Limo Group - Stretch limos and sedans for VIP guests\n"
        f"3. Green Transit - Eco-friendly electric bus service for large groups"
    )


agent = create_deep_agent(
    model="openai:gpt-4o-mini",
    tools=[search_transportation],
    system_prompt=(
        "You are a transportation planner. When asked to find transportation, "
        "use the search_transportation tool with the event type and guest count. "
        "Return the available transportation options. "
        "Always call the tool before responding."
    ),
    name="transportation-planner",
)

runner = DaprWorkflowDeepAgentRunner(
    agent=agent,
    name="transportation-planner",
    role="Transportation Planner",
    goal="Find transportation options for events using the search_transportation tool. Provide shuttle, limo, and transit options based on event type and guest count.",
)

# PubSub: subscribe for incoming tasks, publish results
runner.serve(
    port=int(os.environ.get("APP_PORT", "8009")),
    input_mapper=lambda req: {"messages": [HumanMessage(content=req["task"])]},
    pubsub_name="agent-pubsub",
    subscribe_topic="transportation.requests",
    publish_topic="transportation.results",
)

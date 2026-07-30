import logging
import os

logging.basicConfig(level=logging.INFO)

from claude_agent_sdk import ClaudeAgentOptions, tool
from diagrid.agent.claude_agents import DaprWorkflowAgentRunner
from diagrid.agent.core.state import DaprStateStore


@tool(
    "search_photography",
    "Search for photography and videography packages by event type and number of coverage hours.",
    {"event_type": str, "hours": int},
)
async def search_photography(args):
    """Search for photography options by event type and coverage hours."""
    event_type = args["event_type"]
    hours = args["hours"]
    text = (
        f"Found photography options for '{event_type}' ({hours} hours of coverage):\n"
        f"1. Lumiere Studios - ${hours * 250}/event, two photographers + edited gallery\n"
        f"2. Candid Frames - ${hours * 180}/event, photojournalistic style, next-day previews\n"
        f"3. Motion & Still Co - ${hours * 320}/event, photo + cinematic video package"
    )
    return {"content": [{"type": "text", "text": text}]}


options = ClaudeAgentOptions(
    system_prompt=(
        "You are a photography planner. When asked to find photography or "
        "videography, use the search_photography tool with the event type and the "
        "number of coverage hours. Return the available packages with pricing. "
        "Always call the tool before responding."
    ),
    model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
)

# Runner: each LLM turn and each tool call runs as a durable Dapr Workflow activity
runner = DaprWorkflowAgentRunner(
    name="photography-planner",
    options=options,
    tools=[search_photography],
    # State: persist agent memory across invocations
    state_store=DaprStateStore(store_name="agent-memory"),
)

# PubSub: subscribe for incoming tasks, publish results
runner.serve(
    port=int(os.environ.get("APP_PORT", "8010")),
    pubsub_name="agent-pubsub",
    subscribe_topic="photography.requests",
    publish_topic="photography.results",
)

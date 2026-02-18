import os

from agents import Agent, function_tool
from diagrid.agent.openai_agents import DaprWorkflowAgentRunner


@function_tool
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return f"Sunny in {city}, 72F"


agent = Agent(
    name="assistant",
    instructions="You are a helpful assistant.",
    model="gpt-4o-mini",
    tools=[get_weather],
)
runner = DaprWorkflowAgentRunner(agent=agent)
runner.serve(port=int(os.environ.get("APP_PORT", "5001")))

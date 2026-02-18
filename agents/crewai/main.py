import os

from crewai import Agent
from crewai.tools import tool
from diagrid.agent.crewai import DaprWorkflowAgentRunner


@tool("Get weather")
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return f"Sunny in {city}, 72F"


agent = Agent(
    role="Assistant",
    goal="Help users",
    backstory="Expert assistant",
    tools=[get_weather],
    llm="openai/gpt-4o-mini",
)
runner = DaprWorkflowAgentRunner(agent=agent)
runner.serve(port=int(os.environ.get("APP_PORT", "5001")))

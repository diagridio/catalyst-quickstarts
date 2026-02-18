import os

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from diagrid.agent.adk import DaprWorkflowAgentRunner


def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return f"Sunny in {city}, 72F"


agent = LlmAgent(
    name="assistant",
    model="gemini-2.0-flash",
    tools=[FunctionTool(get_weather)],
)
runner = DaprWorkflowAgentRunner(agent=agent)
runner.serve(port=int(os.environ.get("APP_PORT", "5001")))

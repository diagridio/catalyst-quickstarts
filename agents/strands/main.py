import os

from strands import Agent, tool
from strands.models.openai import OpenAIModel
from diagrid.agent.strands import DaprWorkflowAgentRunner


@tool
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return f"Weather in {city}: Sunny, 72F"


agent = Agent(
    model=OpenAIModel(model_id="gpt-4o-mini"),
    tools=[get_weather],
    system_prompt="You are a helpful assistant.",
)
runner = DaprWorkflowAgentRunner(agent=agent)
runner.serve(port=int(os.environ.get("APP_PORT", "5001")))

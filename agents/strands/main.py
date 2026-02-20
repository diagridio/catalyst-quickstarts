import logging
import os

logging.basicConfig(level=logging.DEBUG)

from strands import Agent, tool
from diagrid.agent.strands import DaprWorkflowAgentRunner


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


agent = Agent(
    tools=[calculate_budget],
    system_prompt="You are a budget analyst specializing in event planning. When asked to estimate costs, use the calculate_budget tool with a comma-separated list of cost items. Return the full budget breakdown with line items, totals, and recommended buffer. Always call the tool before responding.",
)
runner = DaprWorkflowAgentRunner(agent=agent)
runner.serve(port=int(os.environ.get("APP_PORT", "8004")))

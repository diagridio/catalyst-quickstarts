import logging
import os

# Imported first: it loads the secrets the Dapr SDK reads when it is imported.
from bedrock_runner import BedrockRunner

from strands import Agent, tool
from strands.models.openai import OpenAIModel
from diagrid.agent.core.state import DaprStateStore
from diagrid.agent.strands import DaprWorkflowAgentRunner

logging.basicConfig(level=logging.INFO)


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


# Any OpenAI-compatible provider works: set OPENAI_BASE_URL to its endpoint and
# OPENAI_MODEL to a model it serves. Empty values fall back to OpenAI's defaults.
model = OpenAIModel(
    client_args={"base_url": os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"},
    model_id=os.environ.get("OPENAI_MODEL") or "gpt-4o-mini",
)

agent = Agent(
    model=model,
    tools=[calculate_budget],
    system_prompt="You are a budget analyst specializing in event planning. When asked to estimate costs, use the calculate_budget tool with a comma-separated list of cost items. Return the full budget breakdown with line items, totals, and recommended buffer. Always call the tool before responding.",
)

runner = BedrockRunner(
    DaprWorkflowAgentRunner(
        name="budget-planner",
        agent=agent,
        state_store=DaprStateStore(store_name="kvstore"),
    )
)

if __name__ == "__main__":
    runner.serve()

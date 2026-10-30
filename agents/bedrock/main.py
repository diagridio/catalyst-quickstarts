import logging
import os

# Imported first: it loads the secrets the Dapr SDK reads when it is imported.
from bedrock_runner import BedrockRunner

from strands import Agent, tool
from strands.models.openai import OpenAIModel
from diagrid.agent.core.state import DaprStateStore
from diagrid.agent.strands import DaprWorkflowAgentRunner

logging.basicConfig(level=logging.INFO)


PRICES = {
    "venue": 3500,
    "catering": 2250,
    "entertainment": 1500,
    "decorations": 800,
    "miscellaneous": 500,
}


@tool
def calculate_budget(items: str) -> str:
    """Calculate total budget from a comma-separated list of cost items."""
    lines = ["Budget breakdown:"]
    total = 0
    for item in (i.strip() for i in items.split(",")):
        if not item:
            continue
        price = PRICES.get(item.lower())
        if price is None:
            lines.append(f"- {item}: no price available")
            continue
        lines.append(f"- {item}: ${price:,}")
        total += price
    buffer = round(total * 0.15)
    lines.append(f"Total: ${total:,}")
    lines.append(f"Recommended buffer (15%): ${buffer:,}")
    lines.append(f"Grand Total: ${total + buffer:,}")
    return "\n".join(lines)


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

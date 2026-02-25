from dapr_agents import DurableAgent, tool
from dapr_agents.llm.dapr import DaprChatClient
from dapr_agents.workflow.runners.agent import AgentRunner
from dotenv import load_dotenv

load_dotenv()

@tool
def get_customer_environment(customer_name: str) -> dict:
    """Return hardcoded environment details for a given customer."""
    return {
        "customer": customer_name,
        "kubernetes_version": "1.34.0",
        "region": "us-west-2",
    }


def main() -> None:
    expert_agent = DurableAgent(
        name="expert-agent",
        role="Technical Troubleshooting Specialist",
        goal="Diagnose and summarize a customer issue into a professional response message.",
        instructions=[
            "Use the tool to fetch the customer's environment info.",
            "Based on the environment and issue description, provide a short, actionable resolution proposal.",
            "Summarize the resolution in a customer-friendly message format, including urgency.",
            "Output a JSON with fields: environment, resolution, and customer_message.",
        ],
        llm = DaprChatClient(component_name="agent-llm-provider"),
        tools=[get_customer_environment],
    )

    runner = AgentRunner()
    try:
        runner.serve(expert_agent, port=8002)
    finally:
        runner.shutdown(expert_agent)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Shutting down agent...")

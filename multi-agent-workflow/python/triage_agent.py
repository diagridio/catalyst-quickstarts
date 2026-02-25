from dapr_agents import DurableAgent, tool
from dapr_agents.llm.dapr import DaprChatClient
from dapr_agents.workflow.runners.agent import AgentRunner
from dotenv import load_dotenv

load_dotenv()

@tool
def check_entitlement(customer_name: str) -> bool:
    """Return True if customer has entitlement."""
    return customer_name.strip().lower() == "alice"

def main() -> None:
    triage_agent = DurableAgent(
        name="triage-agent",
        role="Customer Support Triage Assistant",
        goal="Assess entitlement and urgency based on issue description.",
        instructions=[
            "Use the tool to check entitlement by name.",
            "If the customer has entitlement, classify urgency: "
            "if the issue affects production, mark as URGENT, otherwise NORMAL.",
            "Return a JSON object with keys: entitled (bool) and urgency (string).",
        ],
        llm = DaprChatClient(component_name="agent-llm-provider"),
        tools=[check_entitlement],
    )

    runner = AgentRunner()
    try:
        runner.serve(triage_agent, port=8001)
    finally:
        runner.shutdown(triage_agent)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Shutting down agent...")

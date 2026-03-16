from dapr_agents import DurableAgent, tool
from dapr_agents.agents.configs import (
    AgentPubSubConfig,
    AgentRegistryConfig,
    AgentStateConfig,
)
from dapr_agents.llm.dapr import DaprChatClient
from dapr_agents.storage.daprstores.stateservice import StateStoreService
from dapr_agents.workflow.runners.agent import AgentRunner
from dotenv import load_dotenv

load_dotenv()


@tool
def get_customer_environment(customer_name: str) -> dict:
    """Return environment details for a given customer."""
    return {
        "customer": customer_name,
        "kubernetes_version": "1.34.0",
        "region": "us-west-2",
    }


def main() -> None:
    agent = DurableAgent(
        name="expert-agent",
        role="Technical Troubleshooting Specialist",
        goal="Diagnose issues and provide resolutions.",
        instructions=[
            "Get the customer's environment info, then provide a resolution.",
            "Return JSON with: environment, resolution, customer_message.",
        ],
        llm=DaprChatClient(component_name="agent-llm-provider"),
        tools=[get_customer_environment],

        state=AgentStateConfig(
            store=StateStoreService(store_name="agent-workflow", key_prefix="expert:"),
        ),
        registry=AgentRegistryConfig(
            store=StateStoreService(store_name="agent-registry"),
        ),
    )

    runner = AgentRunner()
    try:
        runner.serve(agent, port=8003)
    finally:
        runner.shutdown(agent)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

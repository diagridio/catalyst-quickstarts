import logging
from dapr_agents.agents import DurableAgent
from dapr_agents.agents.configs import (
    AgentExecutionConfig,
    AgentPubSubConfig,
    AgentRegistryConfig,
    AgentStateConfig,
    OrchestrationMode,
)
from dapr_agents.llm import DaprChatClient
from dapr_agents.storage.daprstores.stateservice import StateStoreService
from dapr_agents.workflow.runners import AgentRunner
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    orchestrator = DurableAgent(
        name="support-agent-orchestrator",
        role="Customer Support Orchestrator",
        goal="Coordinate triage and expert agents to handle customer issues.",
        instructions=[
            "Delegate to triage-agent to check entitlement and assess urgency.",
            "If entitled, delegate to expert-agent to diagnose and resolve the issue.",
            "Synthesize results into a customer-friendly response.",
        ],
        execution=AgentExecutionConfig(
            max_iterations=10,
            orchestration_mode=OrchestrationMode.AGENT,
        ),
        llm=DaprChatClient(component_name="agent-llm-provider"),
        pubsub=AgentPubSubConfig(
            pubsub_name="agent-pubsub",
            agent_topic="support.orchestrator.requests",
            broadcast_topic="agents.broadcast",
        ),
        state=AgentStateConfig(
            store=StateStoreService(store_name="agent-workflow", key_prefix="orchestrator:"),
        ),
        registry=AgentRegistryConfig(
            store=StateStoreService(store_name="agent-registry"),
        ),
    )

    runner = AgentRunner()
    try:
        runner.serve(orchestrator, port=8001)
    finally:
        runner.shutdown(orchestrator)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

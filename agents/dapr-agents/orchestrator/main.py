import logging
import os
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


def main() -> None:
    logging.basicConfig(level=logging.DEBUG)

    orchestrator = DurableAgent(
        name="EventCoordinator",
        role="Event Planning Coordinator",
        goal="Coordinate the event planning team to deliver a complete event plan by delegating to all available specialist agents",
        instructions=[
            "You coordinate a team of specialist agents to plan events. Delegate all tasks in parallel when possible.",
            "For each request: 1) Find a venue, 2) Find catering, 3) Find entertainment, 4) Check date availability, 5) Calculate the budget, 6) Send invitations.",
            "Delegate each task to the matching agent based on their role. Do not attempt tasks yourself.",
            "Once all agents have responded, synthesize their results into a single comprehensive event plan.",
        ],
        llm=DaprChatClient(component_name="llm-provider"),
        pubsub=AgentPubSubConfig(
            pubsub_name="agent-pubsub",
            agent_topic="events.orchestrator.requests",
            broadcast_topic="agents.broadcast",
        ),
        state=AgentStateConfig(
            store=StateStoreService(store_name="agent-workflow", key_prefix="orchestrator:"),
        ),
        registry=AgentRegistryConfig(
            store=StateStoreService(store_name="agent-registry"),
        ),
        execution=AgentExecutionConfig(
            max_iterations=25,
            orchestration_mode=OrchestrationMode.AGENT,
        ),
    )

    runner = AgentRunner()
    try:
        runner.serve(orchestrator, port=int(os.environ.get("APP_PORT", "8007")))
    finally:
        runner.shutdown(orchestrator)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

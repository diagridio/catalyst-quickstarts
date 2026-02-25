import logging
import os
import uuid
from typing import List
from pydantic import BaseModel, Field
from dapr_agents import tool, DurableAgent
from dapr_agents.llm import DaprChatClient

from dapr_agents.agents.configs import (
    AgentMemoryConfig,
    AgentPubSubConfig,
    AgentRegistryConfig,
    AgentStateConfig,
)
from dapr_agents.memory import ConversationDaprStateMemory
from dapr_agents.storage.daprstores.stateservice import StateStoreService
from dapr_agents.workflow.runners import AgentRunner


class InvitationResult(BaseModel):
    sent: int = Field(description="Number of invitations sent")
    method: str = Field(description="Delivery method")


class InvitationSchema(BaseModel):
    guest_count: int = Field(description="Number of guests to invite")
    event_type: str = Field(description="Type of event")


@tool(args_model=InvitationSchema)
def send_invitations(guest_count: int, event_type: str) -> List[InvitationResult]:
    """Send event invitations to guests."""
    return [
        InvitationResult(sent=int(guest_count * 0.7), method="email"),
        InvitationResult(sent=int(guest_count * 0.3), method="physical mail"),
    ]


def main() -> None:
    logging.basicConfig(level=logging.DEBUG)

    agent = DurableAgent(
        name="invitations-manager",
        role="Invitations Manager",
        goal="Send event invitations to guests using the send_invitations tool. Report how many were sent by email and physical mail.",
        instructions=[
            "When asked to send invitations, use the send_invitations tool with the guest count and event type.",
            "Always report back the exact number of invitations sent and via which delivery method.",
        ],
        tools=[send_invitations],
        llm=DaprChatClient(component_name="llm-provider"),
        memory=AgentMemoryConfig(
            store=ConversationDaprStateMemory(
                store_name="agent-workflow"
            )
        ),
        state=AgentStateConfig(
            store=StateStoreService(store_name="agent-memory"),
        ),
        registry=AgentRegistryConfig(
            store=StateStoreService(store_name="agent-registry"),
        ),
        pubsub=AgentPubSubConfig(
            pubsub_name="agent-pubsub",
            agent_topic="events.invitations.requests",
            broadcast_topic="agents.broadcast",
        ),
    )

    agent.start()

    runner = AgentRunner()
    try:
        runner.serve(agent, port=int(os.environ.get("APP_PORT", "8006")))
    finally:
        runner.shutdown()
        agent.stop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

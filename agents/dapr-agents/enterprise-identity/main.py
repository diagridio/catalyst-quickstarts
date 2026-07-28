import logging
import os
from typing import List

from pydantic import BaseModel, Field
from dapr_agents import tool, DurableAgent
from dapr_agents.llm import DaprChatClient
from dapr_agents.hooks import RequireApproval

from dapr_agents.agents.configs import (
    AgentMemoryConfig,
    AgentPubSubConfig,
    AgentRegistryConfig,
    AgentStateConfig,
)
from dapr_agents.memory import ConversationDaprStateMemory
from dapr_agents.storage.daprstores.stateservice import StateStoreService

from diagrid.identity import OAuthConfig
from diagrid.agent.identity import HITLConfig
from diagrid.agent.plugins import PluginRegistry, OAuthPlugin, HITLPlugin


class AccountQuery(BaseModel):
    account_id: str = Field(description="Salesforce account ID to look up")


class AccountRecord(BaseModel):
    account_id: str = Field(description="Salesforce account ID")
    name: str = Field(description="Account name")
    owner: str = Field(description="Account owner")


class DeleteAccountSchema(BaseModel):
    account_id: str = Field(description="Salesforce account ID to delete")


@tool(args_model=AccountQuery)
def query_account(account_id: str) -> AccountRecord:
    """Look up a Salesforce account by ID on behalf of the calling user."""
    return AccountRecord(account_id=account_id, name="Acme Corp", owner="user@acme.example")


@tool(args_model=DeleteAccountSchema)
def delete_account(account_id: str) -> RequireApproval:
    """Delete a Salesforce account. Gated by HITL — a scoped approver must sign off."""
    return RequireApproval(
        required_approver_scopes={"approver.dev"},
        reason=f"Delete Salesforce account {account_id} — irreversible",
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    oauth = OAuthConfig(scopes={"agent.invoke"})
    hitl = HITLConfig(required_approver_scopes={"approver.dev"})

    agent = DurableAgent(
        name="salesforce-agent",
        role="Answer customer questions using Salesforce data",
        goal="Answer account questions and perform account operations on behalf of the calling user.",
        instructions=[
            "Use query_account to look up account details before answering questions.",
            "Use delete_account only when explicitly asked to delete an account; it requires human approval.",
        ],
        tools=[query_account, delete_account],
        llm=DaprChatClient(component_name="llm-provider"),
        memory=AgentMemoryConfig(
            store=ConversationDaprStateMemory(store_name="agent-workflow"),
        ),
        state=AgentStateConfig(
            store=StateStoreService(store_name="agent-memory"),
        ),
        registry=AgentRegistryConfig(
            store=StateStoreService(store_name="agent-registry"),
        ),
        pubsub=AgentPubSubConfig(
            pubsub_name="agent-pubsub",
            agent_topic="agents.salesforce.requests",
            broadcast_topic="agents.broadcast",
        ),
        lifecycle_dispatcher=PluginRegistry([
            OAuthPlugin(oauth),
            HITLPlugin(hitl),
        ]),
    )

    agent.as_service(port=int(os.environ.get("APP_PORT", "8001")))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

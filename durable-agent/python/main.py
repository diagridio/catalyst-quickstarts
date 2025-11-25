import logging
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


# Define tool output models
class FlightOption(BaseModel):
    airline: str = Field(description="Airline name")
    price: float = Field(description="Price in USD")

class HotelOption(BaseModel):
    hotel_name: str = Field(description="Hotel name")
    price_per_night: float = Field(description="Price per night in USD")

# Define tool input models
class DestinationSchema(BaseModel):
    destination: str = Field(description="Destination city name")

# Define flight search tool with mock flight data
@tool(args_model=DestinationSchema)
def search_flights(destination: str) -> List[FlightOption]:
    """Search for flights to the specified destination."""
    return [
        FlightOption(airline="SkyHighAir", price=450.00),
        FlightOption(airline="GlobalWings", price=375.50),
    ]

# Define hotel search tool with mock hotel data
@tool(args_model=DestinationSchema)
def search_hotels(destination: str) -> List[HotelOption]:
    """Search for hotels at the destination. Call this after finding flights."""
    return [
        HotelOption(hotel_name="Grand Plaza Hotel", price_per_night=180.00),
        HotelOption(hotel_name="Seaside Resort", price_per_night=225.00),
    ]

def main() -> None:
    logging.basicConfig(level=logging.INFO)

    travel_assistant = DurableAgent(
        name="travel-assistant-agent",
        role="Travel Assistant",
        goal="Plan trips by searching flights first, then hotels only if flights are available",
        instructions=[
            "Always search for flights first, and after that for hotels",
            "If flights are found, immediately search for hotels for the same destination",
            "If no flights are found for a destination, do NOT search for hotels for that destination",
            "Complete all tool calls automatically without asking for user confirmation"
        ],
        tools=[search_flights, search_hotels],

        llm = DaprChatClient(component_name="openai"),

        memory = AgentMemoryConfig(
            store=ConversationDaprStateMemory(
                store_name="statestore",
                session_id=f"session-headless-{uuid.uuid4().hex[:8]}"
            )
        ),

        state = AgentStateConfig(
            store=StateStoreService(store_name="statestore"),
        ),

        registry = AgentRegistryConfig(
            store=StateStoreService(store_name="statestore"),
        ),

        pubsub = AgentPubSubConfig(
            pubsub_name="pubsub",
            agent_topic="travel.requests",
            broadcast_topic="agents.broadcast",
        )
    )

    travel_assistant.start()
    print("Travel Assistant Agent is running")

    runner = AgentRunner()
    try:
        runner.serve(travel_assistant, port=5001)
    except Exception as e:
        print(f"Error starting service: {e}")
        raise
    finally:
        runner.shutdown()
        travel_assistant.stop()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass


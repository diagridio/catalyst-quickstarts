import asyncio
import logging
import uuid
from typing import List
from pydantic import BaseModel, Field
from dapr_agents import tool, DurableAgent
from dapr_agents.llm.dapr import DaprChatClient

from dapr_agents.memory import ConversationDaprStateMemory
from dotenv import load_dotenv

# Define tool output model
class FlightOption(BaseModel):
    airline: str = Field(description="Airline name")
    price: float = Field(description="Price in USD")

# Define tool input model
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

async def main():

    travel_assistant = DurableAgent(
        name="travel-assistant-agent",
        role="Travel Assistant",
        goal="Help users plan trips by finding flights",
        instructions=[
            "Understand user travel intent even if input is incomplete",
            "Remember user preferences for future queries",
            "Search for flights based on context"
        ],
        tools=[search_flights],

        llm = DaprChatClient(component_name="openai"),

        # Execution state (workflow progress, retries, failure recovery)
        state_store_name="statestore",
        state_key="execution-headless",

        # Long-term memory (preferences, past trips, context continuity)
        memory=ConversationDaprStateMemory(
            session_id=f"session-headless-{uuid.uuid4().hex[:8]}"
        ),

        # PubSub input for real-time interaction
        message_bus_name="message-pubsub",

        # Agent discovery store
        agents_registry_store_name="registry-state",
    )

    try:
        # start REST endpoint
        travel_assistant.as_service(port=5001)
        await travel_assistant.start()
        print("Travel Assistant Agent is running")

    except Exception as e:
        print(f"Error starting service: {e}")

if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())


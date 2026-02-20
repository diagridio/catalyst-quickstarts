import asyncio
import logging
from typing import List

from pydantic import BaseModel, Field

from dapr_agents import DurableAgent, tool
from dapr_agents.llm import DaprChatClient
from dapr_agents.workflow.runners import AgentRunner
from dapr_agents.workflow.utils.core import wait_for_shutdown


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
        llm=DaprChatClient(component_name="agent-llm-provider"),
    )

    print("Travel Assistant Agent is running")

    runner = AgentRunner()
    try:
        runner.subscribe(travel_assistant)
        runner.serve(travel_assistant, port=8001)
    finally:
        runner.shutdown()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting gracefully...")

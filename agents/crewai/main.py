import logging
import os

logging.basicConfig(level=logging.DEBUG)

from crewai import Agent
from crewai.tools import tool
from diagrid.agent.crewai import DaprWorkflowAgentRunner


@tool("Search venues")
def search_venues(city: str, capacity: int) -> str:
    """Search for event venues in a city with given capacity."""
    return (
        f"Found 3 venues in {city} for {capacity} guests:\n"
        f"1. Grand Ballroom - $5,000/day, capacity {capacity+20}\n"
        f"2. Riverside Conference Center - $3,500/day, capacity {capacity+10}\n"
        f"3. Downtown Loft Space - $2,000/day, capacity {capacity}"
    )


agent = Agent(
    role="Venue Scout",
    goal="Search for event venues by city and guest capacity using the search_venues tool. Return venue names, pricing, and capacity.",
    backstory="You are an expert venue finder with knowledge of event spaces across major cities. When asked to find a venue, always use the search_venues tool with the city name and expected number of guests.",
    tools=[search_venues],
)
runner = DaprWorkflowAgentRunner(agent=agent)
runner.serve(port=int(os.environ.get("APP_PORT", "8001")))

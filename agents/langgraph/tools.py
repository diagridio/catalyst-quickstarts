"""The agent's tools.

Separate from main.py so the tests can import the real tool without paying for
main.py's module-level DaprWorkflowGraphRunner, whose constructor health-checks
the Dapr sidecar and retries for about two minutes when there is not one.
"""

from langchain_core.tools import tool


@tool
def check_availability(venue: str, date: str) -> str:
    """Check venue availability for a specific date."""
    return f"{venue} is available on {date}. Time slots: 9AM-1PM, 2PM-6PM, 6PM-11PM."


tools = [check_availability]
tools_by_name = {t.name: t for t in tools}

"""The agent's tools.

Separate from main.py so the tests can import the real tool without paying for
main.py's module-level work: importing main.py installs the identity middleware
and compiles the graph.

Nothing here reaches the network or the Dapr sidecar. The tool takes the calling
user's subject as an ordinary argument, and main.py's `call_tools` node is what
fills that argument in from the verified identity.
"""

from langchain_core.tools import tool


@tool
def my_bookings(subject: str) -> str:
    """List the bookings that belong to the calling user."""
    return (
        f"Bookings for {subject}: "
        "Grand Ballroom on March 15th, 9AM-1PM; "
        "Rooftop Terrace on March 22nd, 6PM-11PM."
    )


tools = [my_bookings]
tools_by_name = {t.name: t for t in tools}

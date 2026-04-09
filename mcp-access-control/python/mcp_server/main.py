import os

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mcp-access-control-demo", host="0.0.0.0", port=8000, stateless_http=True)

DAPR_HTTP_ENDPOINT = os.getenv("DAPR_HTTP_ENDPOINT", "http://localhost")
DAPR_API_TOKEN = os.getenv("DAPR_API_TOKEN", "")
WEATHER_URL = f"{DAPR_HTTP_ENDPOINT}/v1.0/invoke/weather-service/method/weather-alert"


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b


@mcp.tool()
def get_weather_alert(city: str) -> str:
    """Get a weather alert for a given city."""
    try:
        headers = {"dapr-api-token": DAPR_API_TOKEN}
        with httpx.Client() as client:
            resp = client.post(WEATHER_URL, json={"city": city}, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data.get("alert", f"No active alerts for {city}")
    except Exception as e:
        return f"Error fetching weather alert: {e}"


@mcp.tool()
def echo(message: str) -> str:
    """Echo back a message."""
    return f"Echo: {message}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

ALERTS = {
    "new york": "Heat advisory in effect until 8 PM EDT",
    "chicago": "Severe thunderstorm warning until 6 PM CDT",
    "los angeles": "Air quality alert - moderate",
}


async def weather_alert(request: Request) -> JSONResponse:
    body = await request.json()
    city = body.get("city", "")
    alert = ALERTS.get(city.lower(), f"No active alerts for {city}")
    return JSONResponse({"city": city, "alert": alert})


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "healthy", "message": "Weather service is running"})


app = Starlette(
    routes=[
        Route("/", health, methods=["GET"]),
        Route("/weather-alert", weather_alert, methods=["POST"]),
    ]
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)

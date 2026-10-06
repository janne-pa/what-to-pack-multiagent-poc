"""Weather executor and model instructions."""

import json
from typing import Annotated, Any, Dict

from agent_framework import (
    ChatAgent,
    ChatMessage,
    Executor,
    FunctionResultContent,
    Role,
    WorkflowContext,
    ai_function,
    handler,
)
from pydantic import Field

from ..json_utils import safe_load_validated
from ..weather_service import WeatherService


WEATHER_INSTRUCTIONS = """You are a weather analysis expert for travel planning.
        Use get_weather to retrieve current temperature and wind for the destination.
        Estimate the destination's coordinates for the tool arguments; do not invent measurements.
        If coordinates are uncertain, do not guess or claim that weather was retrieved.
        Use only successful tool results for measured weather, and use the last successful
        result in tool-call order if there are multiple calls. Do not claim a forecast.
        If the tool is unavailable or fails, explicitly say that weather is unavailable.
        Write weather summaries and packing notes in English.
        After tool use, respond with the requested JSON only, without extra text or formatting."""


class WeatherAgent(Executor):
    """Agent that fetches weather information for the destination."""

    agent: ChatAgent
    weather_service: WeatherService

    def __init__(self, agent: ChatAgent, weather_service: WeatherService, id: str = "weather_agent"):
        self.agent = agent
        self.weather_service = weather_service
        super().__init__(id=id)

    @handler
    async def handle_travel_info(self, travel_info: Dict[str, Any], ctx: WorkflowContext[Dict[str, Any]]) -> None:
        """Let the model request current weather through a local MAF tool."""

        destination = travel_info.get("destination", "Unknown")
        print(f"🌤️  Weather Agent: Asking the model to check current weather for {destination}")
        tool_results: list[Dict[str, Any] | None] = []

        @ai_function(
            name="get_weather",
            description=(
                "Get current temperature in Celsius and wind speed in metres per second "
                "from Open-Meteo for geographic coordinates. This is not a travel-date forecast."
            ),
        )
        async def get_weather(
            latitude: Annotated[
                float, Field(strict=True, description="Latitude in decimal degrees, between -90 and 90.")
            ],
            longitude: Annotated[
                float, Field(strict=True, description="Longitude in decimal degrees, between -180 and 180.")
            ],
        ) -> Dict[str, Any]:
            # Reserve the result slot before awaiting: parallel calls can finish out of order.
            result_index = len(tool_results)
            tool_results.append(None)
            print(f"🔧 Tool call: get_weather(latitude={latitude}, longitude={longitude})")
            if not (
                type(latitude) in (int, float)
                and type(longitude) in (int, float)
                and -90 <= latitude <= 90
                and -180 <= longitude <= 180
            ):
                result = {
                    "status": "unavailable",
                    "error": "Invalid coordinates; latitude must be in [-90, 90] and longitude in [-180, 180].",
                }
            else:
                weather = await self.weather_service.get_weather_info_by_coords(latitude, longitude)
                if weather is None:
                    result = {"status": "unavailable", "error": "Open-Meteo current weather is unavailable."}
                else:
                    tool_results[result_index] = weather
                    result = {
                        "status": "ok",
                        "weather": weather,
                        "units": {"temperature": "Celsius", "wind_speed": "m/s"},
                        "scope": "current conditions, not a travel-date forecast",
                    }
            print("🔧 Tool result: get_weather -> " + json.dumps(result, ensure_ascii=False))
            return result

        weather_prompt = f"""
        Analyze current weather for the destination "{destination}".
        You have access to get_weather(latitude, longitude). Use it to obtain
        current temperature and wind before making claims about measured conditions.
        Do not infer rain or future conditions from temperature and wind alone.
        If you cannot get measurements, say that weather is unavailable and provide
        generic packing guidance instead. Do not fabricate a successful tool result.

        Provide thermal-comfort, layering and wind-protection advice in English.
        Return only JSON:
        {{"weather_summary": "short description", "packing_notes": ["item1", "item2", "item3"]}}
        """
        response = await self.agent.run(
            [ChatMessage(role="user", text=weather_prompt)],
            tools=[get_weather],
            tool_choice="auto",
        )
        for message in response.messages:
            for content in message.contents:
                if isinstance(content, FunctionResultContent) and content.exception is not None:
                    print(f"⚠️  Weather tool call {content.call_id} failed: {content.exception}")

        weather_data = next((result for result in reversed(tool_results) if result is not None), None)

        if weather_data is not None:
            temperature = weather_data.get("temperature")
            wind_speed = weather_data.get("wind_speed")
            analysis_text = next(
                (
                    message.text for message in reversed(response.messages)
                    if message.role == Role.ASSISTANT and message.text
                ),
                "",
            )
            weather_analysis, warnings = safe_load_validated(analysis_text, ["weather_summary", "packing_notes"])
            if warnings:
                print("⚠️  Weather analysis warnings: " + "; ".join(warnings))
            if not weather_analysis:
                weather_analysis = {
                    "weather_summary": f"Temp {temperature}°C, wind {wind_speed} m/s",
                    "packing_notes": ["Layer clothing appropriately", "Consider wind-resistant outerwear"],
                }
            print(f"🌡️  Current temperature: {temperature}°C; 💨 Wind: {wind_speed} m/s (Weather data by Open-Meteo.com)")
            complete_info = {**travel_info, "weather": weather_data, "weather_analysis": weather_analysis}
            await ctx.send_message(complete_info)
        else:
            print(
                f"⚠️  No successful get_weather tool result for {destination}; "
                "using generic packing guidance. Model-only weather claims are ignored."
            )
            complete_info = {
                **travel_info,
                "weather": None,
                "weather_analysis": {
                    "weather_summary": "Weather data unavailable",
                    "packing_notes": ["Pack for variable weather conditions"]
                }
            }
            await ctx.send_message(complete_info)

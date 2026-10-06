"""Weather service for fetching temperature and wind data via Open-Meteo."""

import asyncio
import math

import aiohttp
from typing import Optional, Dict, Any
from .config import AzureAIConfig


class WeatherService:
    """Weather data by Open-Meteo.com - Service for fetching weather data via Open-Meteo using coordinates.

    Reuses a single aiohttp.ClientSession for efficiency and proper cleanup.
    """

    def __init__(self, config: AzureAIConfig):  # config retained for future extensibility
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_weather_info_by_coords(self, latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
        """Fetch current weather metrics using Open-Meteo (no API key required).

        Args:
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees
        Returns:
            Dictionary containing temperature (°C) and wind speed (m/s) or None on failure.
        """
        base_url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,wind_speed_10m",
            "wind_speed_unit": "ms",
        }
        if not (
            type(latitude) in (int, float)
            and type(longitude) in (int, float)
            and -90 <= latitude <= 90
            and -180 <= longitude <= 180
        ):
            print("Open-Meteo error: invalid coordinates")
            return None
        try:
            session = await self._get_session()
            async with session.get(base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if not isinstance(data, dict):
                        raise ValueError("response must be a JSON object")
                    current = data.get("current")
                    units = data.get("current_units")
                    if not isinstance(current, dict) or not isinstance(units, dict):
                        raise ValueError("current weather or units missing")
                    temperature = current.get("temperature_2m")
                    wind_speed = current.get("wind_speed_10m")
                    if not all(
                        type(value) in (int, float) and math.isfinite(value)
                        for value in (temperature, wind_speed)
                    ):
                        raise ValueError("temperature or wind speed missing or invalid")
                    if wind_speed < 0:
                        raise ValueError("wind speed cannot be negative")
                    if units.get("temperature_2m") != "\u00b0C" or units.get("wind_speed_10m") != "m/s":
                        raise ValueError("unexpected weather units")
                    return {
                        "temperature": temperature,
                        "wind_speed": wind_speed,
                        "latitude": latitude,
                        "longitude": longitude,
                        "source": "open-meteo",
                    }
                else:
                    print(f"Open-Meteo error: {response.status}")
                    return None
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            print(f"Error fetching Open-Meteo data: {e}")
            return None
        
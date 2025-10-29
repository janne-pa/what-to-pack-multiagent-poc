"""Weather service for fetching temperature and wind data via Open-Meteo."""

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
            self._session = aiohttp.ClientSession()
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
        }
        try:
            session = await self._get_session()
            async with session.get(base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    current = data.get("current", {})
                    return {
                        "temperature": current.get("temperature_2m"),
                        "wind_speed": current.get("wind_speed_10m"),
                        "latitude": latitude,
                        "longitude": longitude,
                        "source": "open-meteo",
                    }
                else:
                    print(f"Open-Meteo error: {response.status}")
                    return None
        except Exception as e:  # noqa: BLE001
            print(f"Error fetching Open-Meteo data: {e}")
            return None
        
import asyncio
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from what_to_pack.weather_service import WeatherService


def weather_response():
    return {
        "current": {"temperature_2m": 12.3, "wind_speed_10m": 4.5},
        "current_units": {"temperature_2m": "\u00b0C", "wind_speed_10m": "m/s"},
    }


def service_with_response(data, status=200):
    service = WeatherService(None)
    response = MagicMock(status=status)
    response.json = AsyncMock(return_value=data)
    request = MagicMock()
    request.__aenter__ = AsyncMock(return_value=response)
    request.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.get.return_value = request
    service._get_session = AsyncMock(return_value=session)
    return service, session


def test_weather_requests_and_returns_metres_per_second():
    service, session = service_with_response(weather_response())
    result = asyncio.run(service.get_weather_info_by_coords(60.17, 24.94))
    assert result["temperature"] == 12.3
    assert result["wind_speed"] == 4.5
    assert result["source"] == "open-meteo"
    assert session.get.call_args.kwargs["params"]["wind_speed_unit"] == "ms"


@pytest.mark.parametrize("data", [None, [], {}, {"current": {}}, {"current": None}])
def test_missing_weather_is_not_presented_as_success(data, capsys):
    service, _ = service_with_response(data)
    assert asyncio.run(service.get_weather_info_by_coords(60, 24)) is None
    assert "Open-Meteo" in capsys.readouterr().out


@pytest.mark.parametrize("value", [None, True, "cold", float("nan"), float("inf")])
def test_invalid_measurement(value):
    data = weather_response()
    data["current"]["temperature_2m"] = value
    service, _ = service_with_response(data)
    assert asyncio.run(service.get_weather_info_by_coords(60, 24)) is None


def test_wrong_units():
    data = weather_response()
    data["current_units"]["wind_speed_10m"] = "km/h"
    service, _ = service_with_response(data)
    assert asyncio.run(service.get_weather_info_by_coords(60, 24)) is None


@pytest.mark.parametrize("status", [429, 500])
def test_http_error(status, capsys):
    service, _ = service_with_response({}, status=status)
    assert asyncio.run(service.get_weather_info_by_coords(60, 24)) is None
    assert str(status) in capsys.readouterr().out


@pytest.mark.parametrize("error", [asyncio.TimeoutError(), aiohttp.ClientError("offline")])
def test_network_failure(error, capsys):
    service, session = service_with_response({})
    session.get.side_effect = error
    assert asyncio.run(service.get_weather_info_by_coords(60, 24)) is None
    assert "Error fetching Open-Meteo data" in capsys.readouterr().out


@pytest.mark.parametrize("latitude,longitude", [(91, 0), (0, 181), (True, 0), (0, float("nan"))])
def test_invalid_coordinates_do_not_call_network(latitude, longitude):
    service, session = service_with_response({})
    assert asyncio.run(service.get_weather_info_by_coords(latitude, longitude)) is None
    session.get.assert_not_called()


def test_session_timeout_reuse_and_cleanup():
    async def exercise():
        service = WeatherService(None)
        session = await service._get_session()
        assert session.timeout.total == 10
        assert await service._get_session() is session
        await service.close()
        assert session.closed
        await service.close()

    asyncio.run(exercise())

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from agent_framework import (
    BaseChatClient,
    ChatAgent,
    ChatMessage,
    ChatResponse,
    FunctionCallContent,
    FunctionResultContent,
    use_function_invocation,
)

from what_to_pack.agents.weather_agent import WEATHER_INSTRUCTIONS, WeatherAgent


ANALYSIS = '{"weather_summary":"Cool current weather","packing_notes":["Coat"]}'
MEASUREMENTS = {
    "temperature": 12,
    "wind_speed": 4,
    "latitude": 60,
    "longitude": 24,
    "source": "open-meteo",
}


@use_function_invocation
class ScriptedClient(BaseChatClient):
    def __init__(self, *responses):
        super().__init__()
        self.responses = iter(responses)
        self.turns = []

    async def _inner_get_response(self, *, messages, chat_options, **kwargs):
        self.turns.append((list(messages), chat_options))
        return ChatResponse(messages=[next(self.responses)])

    async def _inner_get_streaming_response(self, *, messages, chat_options, **kwargs):
        raise AssertionError("The weather executor uses non-streaming agent.run")
        yield


def reply(text=ANALYSIS):
    return ChatMessage(role="assistant", text=text)


def call(latitude=60, longitude=24, call_id="weather-1"):
    return FunctionCallContent(
        call_id=call_id, name="get_weather",
        arguments={"latitude": latitude, "longitude": longitude},
    )


def tool_turn(*calls, text=None):
    return ChatMessage(role="assistant", contents=list(calls), text=text)


def setup(*responses, weather=MEASUREMENTS):
    client = ScriptedClient(*responses)
    agent = ChatAgent(chat_client=client, instructions=WEATHER_INSTRUCTIONS)
    service = SimpleNamespace(get_weather_info_by_coords=AsyncMock(return_value=weather))
    return WeatherAgent(agent, service), client, service


async def run(executor, destination="Helsinki"):
    ctx = SimpleNamespace(send_message=AsyncMock())
    await executor.handle_travel_info({"destination": destination}, ctx)
    return ctx.send_message.call_args.args[0]


def results_at(client, turn=1):
    return [
        content
        for message in client.turns[turn][0]
        for content in message.contents
        if isinstance(content, FunctionResultContent)
    ]


def test_real_sdk_executes_tool_and_returns_result_to_model(capsys):
    executor, client, service = setup(tool_turn(call(), text="I will check the weather."), reply())
    output = asyncio.run(run(executor))

    service.get_weather_info_by_coords.assert_awaited_once_with(60, 24)
    assert len(client.turns) == 2
    options = client.turns[0][1]
    assert options.tool_choice == "auto"
    tool = options.tools[0]
    assert tool.name == "get_weather"
    schema = tool.input_model.model_json_schema()
    assert set(schema["required"]) == {"latitude", "longitude"}
    assert schema["properties"]["latitude"]["type"] == "number"
    assert "decimal degrees" in schema["properties"]["latitude"]["description"]
    result = results_at(client)[0]
    assert result.call_id == "weather-1"
    assert result.result["status"] == "ok"
    assert result.result["weather"] == MEASUREMENTS
    assert result.result["units"] == {"temperature": "Celsius", "wind_speed": "m/s"}
    assert output["weather"] == MEASUREMENTS
    assert output["weather_analysis"]["weather_summary"] == "Cool current weather"
    trace = capsys.readouterr().out
    assert "Tool call: get_weather(latitude=60.0, longitude=24.0)" in trace
    assert "Tool result: get_weather" in trace
    assert '"temperature": 12' in trace


@pytest.mark.parametrize(
    "latitude,longitude",
    [(91, 0), (-91, 0), (0, 181), (0, -181), (float("nan"), 0), (0, float("inf"))],
)
def test_invalid_coordinates_return_explicit_error_without_http(latitude, longitude, capsys):
    executor, client, service = setup(tool_turn(call(latitude, longitude)), reply())
    output = asyncio.run(run(executor))
    service.get_weather_info_by_coords.assert_not_called()
    assert results_at(client)[0].result["status"] == "unavailable"
    assert output["weather"] is None
    assert "Invalid coordinates" in capsys.readouterr().out


@pytest.mark.parametrize("latitude", [True, None, "north", "60"])
def test_sdk_rejects_invalid_argument_types(latitude, capsys):
    executor, client, service = setup(tool_turn(call(latitude=latitude)), reply())
    output = asyncio.run(run(executor))
    service.get_weather_info_by_coords.assert_not_called()
    assert results_at(client)[0].exception is not None
    assert output["weather"] is None
    assert "failed:" in capsys.readouterr().out


def test_no_tool_call_discards_fabricated_weather(capsys):
    executor, client, service = setup(reply(
        '{"weather_summary":"It is 30 C","packing_notes":["Shorts"],'
        '"weather":{"temperature":30,"wind_speed":0}}'
    ))
    output = asyncio.run(run(executor))
    service.get_weather_info_by_coords.assert_not_called()
    assert len(client.turns) == 1
    assert output["weather"] is None
    assert output["weather_analysis"]["weather_summary"] == "Weather data unavailable"
    assert "generic packing guidance" in capsys.readouterr().out


def test_unavailable_weather_is_returned_to_model_and_uses_generic_guidance(capsys):
    executor, client, _ = setup(tool_turn(call()), reply(), weather=None)
    output = asyncio.run(run(executor))
    assert results_at(client)[0].result["status"] == "unavailable"
    assert output["weather"] is None
    assert "Open-Meteo current weather is unavailable" in capsys.readouterr().out


def test_invalid_analysis_retains_measurements():
    executor, _, _ = setup(tool_turn(call()), reply("null"))
    output = asyncio.run(run(executor))
    assert output["weather"] == MEASUREMENTS
    assert output["weather_analysis"]["weather_summary"] == "Temp 12°C, wind 4 m/s"


def test_executor_does_not_reuse_previous_weather():
    executor, _, service = setup(tool_turn(call()), reply(), reply())

    async def exercise():
        first = await run(executor)
        second = await run(executor, "London")
        assert first["weather"] == MEASUREMENTS
        assert second["weather"] is None

    asyncio.run(exercise())
    service.get_weather_info_by_coords.assert_awaited_once()


def test_multiple_calls_select_last_success_in_call_order_not_completion_order():
    executor, client, service = setup(
        tool_turn(call(10, 20, "first"), call(30, 40, "second")),
        tool_turn(call(50, 60, "unavailable")),
        reply(),
    )

    async def exercise():
        second_finished = asyncio.Event()

        async def fetch(latitude, longitude):
            if latitude == 10:
                await second_finished.wait()
            elif latitude == 30:
                second_finished.set()
            else:
                return None
            return {**MEASUREMENTS, "latitude": latitude, "longitude": longitude}

        service.get_weather_info_by_coords.side_effect = fetch
        output = await run(executor)
        assert output["weather"]["latitude"] == 30

    asyncio.run(exercise())
    assert service.get_weather_info_by_coords.await_count == 3
    assert [result.call_id for result in results_at(client)] == ["first", "second"]


def test_model_failures_propagate():
    executor, _, _ = setup()
    executor.agent.run = AsyncMock(side_effect=RuntimeError("model unavailable"))
    with pytest.raises(RuntimeError, match="model unavailable"):
        asyncio.run(run(executor))


def test_cancellation_propagates_during_tool_execution():
    executor, _, service = setup(tool_turn(call()), reply())
    service.get_weather_info_by_coords.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run(executor))

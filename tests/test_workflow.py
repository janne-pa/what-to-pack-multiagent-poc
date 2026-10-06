import asyncio
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from agent_framework import ChatAgent, ChatMessage
import pytest

from what_to_pack import main, workflow
from what_to_pack.agents.destination_agent import DESTINATION_INSTRUCTIONS, DestinationAgent
from what_to_pack.agents.packing_agent import PACKING_INSTRUCTIONS, PackingAgent
from what_to_pack.agents.weather_agent import WEATHER_INSTRUCTIONS, WeatherAgent


class FakeAgent:
    def __init__(self, *responses, weather_coordinates=None):
        self.responses = iter(responses)
        self.prompts = []
        self.closed = False
        self.weather_coordinates = weather_coordinates

    async def run(self, messages, **kwargs):
        self.prompts.append(messages[0].text)
        if self.weather_coordinates is not None:
            assert kwargs["tool_choice"] == "auto"
            await kwargs["tools"][0](**self.weather_coordinates)
        text = next(self.responses)
        return SimpleNamespace(text=text, messages=[ChatMessage(role="assistant", text=text)])

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True


def context():
    return SimpleNamespace(send_message=AsyncMock(), yield_output=AsyncMock())


@pytest.mark.parametrize("response", ["null", "[1]", "invalid", '{"destination":"Helsinki"}'])
def test_destination_failure_never_invents_paris(response):
    ctx = context()
    executor = DestinationAgent(FakeAgent(response))
    with pytest.raises(ValueError, match="specify one destination"):
        asyncio.run(executor.handle_user_input("Unclear travel request", ctx))
    ctx.send_message.assert_not_called()


def test_destination_preserves_original_request():
    ctx = context()
    executor = DestinationAgent(
        FakeAgent('{"destination":"London","duration":10,"travel_type":"business"}')
    )
    request = "Ten days in London next winter, with a formal dinner"
    asyncio.run(executor.handle_user_input(request, ctx))
    assert ctx.send_message.call_args.args[0]["original_request"] == request


@pytest.mark.parametrize("response", ["null", "[1]", '{"latitude":91,"longitude":0}'])
def test_no_tool_call_uses_visible_fallback(response, capsys):
    ctx = context()
    weather = SimpleNamespace(get_weather_info_by_coords=AsyncMock())
    executor = WeatherAgent(FakeAgent(response), weather)
    asyncio.run(executor.handle_travel_info({"destination": "London"}, ctx))
    weather.get_weather_info_by_coords.assert_not_called()
    assert ctx.send_message.call_args.args[0]["weather"] is None
    assert "No successful get_weather tool result" in capsys.readouterr().out


def test_invalid_analysis_uses_measured_weather_fallback():
    ctx = context()
    weather = SimpleNamespace(
        get_weather_info_by_coords=AsyncMock(
            return_value={"temperature": 12, "wind_speed": 4, "latitude": 60, "longitude": 24}
        )
    )
    executor = WeatherAgent(
        FakeAgent("null", weather_coordinates={"latitude": 60, "longitude": 24}), weather
    )
    asyncio.run(executor.handle_travel_info({"destination": "Helsinki"}, ctx))
    assert ctx.send_message.call_args.args[0]["weather_analysis"]["weather_summary"] == "Temp 12°C, wind 4 m/s"


def test_empty_packing_response_is_failure():
    ctx = context()
    executor = PackingAgent(FakeAgent(" "))
    with pytest.raises(RuntimeError, match="no recommendations"):
        asyncio.run(executor.handle_complete_info({}, ctx))
    ctx.yield_output.assert_not_called()


@pytest.fixture
def offline_workflow(monkeypatch):
    agents = (
        FakeAgent('{"destination":"Helsinki","duration":5,"travel_type":"business"}'),
        FakeAgent(
            '{"weather_summary":"Cool current weather","packing_notes":["Coat"]}',
            weather_coordinates={"latitude": 60.17, "longitude": 24.94},
        ),
        FakeAgent("Pack a coat and your passport."),
    )
    weather = SimpleNamespace(
        get_weather_info_by_coords=AsyncMock(
            return_value={"temperature": 12, "wind_speed": 4, "latitude": 60.17, "longitude": 24.94}
        ),
        close=AsyncMock(),
    )
    monkeypatch.setattr(workflow, "AzureAIConfig", lambda: SimpleNamespace(validate_config=lambda: True))
    monkeypatch.setattr(workflow, "DefaultAzureCredential", lambda: FakeAgent())
    monkeypatch.setattr(workflow, "WeatherService", lambda config: weather)
    monkeypatch.setattr(workflow, "create_agents", AsyncMock(return_value=agents))
    return agents, weather


@pytest.mark.parametrize(
    "travel_request",
    [
        "Five business days in Helsinki next winter, travelling with hand luggage",
        "Viiden päivän työmatka Helsinkiin ensi talvena, vain käsimatkatavarat",
    ],
)
def test_real_sdk_workflow_with_offline_agents(offline_workflow, travel_request):
    agents, weather = offline_workflow
    result = asyncio.run(workflow.run_multi_agent_workflow(travel_request))
    assert "Pack a coat and your passport." in result
    assert "Open-Meteo" in result
    assert "not a forecast for your travel dates" in result
    assert travel_request in agents[2].prompts[0]
    assert "Respond in English" in agents[2].prompts[0]
    assert all(agent.closed for agent in agents)
    weather.close.assert_awaited_once()


def test_real_sdk_workflow_without_weather(offline_workflow):
    agents, weather = offline_workflow
    weather.get_weather_info_by_coords.return_value = None
    result = asyncio.run(workflow.run_multi_agent_workflow("Five days in Helsinki"))
    assert "Weather data unavailable" in result
    assert len(agents[1].prompts) == 1
    weather.close.assert_awaited_once()


def test_workflow_cleans_up_after_agent_failure(offline_workflow):
    agents, weather = offline_workflow
    agents[0].run = AsyncMock(side_effect=RuntimeError("model unavailable"))
    with pytest.raises(Exception, match="model unavailable"):
        asyncio.run(workflow.run_multi_agent_workflow("Five days in Helsinki"))
    assert all(agent.closed for agent in agents)
    weather.close.assert_awaited_once()


def test_empty_request_is_rejected_before_azure():
    with pytest.raises(ValueError, match="empty request"):
        asyncio.run(workflow.run_multi_agent_workflow(" "))


def test_workflow_timeout(monkeypatch):
    async def expire(coroutine, timeout):
        coroutine.close()
        assert timeout == 120
        raise asyncio.TimeoutError

    monkeypatch.setattr(workflow.asyncio, "wait_for", expire)
    with pytest.raises(RuntimeError, match="120 seconds"):
        asyncio.run(workflow.run_with_timeout("Five days in Helsinki"))


def test_timeout_cancels_workflow_and_closes_resources(offline_workflow, monkeypatch):
    agents, weather = offline_workflow
    cancelled = []

    async def stalled_run(messages):
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.append(True)

    agents[0].run = stalled_run
    wait_for = asyncio.wait_for

    async def short_wait(coroutine, timeout):
        return await wait_for(coroutine, timeout=0.05)

    monkeypatch.setattr(workflow.asyncio, "wait_for", short_wait)
    with pytest.raises(RuntimeError, match="120 seconds"):
        asyncio.run(workflow.run_with_timeout("Five days in Helsinki"))
    assert cancelled == [True]
    assert all(agent.closed for agent in agents)
    weather.close.assert_awaited_once()


def test_workflow_without_output_is_failure(offline_workflow, monkeypatch):
    async def empty_stream(user_input):
        for event in []:
            yield event

    class EmptyBuilder:
        def set_start_executor(self, executor):
            return self

        def add_edge(self, source, target):
            return self

        def build(self):
            return SimpleNamespace(run_stream=empty_stream)

    monkeypatch.setattr(workflow, "WorkflowBuilder", EmptyBuilder)
    with pytest.raises(RuntimeError, match="without packing recommendations"):
        asyncio.run(workflow.run_multi_agent_workflow("Five days in Helsinki"))
    offline_workflow[1].close.assert_awaited_once()


def test_actual_azure_clients_can_be_constructed_and_closed_without_network(monkeypatch):
    factory = Mock(wraps=ChatAgent)
    monkeypatch.setattr(workflow, "ChatAgent", factory)

    async def exercise():
        config = SimpleNamespace(
            endpoint="https://example.services.ai.azure.com/api/projects/demo",
            model_deployment_name="gpt-4o-mini",
        )
        async with workflow.DefaultAzureCredential() as credential:
            agents = await workflow.create_agents(config, credential)
            assert len(agents) == 3
            async with agents[0], agents[1], agents[2]:
                assert all(isinstance(agent, ChatAgent) for agent in agents)
                assert [call.kwargs["instructions"] for call in factory.call_args_list] == [
                    DESTINATION_INSTRUCTIONS,
                    WEATHER_INSTRUCTIONS,
                    PACKING_INSTRUCTIONS,
                ]

    asyncio.run(exercise())


def test_cli_failure_exit_code(monkeypatch, capsys):
    monkeypatch.setattr(main.sys, "argv", ["what-to-pack", "my trip"])
    monkeypatch.setattr(main, "run_with_timeout", AsyncMock(side_effect=RuntimeError("model unavailable")))
    assert main.main() == 1
    assert "model unavailable" in capsys.readouterr().err


def test_cli_success(monkeypatch, capsys):
    monkeypatch.setattr(main.sys, "argv", ["what-to-pack", "Five days in Helsinki"])
    run = AsyncMock(return_value="Pack a coat.")
    monkeypatch.setattr(main, "run_with_timeout", run)
    assert main.main() == 0
    run.assert_awaited_once_with("Five days in Helsinki")
    output = capsys.readouterr().out
    assert "Pack a coat." in output
    assert "Weather data: current temperature and wind" in output


def test_cli_ctrl_c_during_prompt(monkeypatch):
    monkeypatch.setattr(main.sys, "argv", ["what-to-pack"])
    monkeypatch.setattr("builtins.input", lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert main.main() == 130


@pytest.mark.parametrize("entry_mode", ["script", "module"])
@pytest.mark.parametrize(
    ("arguments", "exit_code", "expected_text"),
    [
        (["--help"], 0, "Travel description; prompts if omitted"),
        ([" "], 1, "an empty request cannot be processed"),
    ],
)
def test_cli_entry_points_outside_repo(tmp_path, entry_mode, arguments, exit_code, expected_text):
    source_root = Path(__file__).resolve().parents[1].joinpath("src")
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    if entry_mode == "script":
        entry = [str(source_root.joinpath("what_to_pack", "main.py"))]
    else:
        entry = ["-m", "what_to_pack.main"]
        env["PYTHONPATH"] = str(source_root)

    result = subprocess.run(
        [sys.executable, *entry, *arguments],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == exit_code, result.stderr
    assert expected_text in result.stdout + result.stderr

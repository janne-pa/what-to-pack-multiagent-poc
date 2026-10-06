import pytest

from what_to_pack import config


@pytest.fixture
def clean_config(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("AZURE_AI_FOUNDRY_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", raising=False)


@pytest.mark.parametrize(
    "endpoint",
    [
        "",
        "your-foundry-project-endpoint-here",
        "https://example.openai.azure.com/",
        "http://example.services.ai.azure.com/api/projects/demo",
        "https://example.services.ai.azure.com/api/projects/",
        "https://user:password@example.services.ai.azure.com/api/projects/demo",
    ],
)
def test_invalid_endpoint(clean_config, monkeypatch, endpoint):
    monkeypatch.setenv("AZURE_AI_FOUNDRY_ENDPOINT", endpoint)
    assert not config.AzureAIConfig().validate_config()


def test_project_endpoint_and_default_model(clean_config, monkeypatch):
    monkeypatch.setenv(
        "AZURE_AI_FOUNDRY_ENDPOINT",
        "https://example.services.ai.azure.com/api/projects/demo",
    )
    settings = config.AzureAIConfig()
    assert settings.validate_config()
    assert settings.model_deployment_name == "gpt-4o-mini"


def test_empty_deployment_is_rejected(clean_config, monkeypatch):
    monkeypatch.setenv(
        "AZURE_AI_FOUNDRY_ENDPOINT",
        "https://example.services.ai.azure.com/api/projects/demo",
    )
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", " ")
    assert not config.AzureAIConfig().validate_config()


def test_dotenv_location_is_independent_of_working_directory(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(config, "load_dotenv", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.chdir(tmp_path)
    config.AzureAIConfig()
    path = calls[0][0][0]
    assert path.is_absolute()
    assert path.name == ".env"
    assert (path.parent / "requirements.txt").is_file()
    assert calls[0][1] == {"override": False}

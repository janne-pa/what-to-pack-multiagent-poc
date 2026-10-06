# What to Pack - Multi-Agent Packing Assistant

A local console demo that turns a travel description into an English packing
recommendation using Microsoft Agent Framework, Azure AI Foundry and Open-Meteo.
No web server or cloud application deployment is needed. Model calls still use
Azure and require internet access, an Azure login and an existing model deployment.

```text
Travel description -> DestinationAgent -> WeatherAgent -> PackingAgent -> Console
```

## Scope

- One destination city per request.
- Console messages and generated recommendations are in English, regardless of
  the input language. Travel advice assumes a Finnish citizen (EU).
- Live **current** temperature and wind, not a forecast for the travel dates.
- WeatherAgent exposes `get_weather(latitude, longitude)` as a model-selected
  function tool. The model requests the call; MAF executes Python locally and
  returns Open-Meteo measurements to the model for analysis.
- The original request, including travel timing, activities and preferences, is
  retained for the packing agent. Future-season advice is general guidance, not
  measured or forecast weather.
- Coordinates are estimated by the model; ambiguous place names should include
  a country. This is a demo, not a verified geocoding or travel-advisory service.
- Invalid destination responses stop with an error; the app never substitutes
  a made-up destination. Invalid coordinates, unavailable weather or a model
  response without a successful tool call produce a visible warning and generic
  packing guidance instead. Model-only weather claims are discarded.
- A run is limited to 120 seconds; the weather request has a 10-second timeout.

## Quick start: Windows PowerShell

Use Python 3.10 or newer and the Azure CLI. Run commands from the repository root.
An isolated virtual environment avoids changing your other Python projects.
Activation is optional: these commands use its Python executable directly.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Keep an existing configured `.env`; do not replace it with the template.
Otherwise, edit `.env` with your **Foundry project endpoint** and actual deployment name:

```dotenv
AZURE_AI_FOUNDRY_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-4o-mini
```

An endpoint such as `https://<resource>.openai.azure.com/` is an Azure OpenAI
resource endpoint and cannot be used as this client's project endpoint.
The deployment name must match the deployment in your project, even if its name
differs from the underlying model name. `.env` is ignored by Git. Existing shell
environment variables take precedence over `.env`.

```powershell
az login
az account set --subscription "<subscription-id>"
.\.venv\Scripts\python.exe src\what_to_pack\main.py
```

Your signed-in user needs access to the project's agents and model deployment
(typically the Azure AI User role at the appropriate resource/project scope).
The app uses `DefaultAzureCredential`; an existing service-principal or managed
identity configuration can take precedence over your Azure CLI login.

You can also pass the request directly, which is convenient for a prepared demo:

```powershell
.\.venv\Scripts\python.exe src\what_to_pack\main.py "A five-day business trip to Helsinki, carry-on luggage only."
```

On macOS/Linux, use `.venv/bin/python` and `src/what_to_pack/main.py` instead.
No `setup.py` or editable installation is required.

## Before presenting

Rehearse the exact command on the presentation machine with the actual Azure
project and network. The three agents run sequentially: destination extraction,
weather and packing recommendations. WeatherAgent uses `tool_choice="auto"`:
one agent run can contain multiple model/tool round trips, not just one model
request. Calls incur your deployment's normal Azure usage charges.

Confirm that the console produces a packing list and that current weather is
clearly distinguished from travel-date weather. Also try an empty request and
an unclear destination. Missing configuration, model failures and timeouts exit
with code 1; Ctrl+C exits with code 130. Weather-only failures are reported but
can still produce a generic packing list.

For the tool-calling highlight, look for `Tool call: get_weather(...)` followed
by `Tool result: get_weather -> ...` in the console. These show actual local
execution, arguments and returned measurements, not hidden model reasoning.
See the [architecture highlight](docs/ARCHITECTURE.md#architecture-highlight-model-selected-weather-tool)
for the cloud/local boundary and an illustrative trace. Auto-choice does not
guarantee that the model will call the tool on every run.

The SDK is deliberately pinned to the API generation used by this demo, rather
than installing the latest umbrella `agent-framework` package and all providers.
An SDK upgrade should be a separate, verified migration. Top-level dependencies
are pinned; this is not a complete transitive dependency lockfile.

## Offline regression tests

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Tests cover JSON contracts, configuration, weather units and failures, console
exit codes, the real framework workflow with fake agents and the real SDK
function-call loop with scripted model responses. They make
no Azure or weather requests and do not replace a live Azure rehearsal.

## Project structure

```text
src\what_to_pack\
    main.py                 Console entry point, input/output and exit codes
    workflow.py             Agent creation, lifetime and sequential MAF workflow
    agents\
        __init__.py
        destination_agent.py  Destination executor and model instructions
        weather_agent.py      Weather executor and model instructions
        packing_agent.py      Packing executor and model instructions
    config.py               Project configuration and .env loading
    weather_service.py      Current Open-Meteo conditions
    json_utils.py           JSON extraction and field validation
tests\                      Offline regression tests
requirements.txt            Runtime dependencies
requirements-dev.txt        Test dependencies
.env.example                Local configuration template
```

## Data attribution and license

Weather data is provided by [Open-Meteo](https://open-meteo.com/) under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Retain attribution
when redistributing weather-derived output.

Code is licensed under MIT; see `LICENSE`. Provided for demonstration and
educational purposes without warranty. See `docs/ARCHITECTURE.md` for design notes.

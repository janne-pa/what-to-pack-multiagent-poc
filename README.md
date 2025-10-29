# What to Pack – Multi-Agent Packing Assistant

Turns a free-form travel description into a tailored packing recommendation using:
1. Microsoft Agentic Framework
2. Azure AI Foundry (model deployment e.g. `gpt-4o-mini`)
3. Open-Meteo (live weather; no API key)

## 🤖 Pipeline Snapshot

User Input → DestinationAgent → WeatherAgent → PackingAgent → Output

DestinationAgent: JSON extraction (destination, duration, travel_type)
WeatherAgent: AI geocode → Open-Meteo fetch → AI weather analysis
PackingAgent: Final human-readable packing list

## 🏗️ Project Structure

```
what-to-pack-multiagent-poc/
├── src/
│   └── what_to_pack/
│       ├── __init__.py
│       ├── main.py              # Multi-agent workflow orchestration
│       ├── config.py            # Azure AI Foundry configuration
│       └── weather_service.py   # Weather data integration
├── requirements.txt
├── setup.py
├── .env.example                 # Environment variables template
├── .gitignore
└── README.md
```

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd what-to-pack-multiagent-poc
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Azure AI Foundry Configuration & Local Development

Weather data: Open-Meteo (no key). Only coords + temperature + wind used.

Local development via `.env` (auto-loaded by `config.py` using `python-dotenv`):
```
AZURE_AI_FOUNDRY_ENDPOINT=https://your-project.openai.azure.com/
AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-4o-mini
```

Precedence: shell variables override `.env`. Avoid storing secrets; only these non-sensitive values belong here.

### Weather & Geocoding
AI geocoding prompt → coords → Open-Meteo fetch → analysis prompt → packing notes. Fallback: generic notes if geocode/weather fails.

## 🔧 Usage

### Command Line Interface
```bash
python src/what_to_pack/main.py
```

### Example Interaction (Sample Output Flow)

```
✈️  Describe your travel plans: I'm planning a 10-day business trip to London in winter

🎯 Destination Agent: Extracting travel details...
🌤️  Weather Agent: Fetching weather for London...
🌡️  Current temperature: 8°C (light rain)
🎒 Packing Agent: Generating recommendations...
```

## 🏛️ Framework Integration

Microsoft Agentic Framework provides:
- Orchestrated multi-agent workflow execution
- Azure AI Foundry model access (enterprise managed endpoint)
- Event streaming (optional progress hooks)
- Future path for typed executors / tool calling

Conceptual graph:
```python
WorkflowBuilder()
   .set_start_executor(destination_agent)
   .add_edge(destination_agent, weather_agent)
   .add_edge(weather_agent, packing_agent)
   .build()
```

## 📦 Dependencies (Core)
`agent-framework-azure-ai`, `azure-identity`, `aiohttp`, `pytest`, `pytest-asyncio`

## 🛈 Data Attribution

Weather data provided by Open-Meteo (https://open-meteo.com/) under the
Creative Commons Attribution 4.0 International (CC BY 4.0) license. If you
redistribute or publicly expose derived weather outputs, include attribution
to Open-Meteo and reference the CC BY 4.0 terms.

## 📄 License

Code licensed under the MIT License. See the `LICENSE` file for full text.
Provided for demonstration and educational purposes; no warranty.

---

See `docs/ARCHITECTURE.md` for deeper design notes.

---
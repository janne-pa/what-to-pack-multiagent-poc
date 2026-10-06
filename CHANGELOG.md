# Changelog

All notable changes to this project will be documented here.

The format is inspired by Keep a Changelog and semantic versioning (future intent).

## [Unreleased]
### Fixed
- Use English consistently for console messages and agent responses, regardless of input language.
- Request and validate Open-Meteo wind in metres per second.
- Reject invalid model JSON and remove the fabricated Paris destination fallback.
- Retain the original travel request and label weather as current, not a trip forecast.
- Bound weather and workflow execution time; report console failures with non-zero exit codes.
- Load root `.env` consistently and validate the Foundry project endpoint and deployment name.
- Pin the framework API generation and install only the required Azure provider.
- Add offline regression tests, including real SDK workflow execution with fake agents.
- Replace stale setup instructions with local console and Azure login instructions.

### Planned
- Geocode caching (planned)
- Typed data models (planned)
- Tracing & logging improvements (planned)
### Changed
- Give WeatherAgent a model-selected `get_weather` function tool with visible call/result evidence, validated arguments and generic guidance when no call succeeds.
- Document the distinction between Sequential orchestration and local weather tool execution.
- Split agent executors and model instructions into `agents\*_agent.py` modules.
- Move agent creation and Sequential orchestration into `workflow.py`; keep `main.py` focused on the CLI.
- Removed unused dependency: `requests`
- Deleted onboarding helper script: `setup_azure.py`
- Removed obsolete `MockWeatherService` test stub
- Dropped `sys.path` insertion hack in `main.py`
- Cleaned banner encoding artifact in CLI output
- Reused single aiohttp session in `WeatherService` with explicit cleanup
- Added workflow `finally` block to close weather session
- Removed unused import `json` in `main.py`
- Clarified performance trade-offs in `docs/ARCHITECTURE.md`

## [0.1.0] - 2025-10-29
### Added
- Initial public release: multi-agent pipeline (Destination → Weather → Packing)
- Open-Meteo integration with AI geocoding
- Documentation: README, ARCHITECTURE, attribution, license
- Testing harness with mocks
- OSS governance docs (CODE_OF_CONDUCT, CONTRIBUTING, SECURITY, NOTICE)

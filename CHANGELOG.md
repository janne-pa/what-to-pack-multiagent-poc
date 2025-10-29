# Changelog

All notable changes to this project will be documented here.

The format is inspired by Keep a Changelog and semantic versioning (future intent).

## [Unreleased]
- Geocode caching (planned)
- Typed data models (planned)
- Tracing & logging improvements (planned)
### Changed
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

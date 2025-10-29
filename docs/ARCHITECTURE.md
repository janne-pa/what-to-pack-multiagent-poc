# Architecture Overview

## Purpose
This document explains the internal design of the Multi-Agent Travel Packing Assistant using Microsoft Agentic Framework and Azure AI Foundry. For onboarding and usage instructions see the root `README.md`.

## High-Level Flow
User Input → Destination Agent → Weather Agent (Geocode + Weather) → Packing Agent → Final Output

## Agents
- DestinationAgent: Extracts destination, duration, travel_type.
- WeatherAgent: Geocodes city to (lat, lon) via model JSON, calls Open-Meteo, performs weather analysis.
- PackingAgent: Produces narrative packing recommendations based on aggregated context.

## Prompts & JSON Contracts
| Stage | Prompt Output Keys | Notes |
|-------|--------------------|-------|
| Destination | destination, duration, travel_type | Strict JSON only response. Missing keys defaulted in executor. |
| Geocode | latitude, longitude, precision_km | precision_km is informational; only lat/lon required for success. |
| Weather Analysis | weather_summary, packing_notes[] | Fallback summary produced if JSON invalid.

## Weather Strategy
Open-Meteo (keyless) via coordinates resolved by the model. No alternative provider currently integrated.

## Validation & Parsing
`json_utils.safe_load_validated` extracts JSON (handles fenced blocks) then validates required keys, appending warnings without aborting. It returns a tuple of (data, warnings) used by agents to decide on fallbacks.

## Error Handling
- Config missing: raise `RuntimeError` early (fail fast).
- Malformed JSON: collect warnings, apply fallback.
- Missing coordinates: skip weather, provide generic packing notes.

## Extensibility Hooks
1. Coordinate caching: local `cache/geo.json` with TTL.
2. Structured models: Introduce Pydantic schemas for each contract.
3. Tracing: Add OpenTelemetry spans around agent executions and HTTP calls.
4. Persistence: Save packing summaries to a datastore (e.g., Azure Table Storage).

## Security Considerations
- No secrets committed; API key optional.
- Uses DefaultAzureCredential for secure auth flows.

## Performance Considerations
- WeatherAgent intentionally performs two model calls: (1) geocoding JSON, (2) weather interpretation & packing notes. Collapsing these into a single prompt reduces round‑trip latency but empirically harms reliability (harder JSON contract + mixed responsibilities). Keep separation unless latency is a strict requirement.
- Asynchronous I/O for the Open-Meteo request keeps the event loop responsive.
- Low-effort win: cache successful geocode results (e.g., in-memory dict or small file) to skip the first model call on repeated destinations.
- Further optimization could leverage a deterministic geocoding API for coordinates, reserving the model only for qualitative weather analysis.

## Testing Approach
- Unit tests mock ChatAgent responses to assert parsing logic.
- Coordinate flow test ensures geocode + weather path correctness without network.

---
Maintained under `docs/ARCHITECTURE.md`. Update when contracts or agent roles change. See `README.md` for quick start and operational guidance.

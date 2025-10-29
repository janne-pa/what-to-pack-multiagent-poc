"""Multi-Agent Travel Packing System using Microsoft Agentic Framework and Azure AI Foundry."""

import asyncio
import os
import sys
from typing import Dict, Any

# Runtime fallback: allow running via `python src/what_to_pack/main.py` without editable install.
# If package context missing, inject parent of `src` into sys.path so relative imports succeed.
if __package__ is None:  # script execution context
    # Insert the 'src' directory so 'what_to_pack' package can be found
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

from agent_framework import (
    ChatAgent,
    ChatMessage,
    Executor,
    WorkflowBuilder,
    WorkflowContext,
    WorkflowOutputEvent,
    WorkflowStatusEvent,
    WorkflowRunState,
    handler,
)
from agent_framework_azure_ai import AzureAIAgentClient
from azure.identity.aio import DefaultAzureCredential
from typing_extensions import Never

if __package__:
    # Package-relative imports (module invoked via -m)
    from .config import AzureAIConfig
    from .weather_service import WeatherService
    from .json_utils import safe_load_validated
else:
    # Script execution path fallback (absolute imports after path injection above)
    from what_to_pack.config import AzureAIConfig
    from what_to_pack.weather_service import WeatherService
    from what_to_pack.json_utils import safe_load_validated


class DestinationAgent(Executor):
    """Main agent that processes user input and extracts destination information."""
    
    agent: ChatAgent
    
    def __init__(self, agent: ChatAgent, id: str = "destination_agent"):
        self.agent = agent
        super().__init__(id=id)
    
    @handler
    async def handle_user_input(self, user_input: str, ctx: WorkflowContext[Dict[str, Any]]) -> None:
        """Process user input and extract destination information."""
        
        # Create a specific prompt to extract destination
        prompt = f"""
        Extract the destination city from the user's travel request: "{user_input}"
        
        Respond with a JSON object containing:
        - "destination": the city name (string)
        - "duration": estimated trip duration in days (integer, default to 7 if not specified)
        - "travel_type": type of travel like "business", "vacation", "adventure" (default to "vacation")
        
        Example response:
        {{"destination": "Paris", "duration": 5, "travel_type": "vacation"}}
        
        Only respond with the JSON object, no additional text.
        """
        
        messages = [ChatMessage(role="user", text=prompt)]
        response = await self.agent.run(messages)
        
        raw_text = response.messages[-1].contents[-1].text
        travel_info, warnings = safe_load_validated(raw_text, ["destination", "duration", "travel_type"])
        if warnings:
            print("⚠️  Destination parsing warnings: " + "; ".join(warnings))
        if not travel_info:
            # Fallback minimal info
            travel_info = {"destination": "Paris", "duration": 7, "travel_type": "vacation"}
        print(f"🎯 Destination Agent: Extracted travel info - {travel_info}")
        await ctx.send_message(travel_info)


class WeatherAgent(Executor):
    """Agent that fetches weather information for the destination."""
    
    agent: ChatAgent
    weather_service: WeatherService
    
    def __init__(self, agent: ChatAgent, weather_service: WeatherService, id: str = "weather_agent"):
        self.agent = agent
        self.weather_service = weather_service
        super().__init__(id=id)
    
    @handler
    async def handle_travel_info(self, travel_info: Dict[str, Any], ctx: WorkflowContext[Dict[str, Any]]) -> None:
        """Fetch weather information for the destination using AI geocoding + Open-Meteo."""

        destination = travel_info.get("destination", "Unknown")
        print(f"🌤️  Weather Agent: Resolving coordinates for {destination}")

        # Ask model to extract latitude/longitude for the destination city
        geo_prompt = f"""
        Provide geographic coordinates for the city "{destination}".
        Respond ONLY with JSON containing:
        {{"latitude": <decimal>, "longitude": <decimal>, "precision_km": <approximate precision in km>}}
        Do not include explanations.
        """
        geo_messages = [ChatMessage(role="user", text=geo_prompt)]
        geo_response = await self.agent.run(geo_messages)
        geo_raw = geo_response.messages[-1].contents[-1].text
        geo_data, geo_warnings = safe_load_validated(geo_raw, ["latitude", "longitude"])
        if geo_warnings:
            print("⚠️  Geo parsing warnings: " + "; ".join(geo_warnings))

        latitude = geo_data.get("latitude") if isinstance(geo_data.get("latitude"), (int, float)) else None
        longitude = geo_data.get("longitude") if isinstance(geo_data.get("longitude"), (int, float)) else None

        weather_data = None
        if latitude is not None and longitude is not None:
            print(f"📍 Resolved coordinates: lat={latitude}, lon={longitude}")
            weather_data = await self.weather_service.get_weather_info_by_coords(latitude, longitude)
        else:
            print("⚠️  Could not resolve coordinates; skipping weather fetch.")

        if weather_data:
            temperature = weather_data.get("temperature")
            wind_speed = weather_data.get("wind_speed")

            weather_prompt = f"""
            Analyze travel weather for {destination} at coordinates ({weather_data.get('latitude')}, {weather_data.get('longitude')}):
            - Temperature: {temperature}°C
            - Wind Speed: {wind_speed} m/s

            Provide packing insights considering:
            1. Thermal comfort and layering
            2. Wind conditions and protective gear
            3. Any seasonal context typical for this location

            Respond with JSON:
            {{"weather_summary": "short description", "packing_notes": ["item1", "item2", "item3"]}}
            """
            analysis_messages = [ChatMessage(role="user", text=weather_prompt)]
            analysis_resp = await self.agent.run(analysis_messages)
            analysis_raw = analysis_resp.messages[-1].contents[-1].text
            weather_analysis, warnings = safe_load_validated(analysis_raw, ["weather_summary", "packing_notes"])
            if warnings:
                print("⚠️  Weather analysis warnings: " + "; ".join(warnings))
            if not weather_analysis:
                weather_analysis = {
                    "weather_summary": f"Temp {temperature}°C, wind {wind_speed} m/s",
                    "packing_notes": ["Layer clothing appropriately", "Consider wind-resistant outerwear"],
                }
            print(f"🌡️  Current temperature: {temperature}°C; 💨 Wind: {wind_speed} m/s (Weather data by Open-Meteo.com)")
            complete_info = {**travel_info, "weather": weather_data, "weather_analysis": weather_analysis}
            await ctx.send_message(complete_info)
        else:
            print(f"⚠️  Could not fetch weather for {destination}")
            complete_info = {
                **travel_info,
                "weather": None,
                "weather_analysis": {
                    "weather_summary": "Weather data unavailable",
                    "packing_notes": ["Pack for variable weather conditions"]
                }
            }
            await ctx.send_message(complete_info)


class PackingAgent(Executor):
    """Agent that generates personalized packing recommendations."""
    
    agent: ChatAgent
    
    def __init__(self, agent: ChatAgent, id: str = "packing_agent"):
        self.agent = agent
        super().__init__(id=id)
    
    @handler
    async def handle_complete_info(self, complete_info: Dict[str, Any], ctx: WorkflowContext[Never, str]) -> None:
        """Generate final packing recommendations."""
        
        destination = complete_info.get("destination", "Unknown")
        duration = complete_info.get("duration", 7)
        travel_type = complete_info.get("travel_type", "vacation")
        weather_analysis = complete_info.get("weather_analysis", {})
        
        print(f"🎒 Packing Agent: Generating recommendations for {duration}-day {travel_type} trip to {destination}")
        
        # Create comprehensive packing prompt
        packing_prompt = f"""
        Create a comprehensive packing list for:
        - Destination: {destination}
        - Duration: {duration} days
        - Travel type: {travel_type}
        - Weather info: {weather_analysis.get('weather_summary', 'Weather data unavailable')}
        - Weather notes: {', '.join(weather_analysis.get('packing_notes', []))}
        
        Provide a detailed packing list organized by categories:
        1. Clothing (considering weather and trip type)
        2. Essential items (documents, electronics, etc.)
        3. Weather-specific gear
        4. Travel type specific items
        5. Optional items for comfort/convenience
        
        Format as a clear, organized list with explanations where helpful.
        Make it practical and personalized for this specific trip.
        """
        
        messages = [ChatMessage(role="user", text=packing_prompt)]
        response = await self.agent.run(messages)
        
        packing_recommendations = response.messages[-1].contents[-1].text
        
        # Create final output
        final_output = f"""
🎯 TRAVEL PLANNING SUMMARY
==========================
📍 Destination: {destination}
📅 Duration: {duration} days
🎭 Travel Type: {travel_type}
{f"🌡️  Weather: {weather_analysis.get('weather_summary', 'N/A')}" if weather_analysis.get('weather_summary') else ''}

🎒 PACKING RECOMMENDATIONS
==========================
{packing_recommendations}

✈️ Have a wonderful trip!
"""
        
        print("✅ Packing recommendations generated!")
        await ctx.yield_output(final_output)


async def create_agents(config: AzureAIConfig, credential: DefaultAzureCredential) -> tuple[ChatAgent, ChatAgent, ChatAgent]:
    """Create the three specialized agents using a shared Azure credential."""
    
    # Destination Agent
    destination_agent = ChatAgent(
        chat_client=AzureAIAgentClient(
            project_endpoint=config.endpoint,
            model_deployment_name=config.model_deployment_name,
            async_credential=credential,
            agent_name="DestinationAgent",
        ),
        instructions="""You are a travel planning specialist focused on destination analysis. 
        Your job is to extract and understand travel destinations from user requests.
        Always respond with valid JSON as requested, no additional text or formatting.""",
    )
    
    # Weather Agent
    weather_agent = ChatAgent(
        chat_client=AzureAIAgentClient(
            project_endpoint=config.endpoint,
            model_deployment_name=config.model_deployment_name,
            async_credential=credential,
            agent_name="WeatherAgent",
        ),
        instructions="""You are a weather analysis expert for travel planning.
        Analyze weather conditions and provide practical insights for travelers.
        Always respond with valid JSON as requested, no additional text or formatting.""",
    )
    
    # Packing Agent
    packing_agent = ChatAgent(
        chat_client=AzureAIAgentClient(
            project_endpoint=config.endpoint,
            model_deployment_name=config.model_deployment_name,
            async_credential=credential,
            agent_name="PackingAgent",
        ),
        instructions="""You are a professional travel packing consultant with extensive experience.
        Create comprehensive, practical packing lists tailored to specific destinations, weather, and trip types.
        Be detailed, organized, and helpful in your recommendations. Remember, your customer (user) is Finnish citizens (EU).""",
    )
    
    return destination_agent, weather_agent, packing_agent


async def run_multi_agent_workflow(user_input: str) -> str:
    """Run the complete multi-agent workflow. Requires valid Azure + Weather configuration."""

    # Get Azure AI Foundry configuration
    config = AzureAIConfig()

    # Enforce configuration presence
    if not config.validate_config():
        raise RuntimeError(
            "Missing required configuration. Please set AZURE_AI_FOUNDRY_ENDPOINT and AZURE_AI_MODEL_DEPLOYMENT_NAME.\n" +
            config.get_setup_instructions()
        )

    # Initialize weather service (then the actual REST calls happen inside the agent)
    weather_service = WeatherService(config)

    async with DefaultAzureCredential() as credential:
        try:
            # Create agents with shared credential
            destination_agent, weather_agent, packing_agent = await create_agents(config, credential)

            async with destination_agent, weather_agent, packing_agent:
                # Create executors:
                destination_executor = DestinationAgent(destination_agent)
                weather_executor = WeatherAgent(weather_agent, weather_service)
                packing_executor = PackingAgent(packing_agent)

                # Build workflow
                workflow = (
                    WorkflowBuilder()
                    .set_start_executor(destination_executor)
                    .add_edge(destination_executor, weather_executor)
                    .add_edge(weather_executor, packing_executor)
                    .build()
                )

                print("🚀 Starting multi-agent workflow...")

                final_output = ""
                async for event in workflow.run_stream(user_input):
                    if isinstance(event, WorkflowStatusEvent):
                        if event.state == WorkflowRunState.IN_PROGRESS:
                            print("⚙️  Workflow in progress...")
                    elif isinstance(event, WorkflowOutputEvent):
                        final_output = event.data
                        break
                return final_output
        finally:
            # Ensure weather service session cleanup
            await weather_service.close()


def main():
    """Main entry point for the application."""
    print("🧠 AI-Powered Travel Packing Assistant (Azure AI Foundry Required)")
    print("📝 Microsoft Agentic Framework with Azure AI Foundry")
    print("=" * 60)
    
    user_input = input("✈️  Describe your travel plans: ")
    
    if not user_input.strip():
        user_input = "I'm planning a 5-day vacation to Paris"
    
    # Run the async workflow
    try:
        result = asyncio.run(run_multi_agent_workflow(user_input))
        print("\n" + "=" * 60)
        print(result)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Configuration or runtime error: {e}")


if __name__ == "__main__":
    main()
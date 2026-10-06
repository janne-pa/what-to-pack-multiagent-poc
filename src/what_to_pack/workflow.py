"""Agent creation and sequential workflow orchestration."""

import asyncio

from agent_framework import (
    ChatAgent,
    WorkflowBuilder,
    WorkflowOutputEvent,
    WorkflowStatusEvent,
    WorkflowRunState,
)
from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import DefaultAzureCredential

from .agents.destination_agent import DESTINATION_INSTRUCTIONS, DestinationAgent
from .agents.packing_agent import PACKING_INSTRUCTIONS, PackingAgent
from .agents.weather_agent import WEATHER_INSTRUCTIONS, WeatherAgent
from .config import AzureAIConfig
from .weather_service import WeatherService


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
        instructions=DESTINATION_INSTRUCTIONS,
    )

    # Weather Agent
    weather_agent = ChatAgent(
        chat_client=AzureAIAgentClient(
            project_endpoint=config.endpoint,
            model_deployment_name=config.model_deployment_name,
            async_credential=credential,
            agent_name="WeatherAgent",
        ),
        instructions=WEATHER_INSTRUCTIONS,
    )

    # Packing Agent
    packing_agent = ChatAgent(
        chat_client=AzureAIAgentClient(
            project_endpoint=config.endpoint,
            model_deployment_name=config.model_deployment_name,
            async_credential=credential,
            agent_name="PackingAgent",
        ),
        instructions=PACKING_INSTRUCTIONS,
    )

    return destination_agent, weather_agent, packing_agent


async def run_multi_agent_workflow(user_input: str) -> str:
    """Run the complete multi-agent workflow with Azure and optional live weather."""

    if not user_input.strip():
        raise ValueError("Please describe your trip; an empty request cannot be processed.")

    # Get Azure AI Foundry configuration
    config = AzureAIConfig()

    # Enforce configuration presence
    if not config.validate_config():
        raise RuntimeError(
            "Invalid Azure configuration. Check AZURE_AI_FOUNDRY_ENDPOINT and AZURE_AI_MODEL_DEPLOYMENT_NAME.\n" +
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
                if not final_output.strip():
                    raise RuntimeError("The workflow completed without packing recommendations.")
                return final_output
        finally:
            # Ensure weather service session cleanup
            await weather_service.close()


async def run_with_timeout(user_input: str) -> str:
    try:
        return await asyncio.wait_for(run_multi_agent_workflow(user_input), timeout=120)
    except asyncio.TimeoutError as exc:
        raise RuntimeError(
            "The request exceeded 120 seconds. Check your Azure connection and try again."
        ) from exc

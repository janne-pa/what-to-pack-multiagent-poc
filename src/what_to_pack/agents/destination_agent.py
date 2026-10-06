"""Destination extraction executor and model instructions."""

from typing import Any, Dict

from agent_framework import ChatAgent, ChatMessage, Executor, WorkflowContext, handler

from ..json_utils import safe_load_validated


DESTINATION_INSTRUCTIONS = """You are a travel planning specialist focused on destination analysis.
        Your job is to extract and understand travel destinations from user requests.
        Use English for destination names and travel types, regardless of the input language.
        Always respond with valid JSON as requested, no additional text or formatting."""


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
        If no single destination can be determined, use null for "destination".
        Do not invent a destination or choose one of multiple destinations.
        """

        messages = [ChatMessage(role="user", text=prompt)]
        response = await self.agent.run(messages)

        raw_text = response.text
        travel_info, warnings = safe_load_validated(raw_text, ["destination", "duration", "travel_type"])
        if warnings:
            print("⚠️  Destination parsing warnings: " + "; ".join(warnings))
        if not travel_info:
            raise ValueError(
                "Could not determine valid travel details. Please specify one destination "
                "city and a positive trip duration, then try again."
            )
        travel_info["original_request"] = user_input
        print(f"🎯 Destination Agent: Extracted travel info - {travel_info}")
        await ctx.send_message(travel_info)

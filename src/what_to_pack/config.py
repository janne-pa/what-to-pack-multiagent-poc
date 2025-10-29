"""Configuration settings for Azure AI Foundry integration."""

import os
from typing import Optional

try:
    # Optional local development convenience. If python-dotenv is installed, load .env.
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    # Silent fail if dotenv not available; environment variables must be set externally.
    pass


class AzureAIConfig:
    """Configuration for Azure AI Foundry services.

    Weather provider configuration has been removed; the system now exclusively uses
    Open-Meteo (keyless) via coordinate-based queries.
    """

    def __init__(self):
        # Azure AI Foundry Project Settings
        self.endpoint: Optional[str] = os.getenv("AZURE_AI_FOUNDRY_ENDPOINT")
        self.model_deployment_name: Optional[str] = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
    
    def validate_config(self) -> bool:
        """Validate required configuration.

        Azure endpoint and model deployment are mandatory.
        """
        missing_configs = []

        if not self.endpoint:
            missing_configs.append("AZURE_AI_FOUNDRY_ENDPOINT")

        if missing_configs:
            print("Missing required environment variables:")
            for config in missing_configs:
                print(f"  - {config}")
            return False

        return True

    def get_setup_instructions(self) -> str:
        """Get setup instructions for required environment variables."""
        return """
Setup Instructions:

1. Azure AI Foundry Setup:
    - Create an Azure AI Foundry project: https://ai.azure.com
    - Deploy a model (recommended: gpt-4o-mini for cost efficiency)
    - Set environment variable: AZURE_AI_FOUNDRY_ENDPOINT=<your-project-endpoint>
    - Set environment variable: AZURE_AI_MODEL_DEPLOYMENT_NAME=<your-model-deployment-name>

2. Azure Authentication:
    - Install Azure CLI: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
    - Run: az login
    - The application will use DefaultAzureCredential for authentication

Environment variables can be set in:
- Windows: System Properties > Environment Variables
- Or create a .env file in the project root (not recommended for production)
"""
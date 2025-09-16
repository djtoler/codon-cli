"""
Configuration for agent card generation.
Centralizes tool descriptions and agent card customization.
"""

from typing import Dict, Optional
from pydantic import BaseModel, HttpUrl


# ---------- Tool Bundle Descriptions ----------
DEFAULT_TOOL_DESCRIPTIONS: Dict[str, str] = {
    "math": "Advanced mathematical calculations and numerical analysis",
    "social": "Emotional support, encouragement, and friendly conversation",
    "data": "Data analysis, processing, and statistical operations", 
    "retrieval": "Information search, research, and knowledge retrieval",
    "utilities": "General utility functions and everyday helpers",
    "ops": "System monitoring, health checks, and operational tasks",
    "general_support": "Comprehensive general assistance and support"
}


# ---------- Individual Tool Descriptions ----------
DEFAULT_INDIVIDUAL_TOOL_DESCRIPTIONS: Dict[str, str] = {
    "add": "Mathematical addition operations",
    "multiply": "Mathematical multiplication operations", 
    "greet_person": "Personalized greeting and social interaction",
    "random_number": "Generate random numbers for games and activities",
    "healthcheck": "System health monitoring and status checks"
}


# ---------- Configuration Class ----------
class AgentCardConfig(BaseModel):
    """Configuration for agent card generation with customizable descriptions."""
    
    # Add the missing 'base_url' attribute
    base_url: str = "http://localhost:9999"
    tool_bundle_descriptions: Dict[str, str] = DEFAULT_TOOL_DESCRIPTIONS.copy()
    individual_tool_descriptions: Dict[str, str] = DEFAULT_INDIVIDUAL_TOOL_DESCRIPTIONS.copy()
    
    def get_tool_description(self, tool_name: str) -> str:
        """Get description for an individual tool."""
        return self.individual_tool_descriptions.get(
            tool_name, 
            f"Tool: {tool_name}"
        )
    
    def get_bundle_description(self, bundle_name: str) -> str:
        """Get description for a tool bundle."""
        return self.tool_bundle_descriptions.get(
            bundle_name,
            f"Tool bundle: {bundle_name}"
        )
    
    def update_tool_descriptions(self, descriptions: Dict[str, str]):
        """Update individual tool descriptions."""
        self.individual_tool_descriptions.update(descriptions)
    
    def update_bundle_descriptions(self, descriptions: Dict[str, str]):
        """Update tool bundle descriptions."""
        self.tool_bundle_descriptions.update(descriptions)


# ---------- Factory Functions ----------
def get_default_config() -> AgentCardConfig:
    """Get default agent card configuration."""
    return AgentCardConfig()


def get_custom_config(
    tool_bundles: Optional[Dict[str, str]] = None,
    individual_tools: Optional[Dict[str, str]] = None,
    base_url: str = "http://localhost:9999"
) -> AgentCardConfig:
    """Get customized agent card configuration."""
    return AgentCardConfig(
        tool_bundle_descriptions=tool_bundles,
        individual_tool_descriptions=individual_tools,
        base_url=base_url
    )


# ---------- Environment-based Configuration ----------
def get_config_from_env() -> AgentCardConfig:
    """
    Load agent card configuration from environment variables.
    Future: Could read from env vars like AGENT_CARD_TOOL_DESCRIPTIONS
    """
    # For now, return default config
    # Future enhancement: parse env vars for custom descriptions
    return get_default_config()
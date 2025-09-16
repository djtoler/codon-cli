# agent_card_generator.py
"""
Dynamic agent card generation from RoleConfig data.
Converts role definitions into A2A agent cards.
"""

import json
import yaml
import uuid
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from pydantic import BaseModel, Field, HttpUrl

# Import official A2A Agent Card schema
from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    AgentExtension,
    AgentProvider,
)

from config.roles import RoleConfig, get_roles
from .a2a_card_config import AgentCardConfig, get_default_config


# Custom fallback classes (only used if needed for specific local functionality)
# These are kept for reference but are not used in the core logic anymore
# as the official A2A types are now used directly.
class CustomAgentCardCapabilities(BaseModel):
    """Custom agent capabilities and features."""

    streaming: bool = True
    extensions: Dict[str, Any] = Field(default_factory=dict)


class CustomAgentCardSkill(BaseModel):
    """Custom agent skill/capability."""

    name: str
    description: str
    tags: List[str] = Field(default_factory=list)


class CustomAgentCardSecurity(BaseModel):
    """Custom security and review requirements."""

    requires_human_review: bool = False
    max_tool_calls: int = 50
    allowed_tools_only: bool = True


class CustomAgentCard(BaseModel):
    """Custom A2A Agent Card schema for local extensions."""

    name: str
    description: str
    version: str = "1.0.0"
    provider: str
    documentation_url: Optional[HttpUrl] = None
    skills: List[CustomAgentCardSkill] = Field(default_factory=list)
    capabilities: CustomAgentCardCapabilities = Field(
        default_factory=CustomAgentCardCapabilities
    )
    security: CustomAgentCardSecurity = Field(
        default_factory=CustomAgentCardSecurity
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)
    supports_authenticated_extended_card: bool = False
    url: str = "http://localhost:9999"
    preferred_transport: str = "JSONRPC"


# ---------- YAML Upload Support ----------
def create_agent_card_from_yaml_content(yaml_content: str) -> AgentCard:
    """
    Create an AgentCard from YAML content string.
    Perfect for frontend file uploads.
    """
    try:
        # Parse YAML content
        yaml_data = yaml.safe_load(yaml_content)

        # Validate required fields
        required_fields = ["name", "description"]
        for field in required_fields:
            if field not in yaml_data:
                raise ValueError(f"Missing required field: {field}")

        # Create AgentCard with defaults for missing optional fields
        agent_card_data = {
            "version": yaml_data.get("version", "1.0.0"),
            "provider": yaml_data.get("provider", "User Upload"),
            "url": yaml_data.get("url", "http://localhost:9999"),
            "preferred_transport": yaml_data.get("preferred_transport", "JSONRPC"),
            "supports_authenticated_extended_card": yaml_data.get(
                "supports_authenticated_extended_card", False
            ),
            **yaml_data,
        }

        # Create and validate AgentCard using official A2A types
        # This will raise a Pydantic ValidationError if the data is not valid.
        agent_card = AgentCard(**agent_card_data)

        # This part of the code is also incorrect due to the missing 'metadata' field.
        # It's better to handle custom metadata by encapsulating it in an extension.
        # However, for a user-uploaded YAML, you may not have control over its format.
        # Let's assume the user-uploaded YAML is strictly adhering to the A2A spec.
        # If the user-uploaded YAML had a 'metadata' field, this would fail.
        # A more robust solution would involve a custom Pydantic model for validation
        # that allows the extra 'metadata' field. For now, let's assume the YAML
        # is spec-compliant.

        return agent_card

    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML format: {e}")
    except Exception as e:
        raise ValueError(f"Failed to create agent card from YAML: {e}")


def create_agent_card_from_yaml_file(yaml_file_path: str) -> AgentCard:
    """
    Create an AgentCard from a YAML file path.
    """
    try:
        with open(yaml_file_path, "r", encoding="utf-8") as f:
            yaml_content = f.read()
        return create_agent_card_from_yaml_content(yaml_content)
    except FileNotFoundError:
        raise ValueError(f"YAML file not found: {yaml_file_path}")
    except Exception as e:
        raise ValueError(f"Failed to read YAML file: {e}")


# ---------- Core Mapping Logic ----------
class AgentCardMapper:
    """Maps RoleConfig to AgentCard with configurable tool bundle descriptions."""

    def __init__(self, config: Optional[AgentCardConfig] = None):
        self.config = config or get_default_config()

    def map_role_to_agent_card(self, role_config: RoleConfig) -> AgentCard:
        """Convert a RoleConfig to an AgentCard using official A2A types."""

        # Build skills from tools and tool bundles
        skills = []

        # Add individual tools as skills
        for tool_name in role_config.tools:
            skills.append(
                AgentSkill(
                    id=f"tool_{tool_name}_{uuid.uuid4().hex[:8]}",
                    name=tool_name,
                    description=self.config.get_tool_description(tool_name),
                    tags=["tool"] + role_config.metadata.tags,
                )
            )

        # Add tool bundles as skills
        for bundle_name in role_config.tool_bundles:
            skills.append(
                AgentSkill(
                    id=f"bundle_{bundle_name}_{uuid.uuid4().hex[:8]}",
                    name=bundle_name,
                    description=self.config.get_bundle_description(bundle_name),
                    tags=["bundle"] + role_config.metadata.tags,
                )
            )

        # Define the base list of extensions
        extensions: list[AgentExtension] = [
            AgentExtension(
                uri="urn:a2a:extension:observability",
                description="Observability configuration.",
                params={
                    "tracing_enabled": role_config.observability.tracing_enabled,
                    "trace_tags": role_config.observability.trace_tags,
                },
            ),
            AgentExtension(
                uri="urn:a2a:extension:model_override",
                description="Overrides for the large language model.",
                params={"model_override": role_config.model.model_id},
            ),
            AgentExtension(
                uri="urn:a2a:extension:response_format",
                description="Response formatting hints.",
                params={"response_format": role_config.response_format},
            ),
        ]
        
        # Build custom metadata and encapsulate it within an AgentExtension
        custom_metadata_params = {
            "cost_hint": role_config.metadata.cost_hint,
            "latency_slo_ms": role_config.metadata.latency_slo_ms,
            "deprecation_status": role_config.metadata.deprecation_status,
            "role_tags": role_config.metadata.tags,
        }

        custom_metadata_extension = AgentExtension(
            uri="urn:a2a:extension:custom_metadata",
            description="Custom metadata and performance hints.",
            params=custom_metadata_params,
        )

        extensions.append(custom_metadata_extension)

        capabilities = AgentCapabilities(streaming=True, extensions=extensions)

        # Create official AgentCard
        card = AgentCard(
            name=role_config.name,
            description=role_config.system_prompt,
            version=role_config.metadata.version,
            provider=AgentProvider(
                organization=role_config.metadata.owner,
                url=role_config.metadata.docs_url or "https://example.com/docs",
            ),
            documentation_url=role_config.metadata.docs_url,
            skills=skills,
            capabilities=capabilities,
            default_input_modes=["text/plain", "application/json"],
            default_output_modes=["text/plain", "application/json"],
            # Use the base_url from the config object
            url=self.config.base_url,
        )

        return card


# ---------- Factory Functions ----------
def create_agent_card_for_role(
    role_name: str, config: Optional[AgentCardConfig] = None
) -> AgentCard:
    """Create an agent card for a specific role."""
    roles = get_roles()

    if role_name not in roles:
        available_roles = list(roles.keys())
        raise ValueError(
            f"Role '{role_name}' not found. Available roles: {available_roles}"
        )

    # Convert dict back to RoleConfig for mapping
    role_data = roles[role_name]
    role_config = RoleConfig(name=role_name, **role_data)

    mapper = AgentCardMapper(config)
    return mapper.map_role_to_agent_card(role_config)


def create_agent_card_dict_for_role(
    role_name: str, config: Optional[AgentCardConfig] = None
) -> Dict[str, Any]:
    """Create an agent card as a dictionary."""
    agent_card = create_agent_card_for_role(role_name, config)
    return agent_card.model_dump()


def generate_agent_card_for_executor(
    executor,
    fallback_yaml_path: str = "a2a_agent_card.yaml",
    config: Optional[AgentCardConfig] = None,
    is_ui_upload: bool = False,
    ui_yaml_content: Optional[str] = None,
    ui_yaml_path: Optional[str] = None,
) -> AgentCard:
    """
    Primary interface for servers to generate agent cards from executors.
    Now supports UI YAML uploads!
    
    Args:
        executor: The executor instance
        fallback_yaml_path: Default fallback YAML path
        config: Agent card configuration
        is_ui_upload: If True, use YAML from UI upload instead of role-based generation
        ui_yaml_content: YAML content as string (for direct upload)
        ui_yaml_path: Path to uploaded YAML file
    """

    card_config = config or get_default_config()

    # Handle UI YAML upload
    if is_ui_upload:
        try:
            print("📤 Processing UI YAML upload...")

            if ui_yaml_content:
                # Direct YAML content from frontend
                agent_card = create_agent_card_from_yaml_content(ui_yaml_content)
                print("✅ Agent card created from uploaded YAML content")
            elif ui_yaml_path:
                # YAML file path from frontend upload
                agent_card = create_agent_card_from_yaml_file(ui_yaml_path)
                print(f"✅ Agent card created from uploaded YAML file: {ui_yaml_path}")
            else:
                raise ValueError(
                    "UI upload mode requires either ui_yaml_content or ui_yaml_path"
                )

            # NOTE: We can no longer attach custom metadata to AgentCard this way due to Pydantic
            # validation. The A2A spec doesn't have a top-level 'metadata' field.

            return agent_card

        except Exception as e:
            print(f"❌ UI YAML upload failed: {e}")
            # Fall through to standard role-based generation as fallback
            print("🔄 Falling back to role-based generation...")

    # Standard role-based generation
    try:
        print(f"🤖 Generating dynamic agent card for role: {executor.role_name}")

        # Generate AgentCard object (not dict)
        agent_card = create_agent_card_for_role(executor.role_name, card_config)

        # NOTE: Removed the setattr for "metadata" here. Custom metadata is now handled
        # within the map_role_to_agent_card method by using AgentExtension.

        print(f"✅ Dynamic agent card generated for '{executor.role_name}'")
        return agent_card

    except Exception as e:
        print(f"⚠️ Failed to generate dynamic agent card: {e}")
        print(f"📄 Falling back to minimal agent card generation...")

        # UPDATED: Create a minimal agent card with valid A2A fields
        try:
            minimal_card = AgentCard(
                name=f"Agent ({executor.role_name})",
                description=f"SAOP agent for role: {executor.role_name}",
                version="1.0.0",
                provider=AgentProvider(
                    organization="SAOP Platform", url="http://localhost"
                ),
                skills=[],  # Empty skills for minimal card
                capabilities=AgentCapabilities(
                    streaming=True,
                    extensions=[
                        AgentExtension(
                            uri="urn:a2a:extension:status",
                            description="Status information for the fallback card.",
                            params={
                                "server_mode": "degraded" if executor.is_degraded() else "full",
                                "fallback_reason": str(e),
                                "actual_role": executor.role_name,
                                "source": "minimal_fallback",
                                "note": "Minimal agent card generated due to configuration issues",
                            },
                        )
                    ],
                ),
                default_input_modes=["text/plain"],
                default_output_modes=["text/plain"],
                url="http://localhost:9999",
            )

            print(f"✅ Minimal agent card generated for '{executor.role_name}'")
            return minimal_card

        except Exception as minimal_error:
            # Last resort: try YAML file if it exists
            try:
                if Path(fallback_yaml_path).exists():
                    fallback_card = create_agent_card_from_yaml_file(
                        fallback_yaml_path
                    )
                    
                    # NOTE: We can no longer attach custom metadata to AgentCard this way.
                    # This fallback path assumes the YAML is A2A spec-compliant.

                    return fallback_card
                else:
                    raise FileNotFoundError(
                        f"Fallback YAML not found: {fallback_yaml_path}"
                    )

            except Exception as fallback_error:
                raise RuntimeError(
                    f"All agent card generation methods failed. Dynamic: {e}, Minimal: {minimal_error}, Fallback: {fallback_error}"
                )


# Rest of the functions remain the same...
def validate_yaml_for_agent_card(yaml_content: str) -> Dict[str, Any]:
    """Validate YAML content for agent card creation."""
    result = {"valid": False, "errors": [], "warnings": [], "preview": None}

    try:
        yaml_data = yaml.safe_load(yaml_content)

        required_fields = ["name", "description"]
        missing_fields = [field for field in required_fields if field not in yaml_data]

        if missing_fields:
            result["errors"].append(
                f"Missing required fields: {', '.join(missing_fields)}"
            )

        recommended_fields = ["version", "provider", "skills"]
        missing_recommended = [
            field for field in recommended_fields if field not in yaml_data
        ]

        if missing_recommended:
            result["warnings"].append(
                f"Missing recommended fields: {', '.join(missing_recommended)}"
            )

        if not result["errors"]:
            try:
                agent_card = create_agent_card_from_yaml_content(yaml_content)
                result["valid"] = True
                result["preview"] = {
                    "name": agent_card.name,
                    "description": (
                        agent_card.description[:100] + "..."
                        if len(agent_card.description) > 100
                        else agent_card.description
                    ),
                    "skills_count": len(agent_card.skills),
                    "version": agent_card.version,
                    "provider": agent_card.provider.organization,
                }
            except Exception as e:
                result["errors"].append(f"Card creation failed: {e}")

    except yaml.YAMLError as e:
        result["errors"].append(f"Invalid YAML syntax: {e}")
    except Exception as e:
        result["errors"].append(f"Validation error: {e}")

    return result


def create_agent_card_from_upload(
    file_content: Union[str, bytes], filename: str = "upload.yaml"
) -> Dict[str, Any]:
    """
    Create agent card from frontend file upload.
    Handles both string and bytes content.
    Returns result suitable for JSON response.
    """
    try:
        # Convert bytes to string if needed
        if isinstance(file_content, bytes):
            yaml_content = file_content.decode("utf-8")
        else:
            yaml_content = file_content

        # Validate first
        validation = validate_yaml_for_agent_card(yaml_content)

        if not validation["valid"]:
            return {
                "success": False,
                "error": "Validation failed",
                "validation": validation,
            }

        # Create agent card
        agent_card = create_agent_card_from_yaml_content(yaml_content)

        return {
            "success": True,
            "agent_card": agent_card.model_dump(),
            "validation": validation,
            "metadata": {"filename": filename, "created_from": "upload"},
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "validation": {"valid": False, "errors": [str(e)]},
        }


# ---------- Card Generation Functions ----------
def generate_all_agent_cards(output_dir: str = "generated_agent_cards") -> Dict[str, str]:
    """Generate agent cards for all available roles."""

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    roles = get_roles()
    generated_files = {}

    print(f"🎭 Generating agent cards for {len(roles)} roles...")

    for role_name in roles.keys():
        try:
            # Generate agent card
            agent_card = create_agent_card_dict_for_role(role_name)

            # Save to file
            filename = f"{role_name}_agent_card.json"
            filepath = output_path / filename

            with open(filepath, "w") as f:
                json.dump(agent_card, f, indent=2, default=str)

            generated_files[role_name] = str(filepath)
            print(f"✅ Generated: {filename}")

        except Exception as e:
            print(f"❌ Failed to generate card for '{role_name}': {e}")

    return generated_files


def generate_agent_card_for_role_to_file(
    role_name: str, output_file: str = None
) -> str:
    """Generate agent card for a specific role and save to file."""

    if output_file is None:
        output_file = f"{role_name}_agent_card.json"

    try:
        agent_card = create_agent_card_dict_for_role(role_name)

        with open(output_file, "w") as f:
            json.dump(agent_card, f, indent=2, default=str)

        print(f"✅ Generated agent card for '{role_name}': {output_file}")
        return output_file

    except Exception as e:
        print(f"❌ Failed to generate card for '{role_name}': {e}")
        raise


# ---------- Main Execution ----------
def main():
    """Generate agent cards when run directly."""
    print("🚀 Agent Card Generator")
    print("=" * 40)

    try:
        # Generate all agent cards
        generated_files = generate_all_agent_cards()

        print(f"\n🎉 Successfully generated {len(generated_files)} agent cards:")
        for role_name, filepath in generated_files.items():
            print(f"  📄 {role_name}: {filepath}")

        # Also generate a summary file
        summary = {
            "generated_at": str(Path.cwd()),
            "total_roles": len(generated_files),
            "files": generated_files,
            "available_roles": list(get_roles().keys()),
        }

        with open("generated_agent_cards/summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        print(f"\n📋 Summary saved: generated_agent_cards/summary.json")

    except Exception as e:
        print(f"💥 Generation failed: {e}")
        raise


if __name__ == "__main__":
    main()
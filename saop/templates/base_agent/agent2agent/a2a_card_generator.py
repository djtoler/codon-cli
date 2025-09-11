# agent_card_generator.py
"""
Dynamic agent card generation from RoleConfig data.
Converts role definitions into A2A agent cards.

Run this file directly to generate agent cards for all roles.
"""

import json
import yaml
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

from config.roles import RoleConfig, get_roles
from .a2a_card_config import AgentCardConfig, get_default_config

# Import official A2A Agent Card schema
try:
    from a2a.types import AgentCard, AgentCardCapabilities, AgentCardSkill, AgentCardSecurity
    print("✅ Using official A2A agent card schema")
except ImportError:
    print("⚠️ Official A2A schema not available, using local schema")
    # Fallback to local schema definitions
    from pydantic import BaseModel, Field, HttpUrl
    
    class AgentCardCapabilities(BaseModel):
        """Agent capabilities and features."""
        streaming: bool = True
        extensions: Dict[str, Any] = Field(default_factory=dict)
        
    class AgentCardSkill(BaseModel):
        """Individual agent skill/capability."""
        name: str
        description: str
        tags: List[str] = Field(default_factory=list)
        
    class AgentCardSecurity(BaseModel):
        """Security and review requirements."""
        requires_human_review: bool = False
        max_tool_calls: int = 50
        allowed_tools_only: bool = True

    class AgentCard(BaseModel):
        """A2A Agent Card schema."""
        name: str
        description: str
        version: str = "1.0.0"
        provider: str
        documentation_url: Optional[HttpUrl] = None
        skills: List[AgentCardSkill] = Field(default_factory=list)
        capabilities: AgentCardCapabilities = Field(default_factory=AgentCardCapabilities)
        security: AgentCardSecurity = Field(default_factory=AgentCardSecurity)
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
        required_fields = ['name', 'description']
        for field in required_fields:
            if field not in yaml_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Create AgentCard with defaults for missing optional fields
        agent_card_data = {
            'version': yaml_data.get('version', '1.0.0'),
            'provider': yaml_data.get('provider', 'User Upload'),
            'url': yaml_data.get('url', 'http://localhost:9999'),
            'preferred_transport': yaml_data.get('preferred_transport', 'JSONRPC'),
            'supports_authenticated_extended_card': yaml_data.get('supports_authenticated_extended_card', False),
            **yaml_data
        }
        
        # Create and validate AgentCard
        agent_card = AgentCard(**agent_card_data)
        
        # Add upload metadata
        agent_card.metadata.update({
            'source': 'yaml_upload',
            'upload_timestamp': str(Path.cwd()),
            'validation_status': 'success'
        })
        
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
        with open(yaml_file_path, 'r', encoding='utf-8') as f:
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
        """Convert a RoleConfig to an AgentCard."""
        
        # Build skills from tools and tool bundles
        skills = []
        
        # Add individual tools as skills
        for tool_name in role_config.tools:
            skills.append(AgentCardSkill(
                name=tool_name,
                description=self.config.get_tool_description(tool_name),
                tags=["tool"] + role_config.metadata.tags
            ))
        
        # Add tool bundles as skills  
        for bundle_name in role_config.tool_bundles:
            skills.append(AgentCardSkill(
                name=bundle_name,
                description=self.config.get_bundle_description(bundle_name),
                tags=["bundle"] + role_config.metadata.tags
            ))
        
        # Build capabilities
        capabilities = AgentCardCapabilities(
            streaming=True,  # Default for LangGraph
            extensions={
                "tracing_enabled": role_config.observability.tracing_enabled,
                "trace_tags": role_config.observability.trace_tags,
                "model_override": role_config.model.model_id,
                "response_format": role_config.response_format
            }
        )
        
        # Build security settings
        security = AgentCardSecurity(
            requires_human_review=role_config.human_review,
            max_tool_calls=role_config.guardrails.max_tool_calls,
            allowed_tools_only=role_config.guardrails.allowed_tools_only
        )
        
        # Build metadata with performance hints
        metadata = {
            "cost_hint": role_config.metadata.cost_hint,
            "latency_slo_ms": role_config.metadata.latency_slo_ms,
            "deprecation_status": role_config.metadata.deprecation_status,
            "role_tags": role_config.metadata.tags
        }

        card = AgentCard(
            name=role_config.name,
            description=role_config.system_prompt,
            version=role_config.metadata.version,
            provider=role_config.metadata.owner,
            documentation_url=role_config.metadata.docs_url,
            skills=skills,
            capabilities=capabilities,
            security=security,
            metadata=metadata
        )

        return card


# ---------- Factory Functions ----------
def create_agent_card_for_role(role_name: str, 
                             config: Optional[AgentCardConfig] = None) -> AgentCard:
    """Create an agent card for a specific role."""
    roles = get_roles()
    
    if role_name not in roles:
        available_roles = list(roles.keys())
        raise ValueError(f"Role '{role_name}' not found. Available roles: {available_roles}")
    
    # Convert dict back to RoleConfig for mapping
    role_data = roles[role_name]
    role_config = RoleConfig(
        name=role_name,
        **role_data  
    )
    
    mapper = AgentCardMapper(config)
    return mapper.map_role_to_agent_card(role_config)


def create_agent_card_dict_for_role(role_name: str, 
                                  config: Optional[AgentCardConfig] = None) -> Dict[str, Any]:
    """Create an agent card as a dictionary (compatible with existing A2A infrastructure)."""
    agent_card = create_agent_card_for_role(role_name, config)
    return agent_card.model_dump()


def generate_agent_card_for_executor(executor, 
                                   fallback_yaml_path: str = "a2a_agent_card.yaml",
                                   config: Optional[AgentCardConfig] = None,
                                   is_ui_upload: bool = False,
                                   ui_yaml_content: Optional[str] = None,
                                   ui_yaml_path: Optional[str] = None) -> AgentCard:
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
                raise ValueError("UI upload mode requires either ui_yaml_content or ui_yaml_path")
            
            # Add executor metadata for UI uploads
            agent_card.metadata.update({
                "server_mode": "degraded" if executor.is_degraded() else "full",
                "source": "ui_upload",
                "executor_role": executor.role_name if hasattr(executor, 'role_name') else "unknown"
            })
            
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
        
        # Enhance with executor-specific metadata
        agent_card.metadata.update({
            "server_mode": "degraded" if executor.is_degraded() else "full",
            "initialization_status": "success" if executor.is_initialized() else "degraded",
            "actual_role": executor.role_name,
            "source": "role_based",
            "initialization_error": executor.get_initialization_error() if executor.is_degraded() else None
        })
        
        print(f"✅ Dynamic agent card generated for '{executor.role_name}'")
        return agent_card
        
    except Exception as e:
        print(f"⚠️ Failed to generate dynamic agent card: {e}")
        print(f"📄 Falling back to static YAML: {fallback_yaml_path}")
        
        # Final fallback to static YAML
        try:
            fallback_card = create_agent_card_from_yaml_file(fallback_yaml_path)
            
            # Add executor metadata
            fallback_card.metadata.update({
                "server_mode": "degraded" if executor.is_degraded() else "full",
                "fallback_reason": str(e),
                "actual_role": executor.role_name,
                "source": "fallback_yaml"
            })
                
            return fallback_card
            
        except Exception as fallback_error:
            raise RuntimeError(f"All agent card generation methods failed. Dynamic: {e}, Fallback: {fallback_error}")


# ---------- Frontend Helper Functions ----------
def validate_yaml_for_agent_card(yaml_content: str) -> Dict[str, Any]:
    """
    Validate YAML content for agent card creation.
    Returns validation result for frontend feedback.
    """
    result = {
        "valid": False,
        "errors": [],
        "warnings": [],
        "preview": None
    }
    
    try:
        # Parse YAML
        yaml_data = yaml.safe_load(yaml_content)
        
        # Check required fields
        required_fields = ['name', 'description']
        missing_fields = [field for field in required_fields if field not in yaml_data]
        
        if missing_fields:
            result["errors"].append(f"Missing required fields: {', '.join(missing_fields)}")
        
        # Check optional but recommended fields
        recommended_fields = ['version', 'provider', 'skills']
        missing_recommended = [field for field in recommended_fields if field not in yaml_data]
        
        if missing_recommended:
            result["warnings"].append(f"Missing recommended fields: {', '.join(missing_recommended)}")
        
        # If no errors, create preview
        if not result["errors"]:
            try:
                agent_card = create_agent_card_from_yaml_content(yaml_content)
                result["valid"] = True
                result["preview"] = {
                    "name": agent_card.name,
                    "description": agent_card.description[:100] + "..." if len(agent_card.description) > 100 else agent_card.description,
                    "skills_count": len(agent_card.skills),
                    "version": agent_card.version,
                    "provider": agent_card.provider
                }
            except Exception as e:
                result["errors"].append(f"Card creation failed: {e}")
        
    except yaml.YAMLError as e:
        result["errors"].append(f"Invalid YAML syntax: {e}")
    except Exception as e:
        result["errors"].append(f"Validation error: {e}")
    
    return result


def create_agent_card_from_upload(file_content: Union[str, bytes], 
                                filename: str = "upload.yaml") -> Dict[str, Any]:
    """
    Create agent card from frontend file upload.
    Handles both string and bytes content.
    Returns result suitable for JSON response.
    """
    try:
        # Convert bytes to string if needed
        if isinstance(file_content, bytes):
            yaml_content = file_content.decode('utf-8')
        else:
            yaml_content = file_content
        
        # Validate first
        validation = validate_yaml_for_agent_card(yaml_content)
        
        if not validation["valid"]:
            return {
                "success": False,
                "error": "Validation failed",
                "validation": validation
            }
        
        # Create agent card
        agent_card = create_agent_card_from_yaml_content(yaml_content)
        
        return {
            "success": True,
            "agent_card": agent_card.model_dump(),
            "validation": validation,
            "metadata": {
                "filename": filename,
                "created_from": "upload"
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "validation": {"valid": False, "errors": [str(e)]}
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
            
            with open(filepath, 'w') as f:
                json.dump(agent_card, f, indent=2, default=str)
            
            generated_files[role_name] = str(filepath)
            print(f"✅ Generated: {filename}")
            
        except Exception as e:
            print(f"❌ Failed to generate card for '{role_name}': {e}")
    
    return generated_files


def generate_agent_card_for_role_to_file(role_name: str, output_file: str = None) -> str:
    """Generate agent card for a specific role and save to file."""
    
    if output_file is None:
        output_file = f"{role_name}_agent_card.json"
    
    try:
        agent_card = create_agent_card_dict_for_role(role_name)
        
        with open(output_file, 'w') as f:
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
            "available_roles": list(get_roles().keys())
        }
        
        with open("generated_agent_cards/summary.json", 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n📋 Summary saved: generated_agent_cards/summary.json")
        
    except Exception as e:
        print(f"💥 Generation failed: {e}")
        raise


if __name__ == "__main__":
    main()
# agent_card_generator.py
"""
Dynamic agent card generation from RoleConfig data.
Converts role definitions into A2A agent cards.

Run this file directly to generate agent cards for all roles.
"""

import json
from typing import Dict, List, Optional, Any
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
        supports_authenticated_extended_card: bool = False  # Add this missing field
        url: str = "http://localhost:9999"  # Add required URL field
        preferred_transport: str = "JSONRPC"  # Add preferred transport


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

        print("CARD: ", card)
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
                                   config: Optional[AgentCardConfig] = None) -> AgentCard:  # Return AgentCard, not Dict
    """
    Primary interface for servers to generate agent cards from executors.
    """
    
    card_config = config or get_default_config()
    
    try:
        print(f"🤖 Generating dynamic agent card for role: {executor.role_name}")
        
        # Generate AgentCard object (not dict)
        agent_card = create_agent_card_for_role(executor.role_name, card_config)
        
        # Enhance with executor-specific metadata
        agent_card.metadata.update({
            "server_mode": "degraded" if executor.is_degraded() else "full",
            "initialization_status": "success" if executor.is_initialized() else "degraded",
            "actual_role": executor.role_name,
            "initialization_error": executor.get_initialization_error() if executor.is_degraded() else None
        })
        
        print(f"✅ Dynamic agent card generated for '{executor.role_name}'")
        return agent_card  # Return the object, not dict
        
    except Exception as e:
        print(f"⚠️ Failed to generate dynamic agent card: {e}")
        print(f"📄 Falling back to static YAML: {fallback_yaml_path}")
        
        # Fallback should also return AgentCard object
        try:
            from agent2agent.a2a_utils import create_agent_card_from_yaml_file
            fallback_card_dict = create_agent_card_from_yaml_file(fallback_yaml_path)
            
            # Convert dict to AgentCard object
            fallback_card = AgentCard(**fallback_card_dict)
            
            # Add executor metadata
            try:
                fallback_card.metadata.update({
                    "server_mode": "degraded" if executor.is_degraded() else "full",
                    "fallback_reason": str(e),
                    "actual_role": executor.role_name
                })
            except:
                pass
                
            return fallback_card
            
        except ImportError:
            raise RuntimeError(f"Dynamic agent card failed and fallback YAML import failed: {e}")


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
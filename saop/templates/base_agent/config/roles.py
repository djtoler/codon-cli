# roles.py
"""
Role definitions for your agent factory system.
Defines specialized agents with different tool access and personalities.
"""

from __future__ import annotations
from typing import List, Optional, Dict, Literal
from pydantic import BaseModel, Field, HttpUrl

# Import prompt components from the dedicated vars file
from .vars import (
    ToolUsageMode,
    CommunicationStyle,
    build_system_prompt
)


# ---------- Response schemas ----------
class MathResult(BaseModel):
    """Schema for mathematical operations."""
    result: float
    operation: str

# ---------- Model configuration ----------
class ModelConfig(BaseModel):
    """Role-level model override."""
    model_id: Optional[str] = Field(default=None)
    model_factory_path: Optional[str] = Field(default=None)

# ---------- Safety & observability ----------
class Guardrails(BaseModel):
    """Simple constraints for tool usage."""
    max_tool_calls: int = Field(50, ge=1, le=500)
    allowed_tools_only: bool = True

class Observability(BaseModel):
    """Telemetry controls for this role."""
    tracing_enabled: bool = True
    trace_tags: Dict[str, str] = Field(default_factory=dict)

# ---------- Routing metadata ----------
class Metadata(BaseModel):
    """Routing hints & ownership."""
    version: str = "1.0.0"
    owner: str = "your-team@company.com"
    tags: List[str] = Field(default_factory=list)
    docs_url: Optional[HttpUrl] = None
    deprecation_status: Literal["active", "deprecated", "sunset"] = "active"
    cost_hint: float = 1.0
    latency_slo_ms: int = 1000

# ---------- Main role configuration ----------
class RoleConfig(BaseModel):
    """Define an agent role for the factory."""
    name: str
    system_prompt: str = "You are a helpful assistant."
    tools: List[str] = Field(default_factory=list)
    tool_bundles: List[str] = Field(default_factory=list)
    model: ModelConfig = Field(default_factory=ModelConfig)
    response_format: Optional[str] = None
    human_review: bool = False
    observability: Observability = Field(default_factory=Observability)
    guardrails: Guardrails = Field(default_factory=Guardrails)
    metadata: Metadata = Field(default_factory=Metadata)


# ---------- Role catalog for your project ----------
CATALOG: List[RoleConfig] = [
    RoleConfig(
        name="general_support",
        system_prompt=build_system_prompt(
            role_description="You are a helpful and friendly general-purpose assistant. You can help with basic tasks, provide encouragement, check weather, and maintain a warm, conversational tone. Always be polite and helpful.",
            tool_usage_mode=ToolUsageMode.OPTIONAL,
            communication_style=CommunicationStyle.FRIENDLY,
        ),
        tool_bundles=["general_support", "utilities"],
        metadata=Metadata(tags=["general", "friendly", "utilities"], cost_hint=0.6, latency_slo_ms=800),
    ),
    
    RoleConfig(
        name="math_specialist",
        system_prompt=build_system_prompt(
            role_description="You are a mathematics specialist. Focus on numerical calculations, mathematical operations, and providing precise numerical results. Always show your work and explain calculations clearly.",
            tool_usage_mode=ToolUsageMode.MANDATORY,
            communication_style=CommunicationStyle.PROFESSIONAL,
        ),
        tool_bundles=["math"],
        tools=["add"],
        response_format="roles.MathResult",
        metadata=Metadata(tags=["math", "calculations", "precision"], cost_hint=0.3, latency_slo_ms=400),
    ),
    
    RoleConfig(
        name="research_assistant", 
        system_prompt=build_system_prompt(
            role_description="You are a research assistant focused on information retrieval and analysis. You help users find information, provide historical data, and conduct searches. Always cite your sources and provide comprehensive, well-organized responses.",
            tool_usage_mode=ToolUsageMode.PREFERRED,
            communication_style=CommunicationStyle.PROFESSIONAL,
        ),
        tool_bundles=["retrieval", "data"],
        metadata=Metadata(tags=["research", "data", "analysis"], cost_hint=1.2, latency_slo_ms=1500),
    ),
    
    RoleConfig(
        name="social_companion",
        system_prompt=build_system_prompt(
            role_description="You are a warm, encouraging social companion. Your role is to provide emotional support, daily encouragement, and friendly conversation. Avoid using tools unless absolutely necessary, focusing instead on the conversation. Always maintain a positive, uplifting tone and personalize your interactions.",
            tool_usage_mode=ToolUsageMode.DISCOURAGED,
            communication_style=CommunicationStyle.FRIENDLY,
        ),
        tool_bundles=["social"],
        tools=["random_number"],
        metadata=Metadata(tags=["social", "emotional-support", "encouragement"], cost_hint=0.4, latency_slo_ms=600),
    ),
    
    RoleConfig(
        name="ops_monitor",
        system_prompt=build_system_prompt(
            role_description="You are a system operations monitor. Focus on system health, monitoring, and operational tasks. Be concise, technical, and alert to any issues. You must use tools to verify system status before performing any operations.",
            tool_usage_mode=ToolUsageMode.MANDATORY,
            communication_style=CommunicationStyle.PROFESSIONAL,
        ),
        tool_bundles=["ops"],
        human_review=True,
        guardrails=Guardrails(max_tool_calls=10),
        metadata=Metadata(tags=["ops", "monitoring", "system-health"], cost_hint=0.8, latency_slo_ms=500),
    ),
    
    RoleConfig(
        name="full_access",
        system_prompt=build_system_prompt(
            role_description="You are a comprehensive assistant with access to all available tools. Adapt your communication style and approach based on the user's needs. You can handle mathematical calculations, research tasks, provide encouragement, check system status, and more. Prefer using the most appropriate tools for each task to ensure accuracy and efficiency.",
            tool_usage_mode=ToolUsageMode.PREFERRED,
            communication_style=CommunicationStyle.PROFESSIONAL,
        ),
        tool_bundles=["math", "social", "data", "retrieval", "utilities", "ops"],
        metadata=Metadata(tags=["comprehensive", "adaptive", "full-featured"], cost_hint=1.5, latency_slo_ms=1200),
    ),
    
    RoleConfig(
        name="quick_helper",
        system_prompt=build_system_prompt(
            role_description="You are a quick, efficient assistant for simple tasks. Provide brief, direct answers. Focus on speed and efficiency, using tools only when they are the most direct way to answer.",
            tool_usage_mode=ToolUsageMode.OPTIONAL,
            communication_style=CommunicationStyle.PROFESSIONAL,
        ),
        tools=["add", "multiply", "greet_person", "healthcheck"],
        model=ModelConfig(model_id="openai:gpt-4o-mini"),  
        metadata=Metadata(tags=["fast", "efficient", "simple"], cost_hint=0.2, latency_slo_ms=300),
    ),
]

# ---------- Factory entrypoints ----------
def _as_dict(catalog: List[RoleConfig]) -> Dict[str, Dict]:
    """Convert RoleConfig objects to plain dicts for downstream factories."""
    out: Dict[str, Dict] = {}
    for role in catalog:
        if role.metadata.deprecation_status == "sunset":
            continue
        if role.name in out:
            raise ValueError(f"Duplicate role name: {role.name}")
        out[role.name] = {
            "system_prompt": role.system_prompt,
            "tools": role.tools,
            "tool_bundles": role.tool_bundles,
            "model_id": role.model.model_id,
            "model_factory_path": role.model.model_factory_path,
            "response_format": role.response_format,
            "human_review": role.human_review,
            "guardrails": role.guardrails.model_dump(),
            "observability": role.observability.model_dump(),
            "metadata": role.metadata.model_dump(),
        }
    return out

def get_roles() -> Dict[str, Dict]:
    """Public entrypoint: the factory will call this to load role definitions."""
    return _as_dict(CATALOG)


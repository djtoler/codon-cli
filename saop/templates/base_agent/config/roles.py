from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

# Import your existing classes - create simple versions if they don't exist
try:
    from config.vars import build_system_prompt, ToolUsageMode, CommunicationStyle
except ImportError:
    # Simple fallbacks if config.prompts doesn't exist
    def build_system_prompt(role_description: str, **kwargs) -> str:
        return role_description
    
    class ToolUsageMode:
        OPTIONAL = "optional"
        MANDATORY = "mandatory" 
        PREFERRED = "preferred"
        DISCOURAGED = "discouraged"
    
    class CommunicationStyle:
        FRIENDLY = "friendly"
        PROFESSIONAL = "professional"

# Simple ModelConfig for role-specific model settings
class ModelConfig(BaseModel):
    """Configuration for how a role should use a model"""
    model_id: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None

class Metadata(BaseModel):
    """Metadata for role configuration"""
    tags: List[str] = Field(default_factory=list)
    cost_hint: float = 1.0
    latency_slo_ms: int = 1000
    best_for: List[str] = Field(default_factory=list)
    
    # Add these missing attributes
    version: str = "1.0.0"
    deprecation_status: Optional[str] = None
    owner: str = "SAOP Platform"
    docs_url: Optional[str] = None
    
    # Backward compatibility methods for existing LangGraph code
    def get(self, key: str, default=None):
        """Dict-like access for backward compatibility"""
        return getattr(self, key, default)
    
    def __getitem__(self, key: str):
        """Dict-like access with [] syntax"""
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(f"'{key}' not found in Metadata")
    
    def __contains__(self, key: str):
        """Dict-like 'in' operator"""
        return hasattr(self, key)
    
    def keys(self):
        """Dict-like keys() method"""
        return self.model_fields.keys()
    
    def items(self):
        """Dict-like items() method"""
        return [(k, getattr(self, k)) for k in self.model_fields.keys()]
    
    def values(self):
        """Dict-like values() method"""
        return [getattr(self, k) for k in self.model_fields.keys()]
    
    def to_dict(self) -> dict:
        """Convert to plain dictionary"""
        return self.model_dump()
    
    def __iter__(self):
        """Make iterable like a dict"""
        return iter(self.model_fields.keys())

class Observability(BaseModel):
    """Observability configuration"""
    enable_logging: bool = True
    enable_metrics: bool = True
    tracing_enabled: bool = True
    trace_tags: List[str] = Field(default_factory=list)

class Guardrails(BaseModel):
    """Guardrails configuration"""
    max_tool_calls: int = 5
    timeout_seconds: int = 30

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
    
    # Backward compatibility methods for existing LangGraph code
    def get(self, key: str, default=None):
        """Dict-like access for backward compatibility"""
        return getattr(self, key, default)
    
    def __getitem__(self, key: str):
        """Dict-like access with [] syntax"""
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(f"'{key}' not found in RoleConfig")
    
    def __contains__(self, key: str):
        """Dict-like 'in' operator"""
        return hasattr(self, key)
    
    def keys(self):
        """Dict-like keys() method"""
        return self.model_fields.keys()
    
    def items(self):
        """Dict-like items() method"""
        return [(k, getattr(self, k)) for k in self.model_fields.keys()]
    
    def values(self):
        """Dict-like values() method"""
        return [getattr(self, k) for k in self.model_fields.keys()]
    
    def to_dict(self) -> dict:
        """Convert to plain dictionary"""
        return self.model_dump()
    
    def __iter__(self):
        """Make iterable like a dict"""
        return iter(self.model_fields.keys())

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
        metadata=Metadata(
            tags=["general", "friendly", "utilities"], 
            cost_hint=0.6, 
            latency_slo_ms=800,
            best_for=["general questions", "basic help", "weather info"]
        ),
    ),
    
    RoleConfig(
        name="math_specialist",
        system_prompt=build_system_prompt(
            role_description="You are a mathematics specialist. Focus on numerical calculations, mathematical operations, and providing precise numerical results. Use multiplication for factorial calculations, not repeated addition. Always show your work and explain calculations clearly.",
            tool_usage_mode=ToolUsageMode.PREFERRED,
            communication_style=CommunicationStyle.PROFESSIONAL,
        ),
        tool_bundles=["math"],
        tools=["add", "multiply"],  # Add multiply
        response_format="roles.MathResult",
        metadata=Metadata(
            tags=["math", "calculations", "precision"], 
            cost_hint=0.3, 
            latency_slo_ms=400,
            best_for=["calculations", "math problems", "numerical analysis"]
        ),
    ),
    
    RoleConfig(
        name="research_assistant", 
        system_prompt=build_system_prompt(
            role_description="You are a research assistant focused on information retrieval and analysis. You help users find information, provide historical data, and conduct searches. Always cite your sources and provide comprehensive, well-organized responses.",
            tool_usage_mode=ToolUsageMode.PREFERRED,
            communication_style=CommunicationStyle.PROFESSIONAL,
        ),
        tool_bundles=["retrieval", "data"],
        metadata=Metadata(
            tags=["research", "data", "analysis"], 
            cost_hint=1.2, 
            latency_slo_ms=1500,
            best_for=["research tasks", "information retrieval", "data analysis"]
        ),
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
        metadata=Metadata(
            tags=["social", "emotional-support", "encouragement"], 
            cost_hint=0.4, 
            latency_slo_ms=600,
            best_for=["emotional support", "encouragement", "casual conversation"]
        ),
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
        metadata=Metadata(
            tags=["ops", "monitoring", "system-health"], 
            cost_hint=0.8, 
            latency_slo_ms=500,
            best_for=["system monitoring", "operational tasks", "health checks"]
        ),
    ),
    
    RoleConfig(
        name="full_access",
        system_prompt=build_system_prompt(
            role_description="You are a comprehensive assistant with access to all available tools. Adapt your communication style and approach based on the user's needs. You can handle mathematical calculations, research tasks, provide encouragement, check system status, and more. Prefer using the most appropriate tools for each task to ensure accuracy and efficiency.",
            tool_usage_mode=ToolUsageMode.PREFERRED,
            communication_style=CommunicationStyle.PROFESSIONAL,
        ),
        tool_bundles=["math", "social", "data", "retrieval", "utilities", "ops"],
        metadata=Metadata(
            tags=["comprehensive", "adaptive", "full-featured"], 
            cost_hint=1.5, 
            latency_slo_ms=1200,
            best_for=["complex tasks", "multi-domain problems", "comprehensive assistance"]
        ),
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
        metadata=Metadata(
            tags=["fast", "efficient", "simple"], 
            cost_hint=0.2, 
            latency_slo_ms=300,
            best_for=["quick answers", "simple tasks", "fast responses"]
        ),
    ),
]

# Helper functions
def get_roles() -> Dict[str, RoleConfig]:
    """Convert catalog to dictionary format"""
    return {role.name: role for role in CATALOG}

def get_role_by_name(name: str) -> Optional[RoleConfig]:
    """Get a specific role by name"""
    for role in CATALOG:
        if role.name == name:
            return role
    return None

def get_roles_by_tag(tag: str) -> List[RoleConfig]:
    """Get all roles that have a specific tag"""
    return [role for role in CATALOG if tag in role.metadata.tags]

def get_low_cost_roles(max_cost_hint: float = 0.5) -> List[RoleConfig]:
    """Get roles with cost hint below threshold"""
    return [role for role in CATALOG if role.metadata.cost_hint <= max_cost_hint]
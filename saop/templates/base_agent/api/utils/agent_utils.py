# api/utils/agent_utils.py
"""
Clean class-based utilities for agent operations
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AgentDomain(Enum):
    """Standardized agent domains"""
    MATHEMATICS = "Mathematics"
    RESEARCH = "Research"
    SOCIAL = "Social"
    OPERATIONS = "Operations"
    GENERAL = "General"
    COMPREHENSIVE = "Comprehensive"
    QUICK_TASKS = "Quick Tasks"


class AgentStatus(Enum):
    """Agent status types"""
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    ERROR = "error"


@dataclass
class AgentInfo:
    """Structured agent information"""
    agent_id: str
    name: str
    description: str
    status: AgentStatus
    domain: AgentDomain
    version: str
    capability_count: int
    active_tasks: int
    
    # Optional metadata
    tools: Optional[List[str]] = None
    tool_bundles: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    cost_hint: Optional[float] = None
    latency_slo_ms: Optional[int] = None
    human_review: bool = False
    system_prompt: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for template rendering"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "domain": self.domain.value,
            "version": self.version,
            "capability_count": self.capability_count,
            "active_tasks": self.active_tasks,
            "tools": self.tools or [],
            "tool_bundles": self.tool_bundles or [],
            "tags": self.tags or [],
            "cost_hint": self.cost_hint,
            "latency_slo_ms": self.latency_slo_ms,
            "human_review": self.human_review,
            "system_prompt": self.system_prompt
        }


class AgentRoleLoader:
    """Handles loading agent role configurations"""
    
    @staticmethod
    def load_roles() -> Dict[str, Any]:
        """Load roles data with fallback"""
        try:
            from config.roles import get_roles
            roles = get_roles()
            logger.info(f"Loaded {len(roles)} agent roles from config")
            return roles
        except ImportError as e:
            logger.warning(f"Could not import roles config: {e}, using fallback")
            return AgentRoleLoader._get_fallback_roles()
    
    @staticmethod
    def _get_fallback_roles() -> Dict[str, Any]:
        """Provide fallback roles when config is unavailable"""
        return {
            "general_support": {
                "system_prompt": "You are a helpful general-purpose assistant.",
                "tools": [],
                "tool_bundles": ["utilities"],
                "metadata": {
                    "tags": ["general"], 
                    "version": "1.0.0", 
                    "cost_hint": 0.6
                }
            }
        }


class AgentDescriptionGenerator:
    """Generates clean descriptions from system prompts"""
    
    MAX_DESCRIPTION_LENGTH = 120
    
    @classmethod
    def generate_description(cls, role_name: str, system_prompt: str) -> str:
        """Generate agent description from system prompt"""
        if not system_prompt:
            return cls._fallback_description(role_name)
        
        # Extract description from "You are a..." pattern
        if "You are a" in system_prompt:
            try:
                description_part = system_prompt.split("You are a")[1].split(".")[0]
                description = f"A {description_part.strip()}."
            except (IndexError, AttributeError):
                return cls._fallback_description(role_name)
        else:
            return cls._fallback_description(role_name)
        
        return cls._truncate_description(description)
    
    @classmethod
    def _fallback_description(cls, role_name: str) -> str:
        """Generate fallback description from role name"""
        clean_name = role_name.replace('_', ' ')
        return f"Specialized agent for {clean_name} tasks."
    
    @classmethod
    def _truncate_description(cls, description: str) -> str:
        """Truncate description to maximum length"""
        if len(description) > cls.MAX_DESCRIPTION_LENGTH:
            return description[:cls.MAX_DESCRIPTION_LENGTH - 3] + "..."
        return description


class AgentDomainMapper:
    """Maps agent tags to domains"""
    
    TAG_TO_DOMAIN = {
        "math": AgentDomain.MATHEMATICS,
        "research": AgentDomain.RESEARCH,
        "social": AgentDomain.SOCIAL,
        "ops": AgentDomain.OPERATIONS,
        "general": AgentDomain.GENERAL,
        "comprehensive": AgentDomain.COMPREHENSIVE,
        "fast": AgentDomain.QUICK_TASKS
    }
    
    @classmethod
    def map_tags_to_domain(cls, tags: List[str]) -> AgentDomain:
        """Map agent tags to appropriate domain"""
        for tag in tags:
            if tag in cls.TAG_TO_DOMAIN:
                return cls.TAG_TO_DOMAIN[tag]
        return AgentDomain.GENERAL


class AgentTaskCounter:
    """Handles counting active tasks for agents"""
    
    ACTIVE_STATUSES = ["submitted", "executing"]
    
    @classmethod
    def count_active_tasks(cls, agent_role: str, active_tasks: Dict[str, Any]) -> int:
        """Count active tasks for a specific agent role"""
        return sum(
            1 for task_data in active_tasks.values()
            if task_data.get("agent_role") == agent_role 
            and task_data.get("status") in cls.ACTIVE_STATUSES
        )


class AgentManager:
    """Main class for managing agent operations"""
    
    def __init__(self):
        self.role_loader = AgentRoleLoader()
        self.description_generator = AgentDescriptionGenerator()
        self.domain_mapper = AgentDomainMapper()
        self.task_counter = AgentTaskCounter()
    
    def get_all_agents(self, active_tasks: Optional[Dict[str, Any]] = None) -> List[AgentInfo]:
        """Get all agents as structured AgentInfo objects"""
        if active_tasks is None:
            # Import here to avoid circular imports
            from saop.templates.base_agent.api._streaming_routes import active_tasks as default_tasks
            active_tasks = default_tasks
        
        roles_data = self.role_loader.load_roles()
        agents = []
        
        for role_name, role_config in roles_data.items():
            agent_info = self._create_agent_info(role_name, role_config, active_tasks)
            agents.append(agent_info)
        
        return sorted(agents, key=lambda x: x.name)
    
    def get_agent_by_id(self, agent_id: str, active_tasks: Optional[Dict[str, Any]] = None) -> Optional[AgentInfo]:
        """Get specific agent by ID"""
        if active_tasks is None:
            from saop.templates.base_agent.api._streaming_routes import active_tasks as default_tasks
            active_tasks = default_tasks
        
        roles_data = self.role_loader.load_roles()
        
        if agent_id not in roles_data:
            return None
        
        return self._create_agent_info(agent_id, roles_data[agent_id], active_tasks)
    
    def _create_agent_info(self, role_name: str, role_config: Dict[str, Any], active_tasks: Dict[str, Any]) -> AgentInfo:
        """Create AgentInfo from role configuration"""
        metadata = role_config.get("metadata", {})
        tags = metadata.get("tags", [])
        
        # Generate all the derived information
        active_task_count = self.task_counter.count_active_tasks(role_name, active_tasks)
        domain = self.domain_mapper.map_tags_to_domain(tags)
        description = self.description_generator.generate_description(
            role_name, 
            role_config.get("system_prompt", "")
        )
        
        # Calculate capabilities
        tools = role_config.get("tools", [])
        tool_bundles = role_config.get("tool_bundles", [])
        capability_count = len(tools) + len(tool_bundles)
        
        return AgentInfo(
            agent_id=role_name,
            name=role_name.replace("_", " ").title(),
            description=description,
            status=AgentStatus.ONLINE,  # Could be enhanced with real status checking
            domain=domain,
            version=metadata.get("version", "1.0.0"),
            capability_count=capability_count,
            active_tasks=active_task_count,
            tools=tools,
            tool_bundles=tool_bundles,
            tags=tags,
            cost_hint=metadata.get("cost_hint"),
            latency_slo_ms=metadata.get("latency_slo_ms"),
            human_review=role_config.get("human_review", False),
            system_prompt=role_config.get("system_prompt")
        )
    
    def get_agents_for_templates(self, active_tasks: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get agents formatted for template rendering (backward compatibility)"""
        agents = self.get_all_agents(active_tasks)
        return [agent.to_dict() for agent in agents]


# # Convenience functions for backward compatibility
# def load_agent_roles() -> Dict[str, Any]:
#     """Load roles data with fallback (backward compatibility)"""
#     return AgentRoleLoader.load_roles()


# def transform_roles_to_agents(roles_data: Dict[str, Any]) -> List[Dict[str, Any]]:
#     """Transform roles configuration into agent list for templates (backward compatibility)"""
#     # For backward compatibility, we'll use the old logic but this could be refactored
#     # to use AgentManager if you want to break compatibility
#     manager = AgentManager()
#     return manager.get_agents_for_templates()


# Singleton instance for easy use
agent_manager = AgentManager()

# ===================================================================

# Updated web_routes.py usage example:
"""
# In your web routes, you can now use either:

# Option 1: Backward compatible (no changes needed)
from api.utils.agent_utils import load_agent_roles, transform_roles_to_agents
roles_data = load_agent_roles()
agents = transform_roles_to_agents(roles_data)

# Option 2: New clean approach
from api.utils.agent_utils import agent_manager
agents = agent_manager.get_agents_for_templates()

# Option 3: Full structured approach
from api.utils.agent_utils import agent_manager
agent_infos = agent_manager.get_all_agents()
# Now you have structured AgentInfo objects with proper typing

# Get specific agent
agent_info = agent_manager.get_agent_by_id("legal_agent_001")
if agent_info:
    agent_dict = agent_info.to_dict()  # For template rendering
"""
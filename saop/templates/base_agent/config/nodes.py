"""
Node system for managing operational AI agents with cost tracking, performance monitoring, and budget management.
All node-related classes and functionality in one place.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any, Set
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from enum import Enum
import uuid

# Import roles
from .roles import CATALOG, RoleConfig, get_role_by_name, Metadata, ModelConfig

try:
    from langchain_core.runnables import Runnable
except ImportError:
    # Fallback if langchain not available
    from typing import Any
    Runnable = Any


# ---------- Enums ----------
class NodeCategory(Enum):
    ROUTER = "router"          
    EXPERT = "expert"           
    TOOL_EXECUTOR = "tool_executor"  
    VALIDATOR = "validator"     
    FALLBACK = "fallback"       
    GENERAL = "general"


class NodeType(Enum):
    """Determines if a node is deterministic or not."""
    DETERMINISTIC = "deterministic"
    NON_DETERMINISTIC = "non_deterministic"
    UNKNOWN = "unknown"


# ---------- Tool Model (Simple version) ----------
class ToolModel(BaseModel):
    """Simple tool model for node tool management"""
    name: str
    is_enabled: bool = True
    cost_per_call_usd: float = 0.0
    total_cost_usd: float = 0.0
    description: str = ""


# ---------- 1. Node Info ----------
class NodeInfo(BaseModel):
    """Core node identity and basic configuration"""
    model_config = ConfigDict(validate_assignment=True)
    
    # Identity
    node_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    node_category: NodeCategory
    description: str
    role_name: str  
    node_type: NodeType
    is_enabled: bool = True


# ---------- 2. Cost Tracking ----------
class NodeCostTracker(BaseModel):
    """Handles all cost-related tracking and budgeting"""
    model_config = ConfigDict(validate_assignment=True)
    
    # Cost tracking
    cost_per_execution_usd: float = 0.0
    monthly_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    execution_count: int = 0
    
    # Budget management
    budget_priority: int = 5  # 1=highest, 10=lowest
    monthly_budget_limit_usd: Optional[float] = None
    
    def log_execution_cost(self, additional_cost_usd: float = None):
        """Log cost for a single execution"""
        cost = additional_cost_usd or self.cost_per_execution_usd
        
        self.execution_count += 1
        self.total_cost_usd += cost
        self.monthly_cost_usd += cost
    
    def reset_monthly_costs(self):
        """Reset monthly costs (call at month start)"""
        self.monthly_cost_usd = 0.0
    
    def is_over_budget(self) -> bool:
        """Check if node is over monthly budget"""
        if self.monthly_budget_limit_usd is None:
            return False
        return self.monthly_cost_usd >= self.monthly_budget_limit_usd
    
    def get_budget_utilization(self) -> float:
        """Get budget utilization ratio (0.0 to 1.0+)"""
        if self.monthly_budget_limit_usd is None or self.monthly_budget_limit_usd == 0:
            return 0.0
        return self.monthly_cost_usd / self.monthly_budget_limit_usd
    
    def get_avg_cost_per_execution(self) -> float:
        """Get average cost per execution"""
        if self.execution_count == 0:
            return 0.0
        return self.total_cost_usd / self.execution_count
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary for this tracker"""
        return {
            "cost_per_execution_usd": self.cost_per_execution_usd,
            "monthly_cost_usd": self.monthly_cost_usd,
            "total_cost_usd": self.total_cost_usd,
            "execution_count": self.execution_count,
            "budget_priority": self.budget_priority,
            "monthly_budget_limit_usd": self.monthly_budget_limit_usd,
            "budget_utilization": self.get_budget_utilization(),
            "avg_cost_per_execution": self.get_avg_cost_per_execution(),
            "is_over_budget": self.is_over_budget()
        }


# ---------- 3. Performance Monitoring ----------
class NodePerformanceMonitor(BaseModel):
    """Handles performance tracking, SLOs, and success rates"""
    model_config = ConfigDict(validate_assignment=True)
    
    # Performance metrics
    avg_execution_time_ms: float = 0.0
    p95_execution_time_ms: float = 0.0
    execution_slo_ms: int = 10000  # 10 second SLO per node execution
    
    # Success tracking
    success_rate: float = 1.0
    total_successes: int = 0
    total_failures: int = 0
    
    # Recent execution times for p95 calculation
    recent_execution_times: List[float] = Field(default_factory=list, exclude=True)
    
    def log_execution_performance(self, execution_time_ms: float, success: bool = True):
        """Log performance metrics for an execution"""
        # Update execution time stats
        if len(self.recent_execution_times) >= 100:  # Keep last 100 measurements
            self.recent_execution_times.pop(0)
        self.recent_execution_times.append(execution_time_ms)
        
        # Update averages
        total_executions = self.total_successes + self.total_failures + 1
        if total_executions == 1:
            self.avg_execution_time_ms = execution_time_ms
        else:
            alpha = 0.1  # Smoothing factor
            self.avg_execution_time_ms = (
                alpha * execution_time_ms + (1 - alpha) * self.avg_execution_time_ms
            )
        
        # Calculate p95
        if len(self.recent_execution_times) > 10:
            sorted_times = sorted(self.recent_execution_times)
            p95_index = int(0.95 * len(sorted_times))
            self.p95_execution_time_ms = sorted_times[p95_index]
        
        # Update success rate
        if success:
            self.total_successes += 1
        else:
            self.total_failures += 1
        
        total_attempts = self.total_successes + self.total_failures
        self.success_rate = self.total_successes / total_attempts if total_attempts > 0 else 1.0
    
    def is_slo_breaching(self) -> bool:
        """Check if node is breaching execution SLO"""
        return self.avg_execution_time_ms > self.execution_slo_ms
    
    def get_performance_health(self) -> str:
        """Get overall performance health status"""
        if self.success_rate < 0.95:
            return "critical"
        elif self.p95_execution_time_ms > self.execution_slo_ms:
            return "warning"
        elif self.is_slo_breaching():
            return "degraded"
        else:
            return "healthy"
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for this monitor"""
        return {
            "avg_execution_time_ms": self.avg_execution_time_ms,
            "p95_execution_time_ms": self.p95_execution_time_ms,
            "execution_slo_ms": self.execution_slo_ms,
            "success_rate": self.success_rate,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "is_slo_breaching": self.is_slo_breaching(),
            "performance_health": self.get_performance_health()
        }


# ---------- 4. Tool Management ----------
class NodeToolManager(BaseModel):
    """Manages tool assignment and tool-related operations"""
    model_config = ConfigDict(validate_assignment=True)
    
    # Tool assignment
    assigned_tools: Dict[str, ToolModel] = Field(default_factory=dict)
    
    # Tool configuration
    max_tools_per_execution: int = 10
    tool_timeout_seconds: int = 30
    
    def add_tool(self, tool: ToolModel):
        """Add a tool to this node"""
        self.assigned_tools[tool.name] = tool
    
    def remove_tool(self, tool_name: str):
        """Remove a tool from this node"""
        if tool_name in self.assigned_tools:
            del self.assigned_tools[tool_name]
    
    def get_enabled_tools(self) -> Dict[str, ToolModel]:
        """Get only enabled tools"""
        return {
            name: tool for name, tool in self.assigned_tools.items()
            if tool.is_enabled
        }
    
    def get_tools_by_cost_threshold(self, max_cost_usd: float) -> Dict[str, ToolModel]:
        """Get tools under a cost threshold"""
        return {
            name: tool for name, tool in self.assigned_tools.items()
            if tool.cost_per_call_usd <= max_cost_usd and tool.is_enabled
        }
    
    def get_total_tool_cost(self) -> float:
        """Get total cost from all assigned tools"""
        return sum(tool.total_cost_usd for tool in self.assigned_tools.values())
    
    def disable_expensive_tools(self, cost_threshold_usd: float):
        """Disable tools above cost threshold"""
        for tool in self.assigned_tools.values():
            if tool.cost_per_call_usd > cost_threshold_usd:
                tool.is_enabled = False
    
    def get_tool_summary(self) -> Dict[str, Any]:
        """Get tool summary for this manager"""
        enabled_tools = self.get_enabled_tools()
        return {
            "total_tools": len(self.assigned_tools),
            "enabled_tools": len(enabled_tools),
            "disabled_tools": len(self.assigned_tools) - len(enabled_tools),
            "max_tools_per_execution": self.max_tools_per_execution,
            "tool_timeout_seconds": self.tool_timeout_seconds,
            "total_tool_cost": self.get_total_tool_cost(),
            "tool_names": list(self.assigned_tools.keys())
        }


# ---------- 5. Model Configuration ----------
class NodeModelConfig(BaseModel):
    """Handles model selection and switching logic"""
    model_config = ConfigDict(validate_assignment=True)
    
    # Model configuration
    default_model: str = "openai:gpt-4o-mini"
    current_model: str = "openai:gpt-4o-mini"  # Runtime model (policy engine sets this)
    fallback_models: List[str] = Field(default_factory=list)
    
    def switch_model(self, new_model: str, reason: str = "Manual switch"):
        """Switch to a different model"""
        self.current_model = new_model
    
    def revert_to_default(self):
        """Revert to default model"""
        if self.current_model != self.default_model:
            self.switch_model(self.default_model, "Reverted to default")
    
    def try_fallback_model(self) -> bool:
        """Try switching to the next fallback model"""
        if not self.fallback_models:
            return False
        
        # Find current model in fallback chain
        try:
            current_index = self.fallback_models.index(self.current_model)
            if current_index < len(self.fallback_models) - 1:
                next_model = self.fallback_models[current_index + 1]
                self.switch_model(next_model, "Automatic fallback")
                return True
        except ValueError:
            # Current model not in fallback chain, use first fallback
            self.switch_model(self.fallback_models[0], "Fallback to backup model")
            return True
        
        return False
    
    def get_model_summary(self) -> Dict[str, Any]:
        """Get model summary for this config"""
        return {
            "default_model": self.default_model,
            "current_model": self.current_model,
            "fallback_models": self.fallback_models,
            "has_fallbacks": len(self.fallback_models) > 0,
            "is_using_default": self.current_model == self.default_model
        }


# ---------- 6. Routing Information ----------
class NodeRoutingInfo(BaseModel):
    """Routing-specific information for router nodes"""
    model_config = ConfigDict(validate_assignment=True)
    
    # Routing configuration
    routing_keywords: List[str] = Field(default_factory=list)
    routing_confidence_threshold: float = 0.8
    
    # Routing statistics
    total_routing_requests: int = 0
    successful_routings: int = 0
    routing_accuracy: float = 1.0
    
    def add_routing_keyword(self, keyword: str):
        """Add a routing keyword"""
        if keyword not in self.routing_keywords:
            self.routing_keywords.append(keyword)
    
    def log_routing_decision(self, success: bool):
        """Log a routing decision"""
        self.total_routing_requests += 1
        if success:
            self.successful_routings += 1
        
        self.routing_accuracy = (
            self.successful_routings / self.total_routing_requests 
            if self.total_routing_requests > 0 else 1.0
        )
    
    def get_routing_summary(self) -> Dict[str, Any]:
        """Get routing summary for this info"""
        return {
            "routing_keywords": self.routing_keywords,
            "routing_confidence_threshold": self.routing_confidence_threshold,
            "total_routing_requests": self.total_routing_requests,
            "successful_routings": self.successful_routings,
            "routing_accuracy": self.routing_accuracy,
            "keyword_count": len(self.routing_keywords)
        }


# ---------- 7. Main NodeModel ----------
class NodeModel(BaseModel):
    """
    Main node model that composes all the specialized components.
    This maintains the same interface while providing clean separation of concerns.
    """
    model_config = ConfigDict(validate_assignment=True, arbitrary_types_allowed=True)
    
    # Core components
    core: NodeInfo
    cost_tracker: NodeCostTracker = Field(default_factory=NodeCostTracker)
    performance: NodePerformanceMonitor = Field(default_factory=NodePerformanceMonitor)
    tool_manager: NodeToolManager = Field(default_factory=NodeToolManager)
    model_config_data: NodeModelConfig = Field(default_factory=NodeModelConfig)
    routing_info: Optional[NodeRoutingInfo] = Field(default=None)  # Only for router nodes
    
    # LangChain integration (not serialized)
    chain: Optional[Runnable] = Field(default=None, exclude=True)
    
    @classmethod
    def create_expert_node(
        cls, 
        name: str, 
        role_name: str, 
        description: str,
        default_model: str = "openai:gpt-4o-mini",
        **kwargs
    ) -> 'NodeModel':
        """Factory method to create an expert node"""
        core = NodeInfo(
            name=name,
            node_category=NodeCategory.EXPERT,
            node_type=NodeType.UNKNOWN,
            description=description,
            role_name=role_name
        )
        
        model_config = NodeModelConfig(
            default_model=default_model,
            current_model=default_model
        )
        
        return cls(
            core=core,
            model_config_data=model_config,
            **kwargs
        )
    
    @classmethod
    def create_router_node(
        cls, 
        name: str = "router",
        routing_keywords: List[str] = None,
        **kwargs
    ) -> 'NodeModel':
        """Factory method to create a router node"""
        core = NodeInfo(
            name=name,
            node_category=NodeCategory.ROUTER,
            node_type=NodeType.UNKNOWN,
            description="Routes user requests to appropriate expert nodes",
            role_name="router"
        )
        
        routing_info = NodeRoutingInfo(
            routing_keywords=routing_keywords or []
        )
        
        return cls(
            core=core,
            routing_info=routing_info,
            **kwargs
        )
    
    # Convenience methods that delegate to appropriate components
    def add_tool(self, tool: ToolModel):
        """Add a tool to this node"""
        self.tool_manager.add_tool(tool)
    
    def log_execution(self, execution_time_ms: float, success: bool = True, model_used: str = None, cost_usd: float = None):
        """Log execution across all relevant components"""
        self.cost_tracker.log_execution_cost(cost_usd)
        self.performance.log_execution_performance(execution_time_ms, success)
        
        if model_used and model_used != self.model_config_data.current_model:
            self.model_config_data.switch_model(model_used, "Runtime model switch")
    
    def get_comprehensive_summary(self) -> Dict[str, Any]:
        """Get comprehensive summary from all components"""
        summary = {
            "core": {
                "node_id": self.core.node_id,
                "name": self.core.name,
                "node_category": self.core.node_category.value,
                "role_name": self.core.role_name,
                "node_type": self.core.node_type.value,
                "is_enabled": self.core.is_enabled
            },
            "cost": self.cost_tracker.get_cost_summary(),
            "performance": self.performance.get_performance_summary(),
            "tools": self.tool_manager.get_tool_summary(),
            "model": self.model_config_data.get_model_summary()
        }
        
        if self.routing_info:
            summary["routing"] = self.routing_info.get_routing_summary()
        
        return summary
    
    # Properties for backward compatibility
    @property
    def name(self) -> str:
        return self.core.name
    
    @property
    def node_category(self) -> NodeCategory:
        return self.core.node_category
    
    @property
    def node_type(self) -> NodeType:
        return self.core.node_type
    
    @property
    def is_enabled(self) -> bool:
        return self.core.is_enabled
    
    @property
    def assigned_tools(self) -> Dict[str, ToolModel]:
        return self.tool_manager.assigned_tools
    
    @property
    def current_model(self) -> str:
        return self.model_config_data.current_model


# ---------- 8. Node Creation Functions ----------

def extract_description_from_prompt(system_prompt: str) -> str:
    """Extract a brief description from the system prompt"""
    lines = system_prompt.split('\n')
    for line in lines:
        if 'You are' in line and len(line) < 200:
            return line.strip()
    return "Specialized assistant"

def role_config_to_node_model(role_config: RoleConfig) -> NodeModel:
    """Convert RoleConfig to NodeModel for operational management"""
    
    # Extract description from system prompt
    description = extract_description_from_prompt(role_config.system_prompt)
    
    # Determine if this should be a router
    if role_config.name == "router":
        return NodeModel.create_router_node(
            name=role_config.name,
            routing_keywords=role_config.metadata.tags
        )
    
    # Create expert node for all other roles
    node = NodeModel.create_expert_node(
        name=role_config.name,
        role_name=role_config.name,
        description=description,
        default_model=role_config.model.model_id or "openai:gpt-4o-mini"
    )
    
    # Configure cost tracking based on role metadata
    node.cost_tracker.cost_per_execution_usd = role_config.metadata.cost_hint * 0.001  # Convert hint to USD
    node.cost_tracker.budget_priority = min(10, max(1, int(role_config.metadata.cost_hint * 5)))  # 1-10 scale
    
    # Configure performance monitoring
    node.performance.execution_slo_ms = role_config.metadata.latency_slo_ms
    
    # Configure model settings
    if role_config.model.model_id:
        node.model_config_data.default_model = role_config.model.model_id
        node.model_config_data.current_model = role_config.model.model_id
    
    # Set budget limits based on cost hint
    if role_config.metadata.cost_hint < 0.5:
        node.cost_tracker.monthly_budget_limit_usd = 10.0  # Low cost roles
    elif role_config.metadata.cost_hint > 1.0:
        node.cost_tracker.monthly_budget_limit_usd = 100.0  # High cost roles
    else:
        node.cost_tracker.monthly_budget_limit_usd = 50.0  # Medium cost roles
    
    # Set fallback models based on cost priority
    if role_config.metadata.cost_hint > 1.0:
        # High cost roles get fallback chain
        node.model_config_data.fallback_models = [
            "openai:gpt-4o-mini",
            "anthropic:claude-3-haiku-20240307"
        ]
    
    # Configure guardrails
    if role_config.guardrails:
        node.tool_manager.max_tools_per_execution = role_config.guardrails.max_tool_calls
        node.tool_manager.tool_timeout_seconds = role_config.guardrails.timeout_seconds
    
    # Store original role config for chain building
    node._role_config = role_config
    
    return node

def create_router_node_with_system_state(available_nodes: List[NodeModel], budget_state: Dict[str, Any]) -> NodeModel:
    """Create a dynamic router node based on available nodes and system state"""
    
    # Build dynamic routing keywords from available nodes
    routing_keywords = []
    for node in available_nodes:
        if hasattr(node, '_role_config'):
            routing_keywords.extend(node._role_config.metadata.tags)
    
    # Remove duplicates while preserving order
    routing_keywords = list(dict.fromkeys(routing_keywords))
    
    # Create router node
    router_node = NodeModel.create_router_node(
        name="router",
        routing_keywords=routing_keywords
    )
    
    # Configure router cost tracking (very cheap)
    router_node.cost_tracker.cost_per_execution_usd = 0.0001  # Very cheap
    router_node.cost_tracker.budget_priority = 1  # Highest priority
    router_node.cost_tracker.monthly_budget_limit_usd = 5.0  # Small budget
    
    # Configure router performance (fast)
    router_node.performance.execution_slo_ms = 200  # Very fast SLO
    
    # Create dynamic role config for the router
    # ModelConfig is already imported at the top from roles
    router_role_config = RoleConfig(
        name="router",
        system_prompt=build_dynamic_router_prompt(available_nodes, budget_state),
        model=ModelConfig(model_id="openai:gpt-4o-mini"),  # Use cheap model for routing
        metadata=Metadata(
            tags=["routing", "orchestration"], 
            cost_hint=0.1,
            latency_slo_ms=200,
            best_for=["request routing", "node selection"]
        )
    )
    
    router_node._role_config = router_role_config
    return router_node

def build_dynamic_router_prompt(available_nodes: List[NodeModel], budget_state: Dict[str, Any]) -> str:
    """Build dynamic router prompt based on current system state"""
    
    # Extract budget info
    spend_ratio = budget_state.get('spend_ratio', 0.0)
    budget_level = "healthy" if spend_ratio < 0.7 else "constrained" if spend_ratio < 0.9 else "critical"
    
    # Build node descriptions
    node_descriptions = []
    valid_node_names = []
    
    for node in available_nodes:
        if node.core.name == "router":
            continue
            
        role_config = getattr(node, '_role_config', None)
        if not role_config:
            continue
            
        description = f'• "{node.core.name}": {node.core.description}'
        description += f'\n  Model: {node.model_config_data.current_model} | Cost: ${node.cost_tracker.cost_per_execution_usd:.4f}'
        description += f'\n  Tools: {", ".join(node.tool_manager.assigned_tools.keys())}'
        description += f'\n  Best for: {", ".join(role_config.metadata.best_for)}'
        description += f'\n  Performance: {node.performance.get_performance_health()}, Success: {node.performance.success_rate:.1%}'
        
        # Add budget status
        budget_util = node.cost_tracker.get_budget_utilization()
        if budget_util > 0.8:
            description += f'\n  ⚠️  Budget: {budget_util:.1%} used'
        
        node_descriptions.append(description)
        valid_node_names.append(node.core.name)
    
    # Build the complete prompt
    base_description = "You are an intelligent routing assistant that directs user requests to the most appropriate specialized node while considering budget constraints, performance, and system efficiency."
    
    dynamic_context = f"""

CURRENT SYSTEM STATUS:
- Budget Status: {budget_level} ({int(spend_ratio * 100)}% used)
- Monthly Budget: ${budget_state.get('monthly_budget', 0):.2f}
- Current Spend: ${budget_state.get('current_spend', 0):.4f}

AVAILABLE NODES:
{chr(10).join(node_descriptions)}

ROUTING GUIDELINES:
1. If budget is "critical" (>90%), prefer cost-effective nodes unless accuracy is paramount
2. If budget is "constrained" (>70%), avoid expensive operations unless justified
3. Match user intent to node specialization precisely
4. For ambiguous requests, default to general_support
5. For system/technical issues, prefer ops_monitor regardless of cost
6. For calculations/math, always use math_specialist for accuracy
7. Consider node health - avoid nodes with poor performance unless necessary
8. Consider tool requirements - route to nodes that have the needed tools

ROUTING DECISION:
Analyze the user request and respond with ONLY the node name from: {', '.join(valid_node_names)}"""

    return base_description + dynamic_context


# ---------- 9. Create Nodes from Roles ----------

# Initialize empty list - we'll populate it after model rebuild
NODES: List[NodeModel] = []

def _create_nodes_from_roles():
    """Create nodes from role configs - called after model is fully defined"""
    global NODES
    
    print("Converting role configs to node models...")
    NODES = []
    
    for role_config in CATALOG:
        try:
            node = role_config_to_node_model(role_config)
            NODES.append(node)
            print(f"✓ Created node: {node.core.name}")
        except Exception as e:
            print(f"✗ Failed to create node for role {role_config.name}: {e}")
    
    print(f"Successfully created {len(NODES)} nodes from {len(CATALOG)} role configs")

# Rebuild the model to ensure it's fully defined, then create nodes
NodeModel.model_rebuild()
_create_nodes_from_roles()


# ---------- 10. Helper Functions ----------

def get_nodes() -> List[NodeModel]:
    """Get all available nodes"""
    return NODES

def get_node_by_name(name: str) -> Optional[NodeModel]:
    """Get a specific node by name"""
    for node in NODES:
        if node.core.name == name:
            return node
    return None

def get_nodes_by_category(category: NodeCategory) -> List[NodeModel]:
    """Get all nodes in a specific category"""
    return [node for node in NODES if node.core.node_category == category]

def get_low_cost_nodes(max_cost_usd: float = 0.001) -> List[NodeModel]:
    """Get nodes with cost below threshold"""
    return [node for node in NODES if node.cost_tracker.cost_per_execution_usd <= max_cost_usd]

def get_high_performance_nodes() -> List[NodeModel]:
    """Get nodes with good performance health"""
    return [node for node in NODES if node.performance.get_performance_health() in ["healthy", "degraded"]]

def get_budget_summary() -> Dict[str, Any]:
    """Get budget summary across all nodes"""
    total_cost = sum(node.cost_tracker.total_cost_usd for node in NODES)
    total_budget = sum(node.cost_tracker.monthly_budget_limit_usd or 0 for node in NODES)
    
    over_budget_nodes = [node for node in NODES if node.cost_tracker.is_over_budget()]
    
    return {
        "total_cost": total_cost,
        "total_budget": total_budget,
        "utilization": total_cost / max(total_budget, 1),
        "over_budget_nodes": len(over_budget_nodes),
        "node_count": len(NODES)
    }

def get_performance_summary() -> Dict[str, Any]:
    """Get performance summary across all nodes"""
    healthy_nodes = [node for node in NODES if node.performance.get_performance_health() == "healthy"]
    critical_nodes = [node for node in NODES if node.performance.get_performance_health() == "critical"]
    
    avg_success_rate = sum(node.performance.success_rate for node in NODES) / len(NODES) if NODES else 1.0
    avg_latency = sum(node.performance.avg_execution_time_ms for node in NODES) / len(NODES) if NODES else 0.0
    
    return {
        "healthy_nodes": len(healthy_nodes),
        "critical_nodes": len(critical_nodes),
        "avg_success_rate": avg_success_rate,
        "avg_latency_ms": avg_latency,
        "total_nodes": len(NODES)
    }

def reset_all_monthly_budgets():
    """Reset monthly budget tracking for all nodes"""
    for node in NODES:
        node.cost_tracker.reset_monthly_costs()
    print(f"Reset monthly budgets for {len(NODES)} nodes")

def validate_nodes() -> List[str]:
    """Validate all nodes and return any issues"""
    issues = []
    
    for node in NODES:
        # Check for missing role config
        if not hasattr(node, '_role_config'):
            issues.append(f"Node {node.core.name} missing role config")
        
        # Check for reasonable budget limits
        if node.cost_tracker.monthly_budget_limit_usd and node.cost_tracker.monthly_budget_limit_usd < 1.0:
            issues.append(f"Node {node.core.name} has very low budget limit: ${node.cost_tracker.monthly_budget_limit_usd}")
        
        # Check for reasonable SLOs
        if node.performance.execution_slo_ms < 100:
            issues.append(f"Node {node.core.name} has very tight SLO: {node.performance.execution_slo_ms}ms")
    
    return issues

# Print initialization summary
if __name__ == "__main__":
    print("\n" + "="*60)
    print("NODE SYSTEM INITIALIZATION SUMMARY")
    print("="*60)
    print(f"Created {len(NODES)} nodes from {len(CATALOG)} role configs")
    
    budget_summary = get_budget_summary()
    print(f"Total Budget: ${budget_summary['total_budget']:.2f}")
    print(f"Budget Utilization: {budget_summary['utilization']:.1%}")
    
    perf_summary = get_performance_summary()
    print(f"Healthy Nodes: {perf_summary['healthy_nodes']}/{perf_summary['total_nodes']}")
    
    # Check for issues
    issues = validate_nodes()
    if issues:
        print(f"⚠️  Issues found: {len(issues)}")
        for issue in issues[:3]:  # Show first 3
            print(f"   • {issue}")
    else:
        print("✅ All nodes validated successfully")
    
    print("="*60)
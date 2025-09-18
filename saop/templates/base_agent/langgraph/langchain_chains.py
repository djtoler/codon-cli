import time
import logging
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from langchain_core.runnables import Runnable, RunnableLambda
from langchain.chat_models import init_chat_model
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers.string import StrOutputParser

# Import configurations
from config.llms import ModelRegistry, ModelBudgetPolicy
from config.agent_config import load_env_config

# Import node system - everything we need is in nodes.py now
from config.nodes import (
    NodeModel, NodeCategory, NODES,
    get_nodes, get_node_by_name, create_router_node_with_system_state,
    get_budget_summary, get_performance_summary
)

# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("chains")

# Load configuration
env_config = load_env_config()

# Initialize model management
try:
    model_registry = ModelRegistry.load_from_openrouter_json("openrouter_pricing_converted.json")
    print(f"Loaded {len(model_registry.models)} models from ModelRegistry")
except Exception as e:
    print(f"Could not load ModelRegistry: {e}. Using fallback configuration.")
    model_registry = None

# Initialize budget policy
budget_policy = ModelBudgetPolicy(
    monthly_budget_usd=float(env_config.get("MONTHLY_BUDGET_USD", "1000.0"))
)


class NodeChainManager:
    """Manages LangChain chains built from NodeModel instances"""
    
    def __init__(self):
        self.nodes = {node.core.name: node for node in get_nodes()}
        self.chains: Dict[str, Runnable] = {}
        self.model_registry = model_registry
        self.budget_policy = budget_policy
        
        # System-wide usage tracking
        self.system_stats = {
            "total_requests": 0,
            "total_cost": 0.0,
            "start_time": time.time()
        }
        
        self._initialize_chains()
    
    def _initialize_chains(self):
        """Initialize chains from all nodes"""
        print("\n" + "="*60)
        print("INITIALIZING CHAINS FROM NODE MODELS")
        print("="*60)
        
        # Get current node performance and budget state
        budget_summary = get_budget_summary()
        perf_summary = get_performance_summary()
        
        print(f"System Budget Utilization: {budget_summary['utilization']:.1%}")
        print(f"Healthy Nodes: {perf_summary['healthy_nodes']}/{perf_summary['total_nodes']}")
        
        # Create chains for all expert nodes first
        expert_nodes = [node for node in self.nodes.values() if node.core.node_category != NodeCategory.ROUTER]
        
        for node in expert_nodes:
            try:
                chain = self._create_chain_from_node(node)
                self.chains[node.core.name] = chain
                print(f"✓ Created chain for node: {node.core.name} (Model: {node.model_config_data.current_model})")
            except Exception as e:
                print(f"✗ Failed to create chain for node {node.core.name}: {e}")
                self.chains[node.core.name] = self._create_fallback_chain(node)
        
        # Create dynamic router
        self._create_router_chain()
        
        print(f"Total chains created: {len(self.chains)}")
        print("="*60 + "\n")
    
    def _create_chain_from_node(self, node: NodeModel) -> Runnable:
        """Create a LangChain chain from a NodeModel"""
        
        # Apply budget-aware model selection
        selected_model = self._select_model_for_node(node)
        
        # Create LLM based on node configuration
        llm = self._create_llm_for_node(node, selected_model)
        
        # Get system prompt from stored role config
        role_config = getattr(node, '_role_config', None)
        if role_config:
            system_prompt = role_config.system_prompt
        else:
            system_prompt = f"You are {node.core.description}"
        
        # Create prompt template
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])
        
        # Build the chain
        chain = prompt_template | llm | StrOutputParser()
        
        # Wrap with node-aware features
        return self._wrap_chain_with_node_features(chain, node, selected_model)
    
    def _select_model_for_node(self, node: NodeModel) -> str:
        """Select model for node considering budget constraints and node requirements"""
        
        # Start with node's current model
        preferred_model = node.model_config_data.current_model
        
        # Check if node is over budget
        if node.cost_tracker.is_over_budget():
            log.warning(f"Node {node.core.name} is over budget, trying fallback model")
            if node.model_config_data.try_fallback_model():
                return node.model_config_data.current_model
        
        # Apply system-wide budget policy if we have model registry
        if self.model_registry and self.budget_policy:
            system_spend_ratio = self.budget_policy.get_spend_ratio()
            
            # For high-priority nodes, be more conservative with model switching
            if node.cost_tracker.budget_priority <= 3 and system_spend_ratio < 0.9:
                return preferred_model
            
            # Apply budget-aware selection
            selected_model, reason = self.budget_policy.select_model(preferred_model, self.model_registry)
            
            if selected_model != preferred_model:
                print(f"Budget optimization: {node.core.name}: {preferred_model} -> {selected_model} ({reason})")
                node.model_config_data.switch_model(selected_model, reason)
                return selected_model
        
        return preferred_model
    
    def _create_llm_for_node(self, node: NodeModel, model_id: str):
        """Create LLM instance based on node configuration"""
        
        # Get role config for LLM parameters
        role_config = getattr(node, '_role_config', None)
        
        llm_params = {
            "model": model_id,
            "openai_api_key": env_config.get("MODEL_API_KEY"),
            "timeout": 30
        }
        
        # Add role-specific parameters if available
        if role_config:
            llm_params["temperature"] = role_config.model.temperature or 0.7
            if role_config.model.max_tokens:
                llm_params["max_tokens"] = role_config.model.max_tokens
            if role_config.guardrails:
                llm_params["timeout"] = role_config.guardrails.timeout_seconds
        
        # Determine provider
        if self.model_registry:
            model_info = self.model_registry.get_model(model_id)
            if model_info:
                llm_params["model_provider"] = model_info.info.provider.value
        
        if "model_provider" not in llm_params:
            llm_params["model_provider"] = env_config.get("MODEL_PROVIDER", "openai")
        
        return init_chat_model(**llm_params)
    
    def _wrap_chain_with_node_features(self, chain: Runnable, node: NodeModel, model_id: str) -> Runnable:
        """Wrap chain with node-specific features like monitoring, budgeting, and guardrails"""
        
        def node_enhanced_wrapper(input_data):
            start_time = time.perf_counter()
            
            try:
                # Pre-execution checks
                if node.cost_tracker.is_over_budget():
                    raise Exception(f"Node {node.core.name} is over monthly budget limit")
                
                # Check if tools need to be filtered by cost
                available_tools = node.tool_manager.get_enabled_tools()
                if node.cost_tracker.budget_priority > 7:  # Low priority, filter expensive tools
                    max_tool_cost = 0.001  # Very cheap tools only
                    available_tools = node.tool_manager.get_tools_by_cost_threshold(max_tool_cost)
                
                # Apply guardrails
                role_config = getattr(node, '_role_config', None)
                if role_config and role_config.guardrails:
                    # Could implement additional guardrail checks here
                    pass
                
                # Execute chain
                result = chain.invoke(input_data)
                execution_time_ms = (time.perf_counter() - start_time) * 1000
                
                # Calculate cost
                cost_usd = self._calculate_execution_cost(input_data, result, model_id, node)
                
                # Log to node (this updates all node's internal tracking)
                node.log_execution(
                    execution_time_ms=execution_time_ms,
                    success=True,
                    model_used=model_id,
                    cost_usd=cost_usd
                )
                
                # Update system stats
                self._update_system_stats(cost_usd)
                
                # Check alerts
                self._check_node_alerts(node)
                
                # Maybe refresh chains if significant changes
                self._maybe_refresh_chains()
                
                return result
                
            except Exception as e:
                execution_time_ms = (time.perf_counter() - start_time) * 1000
                
                # Log failure to node
                node.log_execution(
                    execution_time_ms=execution_time_ms,
                    success=False,
                    model_used=model_id,
                    cost_usd=0.0
                )
                
                log.error(f"Chain execution failed for node {node.core.name}: {e}")
                
                # Try fallback model if this was a model-related error
                if "model" in str(e).lower() and node.model_config_data.try_fallback_model():
                    log.info(f"Trying fallback model for {node.core.name}: {node.model_config_data.current_model}")
                    # Don't re-execute here, just log the fallback for next time
                
                raise
        
        return RunnableLambda(node_enhanced_wrapper)
    
    def _calculate_execution_cost(self, input_data: Any, result: Any, model_id: str, node: NodeModel) -> float:
        """Calculate the cost of an execution"""
        
        if self.model_registry:
            model = self.model_registry.get_model(model_id)
            if model:
                # Estimate tokens
                prompt_tokens = len(str(input_data)) * 4
                completion_tokens = len(str(result)) * 4
                
                cost = model.calculate_request_cost(prompt_tokens, completion_tokens)
                model.log_usage(prompt_tokens, completion_tokens, 0)
                return cost
        
        # Fallback to node's cost per execution
        return node.cost_tracker.cost_per_execution_usd
    
    def _update_system_stats(self, cost_usd: float):
        """Update system-wide statistics"""
        self.system_stats["total_requests"] += 1
        self.system_stats["total_cost"] += cost_usd
        
        # Update budget policy
        if self.budget_policy:
            self.budget_policy.monthly_spend_usd = self.system_stats["total_cost"]
    
    def _check_node_alerts(self, node: NodeModel):
        """Check for node-specific alerts"""
        
        # Performance alerts
        if node.performance.is_slo_breaching():
            log.warning(f"SLO breach: {node.core.name} avg latency {node.performance.avg_execution_time_ms:.0f}ms > {node.performance.execution_slo_ms}ms")
        
        # Budget alerts
        budget_util = node.cost_tracker.get_budget_utilization()
        if budget_util > 0.9:
            log.critical(f"Budget alert: {node.core.name} at {budget_util:.1%} of monthly budget")
        elif budget_util > 0.7:
            log.warning(f"Budget warning: {node.core.name} at {budget_util:.1%} of monthly budget")
        
        # Success rate alerts
        if node.performance.success_rate < 0.95:
            log.warning(f"Success rate alert: {node.core.name} at {node.performance.success_rate:.1%} success rate")
        
        # Health status
        health = node.performance.get_performance_health()
        if health in ["critical", "warning"]:
            log.warning(f"Node health: {node.core.name} is {health}")
    
    def _create_router_chain(self):
        """Create the dynamic router chain"""
        try:
            # Get current budget state
            budget_state = self._get_budget_state()
            
            # Create router node with current system state
            available_nodes = list(self.nodes.values())
            router_node = create_router_node_with_system_state(available_nodes, budget_state)
            
            # Create router chain using the same process as other nodes
            router_chain = self._create_chain_from_node(router_node)
            
            # Add structured output for reliable routing
            class Route(BaseModel):
                next_node: str
            
            # Get router's LLM for structured output
            router_llm = self._create_llm_for_node(router_node, router_node.model_config_data.current_model)
            
            # Get system prompt from router node
            role_config = getattr(router_node, '_role_config', None)
            if role_config:
                router_prompt = ChatPromptTemplate.from_messages([
                    ("system", role_config.system_prompt),
                    ("human", "{input}"),
                ])
                
                structured_router = (
                    router_prompt
                    | router_llm.with_structured_output(Route)
                    | RunnableLambda(lambda x: x.next_node)
                )
                
                self.chains["router"] = structured_router
                self.nodes["router"] = router_node
                print("✓ Created dynamic router")
        
        except Exception as e:
            print(f"✗ Failed to create router: {e}")
            self.chains["router"] = self._create_fallback_router()
    
    def _get_budget_state(self) -> Dict[str, Any]:
        """Get current budget state for router creation"""
        
        if self.budget_policy:
            spend_ratio = self.budget_policy.get_spend_ratio()
        else:
            spend_ratio = 0.0
        
        return {
            "spend_ratio": spend_ratio,
            "monthly_budget": self.budget_policy.monthly_budget_usd if self.budget_policy else 1000.0,
            "current_spend": self.system_stats["total_cost"]
        }
    
    def _create_fallback_chain(self, node: NodeModel) -> Runnable:
        """Create a simple fallback chain for a node"""
        
        system_prompt = f"You are {node.core.description}. Help the user with their request."
        
        llm = init_chat_model(
            model=env_config.get("MODEL_NAME", "openai:gpt-4o-mini"),
            openai_api_key=env_config.get("MODEL_API_KEY"),
            model_provider=env_config.get("MODEL_PROVIDER", "openai")
        )
        
        return ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ]) | llm | StrOutputParser()
    
    def _create_fallback_router(self) -> Runnable:
        """Create a simple fallback router"""
        
        available_nodes = [name for name in self.nodes.keys() if name != "router"]
        
        router_prompt = f"""You are a routing assistant. Choose the best node for the user's request.
        
Available nodes: {', '.join(available_nodes)}

For math questions, choose: math_specialist
For system/technical issues, choose: ops_monitor  
For research tasks, choose: research_assistant
For emotional support, choose: social_companion
For everything else, choose: general_support

Respond with just the node name.

User request: {{input}}"""
        
        llm = init_chat_model(
            model=env_config.get("MODEL_NAME", "openai:gpt-4o-mini"),
            openai_api_key=env_config.get("MODEL_API_KEY"),
            model_provider=env_config.get("MODEL_PROVIDER", "openai")
        )
        
        return ChatPromptTemplate.from_template(router_prompt) | llm | StrOutputParser()
    
    def _maybe_refresh_chains(self):
        """Check if chains need refresh due to significant changes"""
        
        # Check if any nodes have switched models significantly
        model_switches = 0
        budget_breaches = 0
        
        for node in self.nodes.values():
            if hasattr(node, '_last_known_model'):
                if node._last_known_model != node.model_config_data.current_model:
                    model_switches += 1
            node._last_known_model = node.model_config_data.current_model
            
            if node.cost_tracker.is_over_budget():
                budget_breaches += 1
        
        # Refresh router if significant changes
        if model_switches > 2 or budget_breaches > 0:
            print(f"🔄 Refreshing router due to {model_switches} model switches, {budget_breaches} budget breaches")
            self._create_router_chain()
    
    def get_chain(self, node_name: str) -> Optional[Runnable]:
        """Get chain for a specific node"""
        return self.chains.get(node_name)
    
    def get_node(self, node_name: str) -> Optional[NodeModel]:
        """Get node model for a specific node"""
        return self.nodes.get(node_name)
    
    def get_system_dashboard(self) -> Dict[str, Any]:
        """Get comprehensive system dashboard"""
        
        runtime_hours = (time.time() - self.system_stats["start_time"]) / 3600
        
        # Node summaries with all the rich data from NodeModel
        node_summaries = []
        for node in self.nodes.values():
            summary = {
                "name": node.core.name,
                "category": node.core.node_category.value,
                "current_model": node.model_config_data.current_model,
                "executions": node.cost_tracker.execution_count,
                "total_cost": node.cost_tracker.total_cost_usd,
                "monthly_cost": node.cost_tracker.monthly_cost_usd,
                "avg_latency_ms": node.performance.avg_execution_time_ms,
                "p95_latency_ms": node.performance.p95_execution_time_ms,
                "success_rate": node.performance.success_rate,
                "budget_utilization": node.cost_tracker.get_budget_utilization(),
                "budget_priority": node.cost_tracker.budget_priority,
                "health": node.performance.get_performance_health(),
                "slo_ms": node.performance.execution_slo_ms,
                "tool_count": len(node.tool_manager.assigned_tools)
            }
            node_summaries.append(summary)
        
        # Sort by cost
        node_summaries.sort(key=lambda x: x["total_cost"], reverse=True)
        
        # Get system-wide summaries from nodes.py
        budget_summary = get_budget_summary()
        perf_summary = get_performance_summary()
        
        return {
            "system": {
                "total_requests": self.system_stats["total_requests"],
                "total_cost": self.system_stats["total_cost"],
                "runtime_hours": runtime_hours,
                "requests_per_hour": self.system_stats["total_requests"] / max(runtime_hours, 0.01)
            },
            "budget": {
                "monthly_budget": self.budget_policy.monthly_budget_usd if self.budget_policy else 0,
                "monthly_spend": self.system_stats["total_cost"],
                "spend_ratio": self.budget_policy.get_spend_ratio() if self.budget_policy else 0,
                "node_budget_summary": budget_summary
            },
            "performance": {
                "system_performance": perf_summary,
                "healthy_node_count": perf_summary["healthy_nodes"],
                "critical_node_count": perf_summary["critical_nodes"]
            },
            "nodes": node_summaries,
            "alerts": self._get_system_alerts()
        }
    
    def _get_system_alerts(self) -> List[Dict[str, Any]]:
        """Get system-wide alerts"""
        alerts = []
        
        for node in self.nodes.values():
            # Budget alerts
            budget_util = node.cost_tracker.get_budget_utilization()
            if budget_util > 0.9:
                alerts.append({
                    "type": "budget",
                    "severity": "critical",
                    "node": node.core.name,
                    "message": f"Node at {budget_util:.1%} of budget",
                    "value": budget_util
                })
            
            # Performance alerts
            if node.performance.success_rate < 0.95:
                alerts.append({
                    "type": "performance",
                    "severity": "warning",
                    "node": node.core.name,
                    "message": f"Success rate {node.performance.success_rate:.1%}",
                    "value": node.performance.success_rate
                })
            
            # SLO alerts
            if node.performance.is_slo_breaching():
                alerts.append({
                    "type": "slo",
                    "severity": "warning", 
                    "node": node.core.name,
                    "message": f"Avg latency {node.performance.avg_execution_time_ms:.0f}ms > {node.performance.execution_slo_ms}ms",
                    "value": node.performance.avg_execution_time_ms
                })
        
        return sorted(alerts, key=lambda x: {"critical": 3, "warning": 2, "info": 1}[x["severity"]], reverse=True)
    
    def reset_monthly_budgets(self):
        """Reset monthly budget tracking for all nodes"""
        for node in self.nodes.values():
            node.cost_tracker.reset_monthly_costs()
        
        self.system_stats["total_cost"] = 0.0
        if self.budget_policy:
            self.budget_policy.monthly_spend_usd = 0.0
        
        print("Monthly budgets reset for all nodes")


# Initialize the chain manager
chain_manager = NodeChainManager()

# Export chains for backward compatibility
chains: Dict[str, Runnable] = chain_manager.chains

# Export functions
def get_chain(node_name: str) -> Optional[Runnable]:
    """Get chain for a specific node"""
    return chain_manager.get_chain(node_name)

def get_node(node_name: str) -> Optional[NodeModel]:
    """Get node model for a specific node"""
    return chain_manager.get_node(node_name)

def get_system_dashboard() -> Dict[str, Any]:
    """Get comprehensive system dashboard"""
    return chain_manager.get_system_dashboard()

def refresh_router():
    """Force refresh the router"""
    chain_manager._create_router_chain()

def reset_monthly_budgets():
    """Reset monthly budget tracking"""
    chain_manager.reset_monthly_budgets()

# Export node functions for convenience
def get_all_nodes() -> List[NodeModel]:
    """Get all node models"""
    return list(chain_manager.nodes.values())

def get_nodes_by_health(health_status: str) -> List[NodeModel]:
    """Get nodes by health status"""
    return [node for node in chain_manager.nodes.values() 
            if node.performance.get_performance_health() == health_status]

def get_over_budget_nodes() -> List[NodeModel]:
    """Get nodes that are over their budget"""
    return [node for node in chain_manager.nodes.values() 
            if node.cost_tracker.is_over_budget()]

# Print initialization summary
if __name__ == "__main__":
    dashboard = get_system_dashboard()
    print("\n" + "="*60)
    print("CHAIN SYSTEM INITIALIZATION COMPLETE")
    print("="*60)
    print(f"Total Requests: {dashboard['system']['total_requests']}")
    print(f"Total Cost: ${dashboard['system']['total_cost']:.4f}")
    print(f"Monthly Budget: ${dashboard['budget']['monthly_budget']:.2f}")
    print(f"Available Nodes: {len(dashboard['nodes'])}")
    print(f"Healthy Nodes: {dashboard['performance']['healthy_node_count']}")
    
    if dashboard['alerts']:
        print(f"System Alerts: {len(dashboard['alerts'])}")
        for alert in dashboard['alerts'][:3]:  # Show first 3 alerts
            print(f"   • {alert['severity'].upper()}: {alert['node']} - {alert['message']}")
    
    print("="*60)
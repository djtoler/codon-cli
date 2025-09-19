
# _mcp/tools.py
"""
Centralized tool registry with LangChain wrappers, telemetry, and MCP registration.
Now using ToolModel for comprehensive tracking and management with clean class-based architecture.
"""
from __future__ import annotations
import asyncio
import time
from typing import Dict, List, Callable, Any, Optional, Set
from functools import wraps
from datetime import datetime
from langchain_core.tools import tool, BaseTool

from telemetry.mcp_trace_utils import track_tools, track_langchain_tools
from saop.templates.base_agent.config.tools import (
    ToolModel, ToolInfo, ToolCost, ToolType, ToolLatency
)


# ---------- Resiliency decorator with ToolModel integration ----------
def resilient(tool_model: ToolModel, retries: int = 1, timeout_sec: Optional[float] = None):
    """Retry a tool and enforce a soft timeout while tracking metrics."""
    def deco(fn: Callable[..., Any]):
        @wraps(fn)
        def inner(*args, **kwargs):
            start_time = time.perf_counter()
            last_err = None
            
            for attempt in range(retries + 1):
                try:
                    result = fn(*args, **kwargs)
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    
                    # Check timeout
                    if timeout_sec is not None and elapsed_ms/1000 > timeout_sec:
                        raise TimeoutError(f"Tool '{fn.__name__}' exceeded {timeout_sec}s")
                    
                    # Log successful usage with actual latency
                    tool_model.log_usage(num_calls=1, latency_ms=elapsed_ms)
                    return result
                    
                except Exception as e:
                    last_err = e
                    if attempt >= retries:
                        # Log failed attempt
                        elapsed_ms = (time.perf_counter() - start_time) * 1000
                        tool_model.log_usage(num_calls=1, latency_ms=elapsed_ms)
                        raise
            raise last_err
        return inner
    return deco


# ---------- Core tool implementations ----------
def get_weather_impl(city: str) -> str:
    """Return a short, friendly weather snippet for the given city."""
    return f"It's always sunny in {city}."

def add_impl(a: int, b: int) -> int:
    """Add two integers and return the sum."""
    return a + b

def healthcheck_impl() -> str:
    """Return 'OK' to verify that the tool runner is healthy."""
    return "OK"

# Add after the add_impl function
def multiply_impl(a: int, b: int) -> int:
    """Multiply two integers and return the product."""
    return a * b


# ---------- ToolModel Management Class ----------
class ToolModelManager:
    """Manages ToolModel creation, registration, and lifecycle."""
    
    def __init__(self):
        self._tool_models: Dict[str, ToolModel] = {}
        self._initialize_static_tools()
    
    def _initialize_static_tools(self):
        """Initialize ToolModels for static/built-in tools."""
        static_tools = [
            {
                'name': 'get_weather',
                'description': 'Return a short, friendly weather snippet for the given city',
                'tool_type': ToolType.NON_DETERMINISTIC,
                'cost_per_call': 0.01,
                'bundles': ['utilities']
            },
            {
                'name': 'add',
                'description': 'Add two integers and return the sum',
                'tool_type': ToolType.DETERMINISTIC,
                'cost_per_call': 0.0,
                'bundles': ['math']
            },
            {
                'name': 'multiply',  
                'description': 'Multiply two integers and return the product',
                'tool_type': ToolType.DETERMINISTIC,
                'cost_per_call': 0.0,
                'bundles': ['math']
            },
            {
                'name': 'healthcheck',
                'description': 'Return OK to verify that the tool runner is healthy',
                'tool_type': ToolType.DETERMINISTIC,
                'cost_per_call': 0.0,
                'bundles': ['utilities', 'ops']
            }
        ]
        
        for tool_config in static_tools:
            tool_model = ToolModel(
                info=ToolInfo(
                    name=tool_config['name'],
                    description=tool_config['description']
                ),
                tool_type=tool_config['tool_type'],
                cost=ToolCost(cost_per_call=tool_config['cost_per_call']),
            )
            
            
            # Add to bundles
            for bundle in tool_config['bundles']:
                tool_model.add_to_bundle(bundle)
            
            self._tool_models[tool_config['name']] = tool_model
    
    def create_dynamic_tool_model(self, tool_name: str, tool_description: str = "") -> ToolModel:
        """Create a ToolModel instance for dynamically discovered MCP tools."""
        # Enhanced cost and type heuristics based on tool name and description
        cost_per_call = 0.0
        tool_type = ToolType.NON_DETERMINISTIC  # Default for external API tools
        
        # Cost heuristics - GitHub API operations
        if any(keyword in tool_name.lower() for keyword in ['create', 'update', 'delete', 'push', 'fork']):
            cost_per_call = 0.10  # Write operations are expensive
        elif any(keyword in tool_name.lower() for keyword in ['search', 'list']):
            cost_per_call = 0.05  # Search operations moderate cost
        elif any(keyword in tool_name.lower() for keyword in ['get', 'show']):
            cost_per_call = 0.02  # Read operations cheaper
        elif 'star' in tool_name.lower():
            cost_per_call = 0.01  # Simple actions
        
        # Deterministic vs non-deterministic heuristics
        if any(keyword in tool_name.lower() for keyword in ['get', 'list', 'search', 'show']):
            tool_type = ToolType.DETERMINISTIC  # Read operations are typically deterministic
        
        # Bundle assignment based on tool name patterns
        bundles = []
        if any(keyword in tool_name.lower() for keyword in ['git', 'branch', 'commit', 'repository', 'repo']):
            bundles.append('git')
        elif any(keyword in tool_name.lower() for keyword in ['file', 'content']):
            bundles.append('files')
        elif any(keyword in tool_name.lower() for keyword in ['search']):
            bundles.append('search')
        elif any(keyword in tool_name.lower() for keyword in ['release', 'tag']):
            bundles.append('releases')
        elif any(keyword in tool_name.lower() for keyword in ['star']):
            bundles.append('social')
        else:
            bundles.append('external')  # Default bundle
        
        # Create the ToolModel
        tool_model = ToolModel(
            info=ToolInfo(
                name=tool_name,
                description=tool_description or f"External MCP tool: {tool_name}"
            ),
            tool_type=tool_type,
            cost=ToolCost(cost_per_call=cost_per_call),
        )
        
        # Add to bundles
        for bundle in bundles:
            tool_model.add_to_bundle(bundle)
        
        return tool_model
    
    def ensure_tool_models(self, tools: List[BaseTool]) -> None:
        """Ensure all discovered tools have ToolModel instances."""
        print(f"🔍 Ensuring ToolModels for {len(tools)} discovered tools...")
        
        created_count = 0
        existing_count = 0
        
        for tool in tools:
            if tool.name not in self._tool_models:
                # Extract description from the tool if available
                description = getattr(tool, 'description', '') or getattr(tool, 'name', '')
                tool_model = self.create_dynamic_tool_model(tool.name, description)
                self._tool_models[tool.name] = tool_model
                print(f"🆕 Created ToolModel: {tool.name} (${tool_model.cost.cost_per_call}, bundles: {tool_model.bundles.bundles})")
                created_count += 1
            else:
                existing_count += 1
        
        print(f"✅ ToolModel summary: {existing_count} existing, {created_count} created")
    
    def get_tool_model(self, tool_name: str) -> Optional[ToolModel]:
        """Get a ToolModel by name."""
        return self._tool_models.get(tool_name)
    
    def get_all_tool_models(self) -> Dict[str, ToolModel]:
        """Get all ToolModel instances."""
        return self._tool_models.copy()
    
    def get_bundles(self) -> Dict[str, List[str]]:
        """Generate bundle mapping from all ToolModel instances AND merge with role-specific bundles."""
        # 1. Get the base bundles generated from the tool models
        base_bundles = {}
        for tool_name, tool_model in self._tool_models.items():
            for bundle_name in tool_model.bundles.bundles:
                if bundle_name not in base_bundles:
                    base_bundles[bundle_name] = []
                base_bundles[bundle_name].append(tool_name)

        # 2. Define the additional, role-specific bundles
        additional_bundles = {
            "general_support": ["get_weather", "healthcheck"],
            "retrieval": ["search_code", "search_repositories"],
            "data": ["get_file_contents", "list_commits", "list_releases"],
            "social": [],
            "files": ["create_or_update_file", "delete_file", "get_file_contents", "push_files"],
            "git": ["create_branch", "create_repository", "fork_repository", "get_commit", "list_branches", "list_commits", "search_repositories", "star_repository", "unstar_repository"],
            "releases": ["get_latest_release", "get_release_by_tag", "get_tag", "list_releases", "list_tags"],
            "search": ["search_code", "search_repositories"],
        }

        # 3. Merge them, with additional_bundles taking precedence if needed
        merged_bundles = {**base_bundles, **additional_bundles}
        return merged_bundles
    
    def reset_monthly_costs(self):
        """Reset monthly costs for all tools (call at month start)."""
        for tool_model in self._tool_models.values():
            tool_model.cost.monthly_cost_usd = 0.0
            tool_model.updated_at = datetime.utcnow()
        print("💰 Monthly costs reset for all tools")


# ---------- Telemetry Wrapper Class ----------
class TelemetryWrapper:
    """Handles telemetry wrapping for tools with ToolModel integration."""
    
    def __init__(self, tool_model_manager: ToolModelManager):
        self.tool_model_manager = tool_model_manager
    
    def wrap_tools_with_telemetry(self, tools: List[BaseTool]) -> List[BaseTool]:
        """Apply telemetry wrapping to tools. Assumes ToolModels already exist."""
        wrapped = []
        
        print(f"🔗 Applying telemetry wrapping to {len(tools)} tools...")
        
        for t in tools:
            # Get the ToolModel (should exist after ensure_tool_models)
            tool_model = self.tool_model_manager.get_tool_model(t.name)
            if tool_model is None:
                print(f"⚠️  Warning: No ToolModel found for {t.name} - skipping usage tracking")
            
            # Apply wrapping to the appropriate method
            if hasattr(t, '_arun') and callable(t._arun):
                t._arun = self._create_tracked_wrapper(t._arun, t.name, tool_model, is_async=True)
            elif hasattr(t, '_run') and callable(t._run):
                t._run = self._create_tracked_wrapper(t._run, t.name, tool_model, is_async=False)
            else:
                print(f"⚠️  Could not wrap tool: {t.name} - no _run or _arun method found")
                
            wrapped.append(t)
        
        print(f"✅ Successfully applied telemetry wrapping to {len(wrapped)} tools")
        return wrapped
    
    def _create_tracked_wrapper(self, original_func, tool_name: str, tool_model: Optional[ToolModel], is_async: bool):
        """Create a tracking wrapper for sync or async functions."""
        if is_async:
            async def tracked_async_wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                try:
                    # Apply telemetry tracking
                    telemetry_wrapped = track_tools(tool_name=tool_name)(original_func)
                    result = await telemetry_wrapped(*args, **kwargs)
                    
                    # Log to ToolModel if available
                    if tool_model:
                        elapsed_ms = (time.perf_counter() - start_time) * 1000
                        tool_model.log_usage(num_calls=1, latency_ms=elapsed_ms)
                    
                    return result
                except Exception as e:
                    # Log failed usage if ToolModel available
                    if tool_model:
                        elapsed_ms = (time.perf_counter() - start_time) * 1000
                        tool_model.log_usage(num_calls=1, latency_ms=elapsed_ms)
                    raise
            return tracked_async_wrapper
        else:
            def tracked_sync_wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                try:
                    # Apply telemetry tracking
                    telemetry_wrapped = track_tools(tool_name=tool_name)(original_func)
                    result = telemetry_wrapped(*args, **kwargs)
                    
                    # Log to ToolModel if available
                    if tool_model:
                        elapsed_ms = (time.perf_counter() - start_time) * 1000
                        tool_model.log_usage(num_calls=1, latency_ms=elapsed_ms)
                    
                    return result
                except Exception as e:
                    # Log failed usage if ToolModel available
                    if tool_model:
                        elapsed_ms = (time.perf_counter() - start_time) * 1000
                        tool_model.log_usage(num_calls=1, latency_ms=elapsed_ms)
                    raise
            return tracked_sync_wrapper


# ---------- Analytics and Stats Class ----------
class ToolAnalytics:
    """Provides analytics and statistics for tool usage."""
    
    def __init__(self, tool_model_manager: ToolModelManager):
        self.tool_model_manager = tool_model_manager
        self.static_tools: Set[str] = {'get_weather', 'add', 'healthcheck', 'multiply'}
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics across all tools."""
        tool_models = self.tool_model_manager.get_all_tool_models()
        
        stats = {
            "total_tools": len(tool_models),
            "active_tools": sum(1 for tm in tool_models.values() if tm.is_active),
            "total_calls": sum(tm.cost.call_count for tm in tool_models.values()),
            "total_cost_usd": sum(tm.cost.total_cost_usd for tm in tool_models.values()),
            "monthly_cost_usd": sum(tm.cost.monthly_cost_usd for tm in tool_models.values()),
            "by_category": {},
            "by_bundle": self.tool_model_manager.get_bundles(),
            "performance_summary": {},
            "tool_origin": self._get_origin_stats(tool_models)
        }
        
        # Group by cost category
        for tool_model in tool_models.values():
            category = tool_model.cost_category
            if category not in stats["by_category"]:
                stats["by_category"][category] = 0
            stats["by_category"][category] += 1
        
        # Performance summary
        perf_scores = [tm.performance_score for tm in tool_models.values()]
        if perf_scores:
            stats["performance_summary"] = {
                "avg_performance": sum(perf_scores) / len(perf_scores),
                "min_performance": min(perf_scores),
                "max_performance": max(perf_scores)
            }
        
        return stats
    
    def _get_origin_stats(self, tool_models: Dict[str, ToolModel]) -> Dict[str, Any]:
        """Get statistics about static vs dynamically created tools."""
        dynamic_tools = set(tool_models.keys()) - self.static_tools
        print("DYNAMIC TOOLS: ", "COUNT: ", len(dynamic_tools), "Static Tools: ", self.static_tools)
        
        return {
            'static_tools': len(self.static_tools),
            'dynamic_tools': len(dynamic_tools),
            'dynamic_tool_names': list(dynamic_tools),
            'github_tools': [t for t in dynamic_tools if any(
                kw in t.lower() for kw in ['branch', 'commit', 'repo', 'file', 'release', 'star']
            )],
        }
    
    def get_top_tools(self, by: str = "usage", limit: int = 5) -> List[Dict[str, Any]]:
        """Get top tools by usage, cost, or performance."""
        tool_models = self.tool_model_manager.get_all_tool_models()
        
        if by == "usage":
            sorted_tools = sorted(tool_models.values(), key=lambda t: t.cost.call_count, reverse=True)
        elif by == "cost":
            sorted_tools = sorted(tool_models.values(), key=lambda t: t.cost.total_cost_usd, reverse=True)
        elif by == "performance":
            sorted_tools = sorted(tool_models.values(), key=lambda t: t.performance_score, reverse=True)
        else:
            raise ValueError(f"Invalid sort criteria: {by}")
        
        return [
            {
                "name": tm.info.name,
                "usage_calls": tm.cost.call_count,
                "total_cost": tm.cost.total_cost_usd,
                "performance_score": tm.performance_score,
                "bundles": tm.bundles.bundles
            }
            for tm in sorted_tools[:limit]
        ]
    
    def print_integration_summary(self):
        """Print a comprehensive summary of the integration."""
        stats = self.get_comprehensive_stats()
        
        print("\n" + "="*60)
        print("📊 TOOLMODEL INTEGRATION SUMMARY")
        print("="*60)
        print(f"📈 Total Tools: {stats['total_tools']}")
        print(f"🏠 Static Tools: {stats['tool_origin']['static_tools']}")
        print(f"🌐 Dynamic MCP Tools: {stats['tool_origin']['dynamic_tools']}")
        print(f"💰 Total Usage Cost: ${stats['total_cost_usd']:.4f}")
        print(f"📅 Monthly Cost: ${stats['monthly_cost_usd']:.4f}")
        print(f"📞 Total Calls: {stats['total_calls']}")
        print(f"📦 Active Bundles: {list(stats['by_bundle'].keys())}")
        
        if stats['tool_origin']['github_tools']:
            print(f"🐙 GitHub Tools: {len(stats['tool_origin']['github_tools'])}")
            
        # Show top tools by usage
        top_tools = self.get_top_tools(by="usage", limit=3)
        if any(t['usage_calls'] > 0 for t in top_tools):
            print("🏆 Most Used Tools:")
            for tool in top_tools:
                if tool['usage_calls'] > 0:
                    print(f"   • {tool['name']}: {tool['usage_calls']} calls, ${tool['total_cost']:.4f}")
        
        print("="*60 + "\n")


# ---------- Main Tool Registry Class ----------
class ToolRegistry:
    """Main coordinator class for tool management."""
    
    def __init__(self):
        self.tool_model_manager = ToolModelManager()
        self.telemetry_wrapper = TelemetryWrapper(self.tool_model_manager)
        self.analytics = ToolAnalytics(self.tool_model_manager)
    
    def process_mcp_tools(self, tools: List[BaseTool]) -> List[BaseTool]:
        """Complete processing pipeline for MCP tools."""
        # Step 1: Ensure ToolModels exist
        self.tool_model_manager.ensure_tool_models(tools)
        self.validate_integrity()
        # Step 2: Apply telemetry wrapping
        wrapped_tools = self.telemetry_wrapper.wrap_tools_with_telemetry(tools)
        
        # Step 3: Print summary
        self.analytics.print_integration_summary()
        
        return wrapped_tools
    
    # Convenience methods for backward compatibility
    def get_tool_models(self) -> Dict[str, ToolModel]:
        """Get all ToolModel instances."""
        return self.tool_model_manager.get_all_tool_models()
    
    def get_bundles(self) -> Dict[str, List[str]]:
        """Get bundle mapping."""
        return self.tool_model_manager.get_bundles()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        return self.analytics.get_comprehensive_stats()
    
    def validate_integrity(self) -> bool:
        """Validate tool registry integrity."""
        bundles = self.get_bundles()
        tool_models = self.get_tool_models()
        
        # Check for duplicate tool names
        names = [tm.info.name for tm in tool_models.values()]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate tool names found in registry")
        
        # Validate bundle references
        for bundle_name, tool_names in bundles.items():
            for tool_name in tool_names:
                if tool_name not in tool_models:
                    raise ValueError(f"Bundle '{bundle_name}' references unknown tool '{tool_name}'")
        
        return True


# ---------- Static tool definitions with ToolModel integration ----------
# Initialize the global registry
TOOL_REGISTRY = ToolRegistry()

# Get static ToolModels
WEATHER_TOOL = TOOL_REGISTRY.tool_model_manager.get_tool_model("get_weather")
ADD_TOOL = TOOL_REGISTRY.tool_model_manager.get_tool_model("add")
HEALTHCHECK_TOOL = TOOL_REGISTRY.tool_model_manager.get_tool_model("healthcheck")
MULTIPLY_TOOL = TOOL_REGISTRY.tool_model_manager.get_tool_model("multiply")

# LangChain tools with ToolModel integration
@tool
@resilient(tool_model=WEATHER_TOOL, retries=1, timeout_sec=3.0)
def get_weather(city: str) -> str:
    """Return a short, friendly weather snippet for the given city."""
    return get_weather_impl(city)

@tool
@resilient(tool_model=ADD_TOOL, retries=1, timeout_sec=1.0)
def add(a: int, b: int) -> int:
    """Add two integers and return the sum."""
    return add_impl(a, b)

@tool
@resilient(tool_model=HEALTHCHECK_TOOL, retries=1, timeout_sec=1.0)
def healthcheck() -> str:
    """Return 'OK' to verify that the tool runner is healthy."""
    return healthcheck_impl()

@tool
@resilient(tool_model=MULTIPLY_TOOL, retries=1, timeout_sec=1.0)
def multiply(a: int, b: int) -> int:
    """Multiply two integers and return the product."""
    return multiply_impl(a, b)

# ---------- Legacy compatibility ----------
TOOLS = TOOL_REGISTRY.get_tool_models()  # For backward compatibility
# TOOLS = {
#     "get_weather": get_weather,
#     "add": add, 
#     "healthcheck": healthcheck,
# }
BUNDLES = TOOL_REGISTRY.get_bundles()


# ---------- MCP registration with ToolModel integration ----------
def register_mcp_tools(mcp):
    """Register tools with MCP server using ToolModel metadata."""
    
    @mcp.tool(
        name=WEATHER_TOOL.info.name, 
        title="Get Weather", 
        description=WEATHER_TOOL.info.description
    )
    def mcp_get_weather(city: str) -> str:
        result = get_weather_impl(city)
        WEATHER_TOOL.log_usage(num_calls=1)
        return result

    @mcp.tool(
        name=ADD_TOOL.info.name,
        title="Add Numbers", 
        description=ADD_TOOL.info.description
    )
    def mcp_add(a: int, b: int) -> int:
        result = add_impl(a, b)
        ADD_TOOL.log_usage(num_calls=1)
        return result

    @mcp.tool(
        name=HEALTHCHECK_TOOL.info.name,
        title="Health Check", 
        description=HEALTHCHECK_TOOL.info.description
    )
    def mcp_healthcheck() -> str:
        result = healthcheck_impl()
        HEALTHCHECK_TOOL.log_usage(num_calls=1)
        return result
    
    @mcp.tool(
        name=MULTIPLY_TOOL.info.name,
        title="Multiply Numbers", 
        description=MULTIPLY_TOOL.info.description
    )
    def mcp_multiply(a: int, b: int) -> int:
        result = multiply_impl(a, b)
        MULTIPLY_TOOL.log_usage(num_calls=1)
        return result


# ---------- Main entry points ----------
def wrap_tools_with_telemetry(tools: List[BaseTool]) -> List[BaseTool]:
    """Main entry point for tool processing (backward compatibility)."""
    return TOOL_REGISTRY.process_mcp_tools(tools)

def get_tool_stats() -> Dict[str, Any]:
    """Get comprehensive tool statistics."""
    return TOOL_REGISTRY.get_stats()

def reset_monthly_costs():
    """Reset monthly costs for all tools."""
    TOOL_REGISTRY.tool_model_manager.reset_monthly_costs()

# Initialize and validate
# TOOL_REGISTRY.validate_integrity()


# Add this after the ToolRegistry initialization in tools.py
# def get_bundles() -> Dict[str, List[str]]:
#     """Get current bundle mapping with role-specific bundles."""
#     base_bundles = TOOL_REGISTRY.get_bundles()
    
#     # Add missing bundles that roles expect
#     additional_bundles = {
#         "general_support": ["get_weather", "healthcheck"],
#         "retrieval": ["search_code", "search_repositories"],
#         "data": ["get_file_contents", "list_commits", "list_releases"],
#         "social": [],  # Empty for now, add tools if needed
#         "files": ["create_or_update_file", "delete_file", "get_file_contents", "push_files"],
#         "git": ["create_branch", "create_repository", "fork_repository", "get_commit", "list_branches", "list_commits", "search_repositories", "star_repository", "unstar_repository"],
#         "releases": ["get_latest_release", "get_release_by_tag", "get_tag", "list_releases", "list_tags"],
#         "search": ["search_code", "search_repositories"],
#     }
    
#     # Merge with base bundles
#     merged_bundles = {**base_bundles, **additional_bundles}
#     return merged_bundles

# # Update the BUNDLES assignment
# BUNDLES = get_bundles()
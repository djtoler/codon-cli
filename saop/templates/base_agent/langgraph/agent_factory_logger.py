# langgraph/factory_logger.py
"""
Dedicated logging class for Agent Factory operations.
Abstracts all logging logic away from the main factory implementation.
"""

import logging
from typing import Dict, List, Any
from langchain_core.tools import BaseTool


class AgentFactoryLogger:
    """Handles all logging for Agent Factory operations."""
    
    def __init__(self, logger_name: str = "agent_factory"):
        self.log = logging.getLogger(logger_name)
    
    def log_factory_init(self, roles: Dict[str, Any], bundles: Dict[str, List[str]], tools: Dict[str, Any]):
        """Log factory initialization details."""
        self.log.info("Factory initializing...")
        self.log.info(f"Loaded {len(roles)} roles: {list(roles.keys())}")
        self.log.info(f"Available tool bundles: {list(bundles.keys())}")
        self.log.info(f"Available individual tools: {list(tools.keys())}")
    
    def log_validation_success(self):
        """Log successful role/tool validation."""
        self.log.info("Role/tool integrity validation passed")
    
    def log_tools_fetch_start(self):
        """Log start of tool fetching process."""
        self.log.info("Fetching all available tools from MCP...")
    
    def log_tools_fetch_complete(self, tools: List[BaseTool]):
        """Log completion of tool fetching."""
        tool_names = [tool.name for tool in tools]
        self.log.info(f"Retrieved {len(tools)} tools: {tool_names}")
    
    def log_tools_cache_hit(self):
        """Log when using cached tools."""
        self.log.debug("Using cached tools")
    
    def log_role_tool_resolution(self, role_name: str, direct_tools: List[str], bundles: List[str]):
        """Log tool resolution for a role."""
        if direct_tools:
            self.log.debug(f"Adding direct tools for {role_name}: {direct_tools}")
        if bundles:
            self.log.debug(f"Adding tool bundles for {role_name}: {bundles}")
    
    def log_bundle_expansion(self, bundle_name: str, bundle_tools: List[str]):
        """Log bundle expansion details."""
        self.log.debug(f"Bundle '{bundle_name}' contains: {bundle_tools}")
    
    def log_missing_tool(self, tool_name: str, role_name: str):
        """Log warning for missing direct tool."""
        self.log.warning(f"Direct tool '{tool_name}' not found in TOOLS registry for role '{role_name}'")
    
    def log_missing_bundle(self, bundle_name: str, role_name: str):
        """Log warning for missing bundle."""
        self.log.warning(f"Bundle '{bundle_name}' not found in BUNDLES registry for role '{role_name}'")
    
    def log_tool_filtering_start(self, role_name: str, allowed_tools: List[str]):
        """Log start of tool filtering process."""
        self.log.info(f"Filtering tools for role: {role_name}")
        self.log.info(f"Role '{role_name}' should have access to: {allowed_tools}")
    
    def log_tool_include(self, tool_name: str):
        """Log tool inclusion."""
        self.log.debug(f"Including tool: {tool_name}")
    
    def log_tool_exclude(self, tool_name: str):
        """Log tool exclusion."""
        self.log.debug(f"Excluding tool: {tool_name}")
    
    def log_tool_filtering_complete(self, role_name: str, final_tools: List[str]):
        """Log completion of tool filtering."""
        self.log.info(f"Final filtered tools for '{role_name}': {final_tools}")
    
    def log_no_tools_warning(self, role_name: str):
        """Log warning when role has no tools."""
        self.log.warning(f"Role '{role_name}' has no available tools!")
    
    def log_custom_llm_creation(self, role_name: str, model_id: str):
        """Log custom LLM creation."""
        self.log.info(f"Creating custom LLM for role '{role_name}' with model: {model_id}")
    
    def log_default_llm_creation(self, role_name: str):
        """Log default LLM creation."""
        self.log.info(f"Using default LLM for role '{role_name}'")
    
    def log_agent_creation_start(self, role_name: str):
        """Log start of agent creation."""
        self.log.info(f"Creating agent for role: {role_name}")
    
    def log_role_not_found(self, role_name: str, available_roles: List[str]):
        """Log error for role not found."""
        error_msg = f"Role '{role_name}' not found. Available roles: {available_roles}"
        self.log.error(error_msg)
        return error_msg
    
    def log_role_details(self, role_config: Dict[str, Any], tool_count: int):
        """Log role configuration details."""
        prompt_preview = role_config['system_prompt'][:60] + "..."
        self.log.info(f"System prompt: {prompt_preview}")
        self.log.info(f"Tags: {role_config['metadata']['tags']}")
        self.log.info(f"Cost hint: {role_config['metadata']['cost_hint']}")
        if role_config.get("human_review"):
            self.log.info("Human review required: YES")
    
    def log_agent_creation_complete(self, role_name: str, tool_count: int):
        """Log successful agent creation."""
        self.log.info(f"Agent '{role_name}' created successfully with {tool_count} tools")
    
    def log_list_roles_start(self):
        """Log start of role listing."""
        self.log.info("Listing all available roles...")
    
    def log_role_summary(self, name: str, tool_count: int, cost_hint: float):
        """Log individual role summary."""
        self.log.debug(f"Role '{name}': {tool_count} tools, cost={cost_hint}")
    
    def log_list_roles_complete(self, role_count: int):
        """Log completion of role listing."""
        self.log.info(f"Total roles available: {role_count}")
    
    def log_template_init_start(self, role_name: str):
        """Log start of RoleBasedAgentTemplate initialization."""
        self.log.info(f"Initializing RoleBasedAgentTemplate for role: {role_name}")
    
    def log_llm_binding(self, tool_count: int, tool_names: List[str]):
        """Log LLM binding details."""
        self.log.debug(f"LLM bound to {tool_count} tools: {tool_names}")
    
    def log_template_init_complete(self, role_name: str):
        """Log successful template initialization."""
        self.log.info(f"RoleBasedAgentTemplate '{role_name}' initialized successfully")
    
    def log_components_already_initialized(self, role_name: str):
        """Log when components are already initialized."""
        self.log.debug(f"Components already initialized for role '{role_name}'")
    
    def log_building_graph(self, role_name: str):
        """Log graph building process."""
        self.log.debug(f"Building graph for role '{role_name}'")

    def log_executor_init_start(self, role_name: str):
        """Log start of executor initialization."""
        self.log.info(f"Initializing LangGraphA2AExecutor for role: {role_name}")

    def log_executor_init_success(self, role_name: str, tool_count: int, tool_names: List[str]):
        """Log successful executor initialization."""
        self.log.info(f"Executor '{role_name}' initialized successfully with {tool_count} tools: {tool_names}")

    def log_executor_init_failure(self, role_name: str, error: str):
        """Log executor initialization failure."""
        self.log.error(f"Failed to initialize executor for role '{role_name}': {error}")

    def log_executor_degraded_mode(self, role_name: str, error: str):
        """Log executor running in degraded mode."""
        self.log.warning(f"Executor '{role_name}' running in degraded mode: {error}")

    def log_executor_role_not_found(self, role_name: str, available_roles: List[str]):
        """Log executor role not found error."""
        error_msg = f"Executor role '{role_name}' not found. Available roles: {available_roles}"
        self.log.error(error_msg)
        return error_msg

    def log_executor_validation_error(self, role_name: str, validation_error: str):
        """Log executor validation error."""
        self.log.error(f"Executor role '{role_name}' validation failed: {validation_error}")

    def log_executor_runtime_error(self, role_name: str, runtime_error: str):
        """Log executor runtime error."""
        self.log.error(f"Executor '{role_name}' runtime error: {runtime_error}")

    def log_executor_execution_blocked(self, role_name: str, reason: str):
        """Log when executor execution is blocked."""
        self.log.warning(f"Execution blocked for '{role_name}': {reason}")

    def log_executor_graceful_recovery(self, role_name: str, action: str):
        """Log executor graceful recovery actions."""
        self.log.info(f"Executor '{role_name}' graceful recovery: {action}")
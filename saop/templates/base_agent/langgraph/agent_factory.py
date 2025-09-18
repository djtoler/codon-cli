# langgraph/agent_factory.py
"""
Agent Factory implementation that creates role-based agents.
Uses your existing AgentComponents and AgentTemplate as building blocks.
"""

import asyncio
from typing import Dict, List, Any, Optional
from langchain_core.tools import BaseTool
from langchain.chat_models import init_chat_model

from config.roles import get_roles
from _mcp.tools import TOOLS, BUNDLES
from config.agent_config import load_env_config
from langgraph.langgraph_agent import AgentComponents, AgentTemplate
from langgraph.agent_factory_logger import AgentFactoryLogger


class AgentFactory:
    """
    Factory for creating role-based agents using existing components.
    Orchestrates AgentComponents and extends AgentTemplate with role filtering.
    """
    
    def __init__(self):
        self.logger = AgentFactoryLogger()
        self.env_config = load_env_config()
        self._all_tools_cache = None
        self._roles = get_roles()
        
        self.logger.log_factory_init(self._roles, BUNDLES, TOOLS)
        # validate_bundle_names()
        # self.logger.log_validation_success()
    
    async def _get_all_tools(self) -> List[BaseTool]:
        """Get all available tools using existing AgentComponents."""
        if self._all_tools_cache is not None:
            self.logger.log_tools_cache_hit()
            return self._all_tools_cache
            
        self.logger.log_tools_fetch_start()
        components = AgentComponents()
        self._all_tools_cache = await components.create_tools()
        self.logger.log_tools_fetch_complete(self._all_tools_cache)
        return self._all_tools_cache
    
    def _resolve_role_tools(self, role_config: Dict[str, Any]) -> List[str]:
        """
        Resolve which tools a role should have access to.
        Uses the same logic as your existing bundle system.
        """
        allowed_tools = set()
        role_name = role_config.get("name", "unknown")
        
        # Add direct tool references
        direct_tools = role_config.get("tools", [])
        bundles = role_config.get("tool_bundles", [])
        self.logger.log_role_tool_resolution(role_name, direct_tools, bundles)
        
        for tool_name in direct_tools:
            if tool_name in TOOLS:
                allowed_tools.add(tool_name)
            else:
                self.logger.log_missing_tool(tool_name, role_name)
        
        # Add tools from bundles
        for bundle_name in bundles:
            if bundle_name in BUNDLES:
                bundle_tools = BUNDLES[bundle_name]
                self.logger.log_bundle_expansion(bundle_name, bundle_tools)
                allowed_tools.update(bundle_tools)
            else:
                self.logger.log_missing_bundle(bundle_name, role_name)
                
        return list(allowed_tools)
    
    async def _filter_tools_for_role(self, role_name: str) -> List[BaseTool]:
        """
        Filter the full tool set to only include tools allowed for this role.
        """
        role_config = self._roles[role_name]
        allowed_tool_names = self._resolve_role_tools(role_config)
        self.logger.log_tool_filtering_start(role_name, allowed_tool_names)
        
        all_tools = await self._get_all_tools()
        
        # Filter tools by name - only include tools this role is allowed to use
        filtered_tools = []
        for tool in all_tools:
            if tool.name in allowed_tool_names:
                filtered_tools.append(tool)
                self.logger.log_tool_include(tool.name)
            else:
                self.logger.log_tool_exclude(tool.name)
        
        actual_tool_names = [tool.name for tool in filtered_tools]
        self.logger.log_tool_filtering_complete(role_name, actual_tool_names)
        
        if not filtered_tools:
            self.logger.log_no_tools_warning(role_name)
                
        return filtered_tools
    
    def _create_role_llm(self, role_config: Dict[str, Any]):
        """
        Create LLM with role-specific overrides if specified.
        Falls back to default config from AgentComponents.
        """
        role_name = role_config.get("name", "unknown")
        model_id = role_config.get("model_id")
        
        if model_id:
            self.logger.log_custom_llm_creation(role_name, model_id)
            # Parse provider:model format
            if ":" in model_id:
                provider, model_name = model_id.split(":", 1)
                return init_chat_model(
                    model=model_name,
                    model_provider=provider,
                    openai_api_key=self.env_config["MODEL_API_KEY"],
                )
            else:
                return init_chat_model(
                    model=model_id,
                    openai_api_key=self.env_config["MODEL_API_KEY"],
                    model_provider=self.env_config["MODEL_PROVIDER"],
                )
        else:
            self.logger.log_default_llm_creation(role_name)
            # Use default from AgentComponents
            components = AgentComponents()
            return components.create_llm()
    
    async def create_agent(self, role_name: str) -> "RoleBasedAgentTemplate":
        """
        Create an agent instance for the specified role.
        """
        self.logger.log_agent_creation_start(role_name)
        
        if role_name not in self._roles:
            available_roles = list(self._roles.keys())
            error_msg = self.logger.log_role_not_found(role_name, available_roles)
            raise ValueError(error_msg)
        
        role_config = self._roles[role_name]
        
        # Get role-specific components
        filtered_tools = await self._filter_tools_for_role(role_name)
        self.logger.log_role_details(role_config, len(filtered_tools))
        
        role_llm = self._create_role_llm(role_config)
        
        self.logger.log_agent_creation_complete(role_name, len(filtered_tools))
        
        return RoleBasedAgentTemplate(
            role_name=role_name,
            role_config=role_config,
            llm=role_llm,
            tools=filtered_tools,
            logger=self.logger
        )
    
    def list_roles(self) -> List[Dict[str, Any]]:
        """List all available roles with their metadata."""
        self.logger.log_list_roles_start()
        roles_info = []
        
        for name, config in self._roles.items():
            allowed_tools = self._resolve_role_tools(name, config)
            role_info = {
                "name": name,
                "system_prompt": config["system_prompt"],
                "tools": allowed_tools,
                "tool_bundles": config.get("tool_bundles", []),
                "tags": config["metadata"]["tags"],
                "cost_hint": config["metadata"]["cost_hint"],
                "human_review": config.get("human_review", False),
            }
            roles_info.append(role_info)
            self.logger.log_role_summary(name, len(allowed_tools), config["metadata"]["cost_hint"])
        
        self.logger.log_list_roles_complete(len(roles_info))
        return roles_info


class RoleBasedAgentTemplate(AgentTemplate):
    """
    Extended AgentTemplate that incorporates role-specific behavior.
    Preserves all existing AgentTemplate functionality while adding role context.
    """
    
    def __init__(self, role_name: str, role_config: Dict[str, Any], llm, tools: List[BaseTool], logger: AgentFactoryLogger):
        self.logger = logger
        self.logger.log_template_init_start(role_name)
        
        super().__init__()
        self.role_name = role_name
        self.role_config = role_config
        self._llm = llm
        self._tools = tools
        self._llm_chain = llm.bind_tools(tools)
        
        tool_names = [t.name for t in tools]
        self.logger.log_llm_binding(len(tools), tool_names)
        
        # Initialize graph with role-specific components
        self._init_graph()
        self.logger.log_template_init_complete(role_name)
    
    async def _initialize_components(self):
        """Override - components are already initialized in constructor."""
        if self._graph is not None:
            self.logger.log_components_already_initialized(self.role_name)
            return
        # Components already set up, just ensure graph is built
        if self._graph is None:
            self.logger.log_building_graph(self.role_name)
            self._init_graph()
    
    @property
    def system_prompt(self) -> str:
        """Get the system prompt for this role."""
        return self.role_config["system_prompt"]
    
    def get_role_info(self) -> Dict[str, Any]:
        """Get information about this agent's role."""
        return {
            "role_name": self.role_name,
            "system_prompt": self.system_prompt,
            "tools": [tool.name for tool in self._tools],
            "tool_count": len(self._tools),
            "metadata": self.role_config["metadata"]
        }
    
    def requires_human_review(self) -> bool:
        """Check if this role requires human review."""
        return self.role_config.get("human_review", False)
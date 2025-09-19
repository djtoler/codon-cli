# # langgraph/agent_factory.py
# """
# Agent Factory implementation that creates role-based agents.
# Uses your existing AgentComponents and AgentTemplate as building blocks.
# """

# import asyncio
# from typing import Dict, List, Any, Optional
# from langchain_core.tools import BaseTool
# from langchain.chat_models import init_chat_model

# from config.roles import get_roles
# from _mcp.tools import TOOLS, BUNDLES
# from config.agent_config import load_env_config
# from langgraph.langgraph_agent import AgentComponents, AgentTemplate
# from langgraph.agent_factory_logger import AgentFactoryLogger


# # Updated AgentFactory to handle both main agent and expert roles
# class AgentFactory:
#     def __init__(self):
#         self.logger = AgentFactoryLogger()
#         self.env_config = load_env_config()
#         self._all_tools_cache = None
#         self._roles = get_roles()  # Expert roles from roles.py
        
#         # Get main agent config from policy
#         try:
#             from config.policy.policy_config import get_policy_config
#             self.policy_config = get_policy_config()
#             self.main_agent_config = self.policy_config.main_agent
#         except Exception as e:
#             self.logger.log_warning(f"Could not load main agent config: {e}")
#             self.main_agent_config = None
        
#         self.logger.log_factory_init(self._roles, BUNDLES, TOOLS)

#     async def create_agent(self, role_name: str):
#         """Create either main agent or expert role agent"""
        
#         # Check if this is the main agent
#         if self.main_agent_config and role_name == self.main_agent_config.name:
#             return await self._create_main_agent(role_name)
        
#         # Otherwise, create expert role agent
#         return await self._create_expert_agent(role_name)
    
#     async def _create_main_agent(self, role_name: str):
#         """Create the main agent from policy configuration"""
#         self.logger.log_agent_creation_start(f"{role_name} (MAIN AGENT)")
        
#         if not self.main_agent_config:
#             raise ValueError(f"Main agent config not available for: {role_name}")
        
#         # Get tools for main agent from policy config
#         main_agent_tools = getattr(self.main_agent_config, 'tools', [])
#         main_agent_bundles = getattr(self.main_agent_config, 'tool_bundles', [])
        
#         # Resolve tools from bundles
#         all_allowed_tools = set(main_agent_tools)
#         for bundle_name in main_agent_bundles:
#             if bundle_name in BUNDLES:
#                 all_allowed_tools.update(BUNDLES[bundle_name])
        
#         # Filter available tools
#         filtered_tools = await self._filter_tools_for_main_agent(role_name, list(all_allowed_tools))

        
#         # Create main agent LLM
#         main_agent_llm = self._create_main_agent_llm()
        
#         self.logger.log_agent_creation_complete(f"{role_name} (MAIN)", len(filtered_tools))
        
#         # Return MainAgentTemplate instead of RoleBasedAgentTemplate
#         return MainAgentTemplate(
#             role_name=role_name,
#             main_agent_config=self.main_agent_config,
#             llm=main_agent_llm,
#             tools=filtered_tools,
#             logger=self.logger
#         )
    
#     async def _create_expert_agent(self, role_name: str):
#         """Create expert role agent from roles.py (existing logic)"""
#         self.logger.log_agent_creation_start(f"{role_name} (EXPERT)")
        
#         if role_name not in self._roles:
#             available_roles = list(self._roles.keys())
#             error_msg = self.logger.log_role_not_found(role_name, available_roles)
#             raise ValueError(error_msg)
        
#         role_config = self._roles[role_name]
        
#         # Existing expert role creation logic
#         filtered_tools = await self._filter_tools_for_role(role_name)
#         role_llm = self._create_role_llm(role_config)
        
#         self.logger.log_agent_creation_complete(f"{role_name} (EXPERT)", len(filtered_tools))
        
#         return RoleBasedAgentTemplate(
#             role_name=role_name,
#             role_config=role_config,
#             llm=role_llm,
#             tools=filtered_tools,
#             logger=self.logger
#         )
    
#     def _create_main_agent_llm(self):
#         """Create LLM for main agent"""
#         model_config = getattr(self.main_agent_config, 'model', {})
        
#         # This block is now updated to correctly use the model dictionary
#         if model_config and model_config.get('model'):
#             self.logger.log_custom_llm_creation(f"main_agent", model_config)
#             # Unpack the entire dictionary (model, model_provider, temperature, etc.)
#             return init_chat_model(**model_config)
#         else:
#             self.logger.log_default_llm_creation("main_agent")
#             # This was the source of the error, now fixed to pass the required config
#             components = AgentComponents(main_agent_config=self.main_agent_config, role_name=self.main_agent_config.name)
#             return components.create_llm()
        
#     async def _filter_tools_for_main_agent(self, role_name: str, allowed_tool_names: List[str]) -> List[BaseTool]:
#         """Filter tools for main agent based on policy config"""
#         self.logger.log_tool_filtering_start(role_name, allowed_tool_names)
        
#         # Use the correct existing method from your AgentFactory
#         all_tools = await self._get_all_tools()  # This is the correct method name
        
#         # Filter tools by name - only include tools this main agent is allowed to use
#         filtered_tools = []
#         for tool in all_tools:
#             if tool.name in allowed_tool_names:
#                 filtered_tools.append(tool)
#                 self.logger.log_tool_include(tool.name)
#             else:
#                 self.logger.log_tool_exclude(tool.name)
        
#         actual_tool_names = [tool.name for tool in filtered_tools]
#         self.logger.log_tool_filtering_complete(role_name, actual_tool_names)
        
#         return filtered_tools
    
#     async def _get_all_tools(self) -> List[BaseTool]:
#         """Get all available tools using existing AgentComponents."""
#         if self._all_tools_cache is not None:
#             self.logger.log_tools_cache_hit()
#             return self._all_tools_cache
            
#         self.logger.log_tools_fetch_start()
#         components = AgentComponents(main_agent_config=self.main_agent_config)
#         self._all_tools_cache = await components.create_tools()
#         self.logger.log_tools_fetch_complete(self._all_tools_cache)

#         return self._all_tools_cache


#     async def _filter_tools_for_role(self, role_name: str) -> List[BaseTool]:
#         """
#         Filter the full tool set to only include tools allowed for this role.
#         """
#         role_config = self._roles[role_name]
#         allowed_tool_names = self._resolve_role_tools(role_config)
#         self.logger.log_tool_filtering_start(role_name, allowed_tool_names)
        
#         all_tools = await self._get_all_tools()
        
#         # Filter tools by name - only include tools this role is allowed to use
#         filtered_tools = []
#         for tool in all_tools:
#             if tool.name in allowed_tool_names:
#                 filtered_tools.append(tool)
#                 self.logger.log_tool_include(tool.name)
#             else:
#                 self.logger.log_tool_exclude(tool.name)
        
#         actual_tool_names = [tool.name for tool in filtered_tools]
#         self.logger.log_tool_filtering_complete(role_name, actual_tool_names)
        
#         if not filtered_tools:
#             self.logger.log_no_tools_warning(role_name)
                
#         return filtered_tools
    
#     def _resolve_role_tools(self, role_config: Dict[str, Any]) -> List[str]:
#             """
#             Resolve which tools a role should have access to.
#             Uses the same logic as your existing bundle system.
#             """
#             allowed_tools = set()
#             role_name = role_config.get("name", "unknown")
            
#             # Add direct tool references
#             direct_tools = role_config.get("tools", [])
#             bundles = role_config.get("tool_bundles", [])
#             self.logger.log_role_tool_resolution(role_name, direct_tools, bundles)
            
#             for tool_name in direct_tools:
#                 if tool_name in TOOLS:
#                     allowed_tools.add(tool_name)
#                 else:
#                     self.logger.log_missing_tool(tool_name, role_name)
            
#             # Add tools from bundles
#             for bundle_name in bundles:
#                 if bundle_name in BUNDLES:
#                     bundle_tools = BUNDLES[bundle_name]
#                     self.logger.log_bundle_expansion(bundle_name, bundle_tools)
#                     allowed_tools.update(bundle_tools)
#                 else:
#                     self.logger.log_missing_bundle(bundle_name, role_name)
                    
#             return list(allowed_tools)


#     def _create_role_llm(self, role_config: Dict[str, Any]):
#         """
#         Create LLM with role-specific overrides if specified.
#         Falls back to default config from AgentComponents.
#         """
#         role_name = role_config.get("name", "unknown")
#         model_id = role_config.get("model_id")
        
#         if model_id:
#             self.logger.log_custom_llm_creation(role_name, model_id)
#             # Parse provider:model format
#             if ":" in model_id:
#                 provider, model_name = model_id.split(":", 1)
#                 return init_chat_model(
#                     model=model_name,
#                     model_provider=provider,
#                     openai_api_key=self.env_config["MODEL_API_KEY"],
#                 )
#             else:
#                 return init_chat_model(
#                     model=model_id,
#                     openai_api_key=self.env_config["MODEL_API_KEY"],
#                     model_provider=self.env_config["MODEL_PROVIDER"],
#                 )
#         else:
#             self.logger.log_default_llm_creation("main_agent")
#             # CHANGE HERE: Pass the config the factory already has
#             components = AgentComponents(main_agent_config=self.main_agent_config)
#             return components.create_llm()



# class MainAgentTemplate(AgentTemplate):
#     """Main agent template using policy configuration"""
    
#     def __init__(self, role_name: str, main_agent_config, llm, tools: List[BaseTool], logger):
#         super().__init__()
#         self.role_name = role_name
#         self.main_agent_config = main_agent_config
#         self._llm = llm
#         self._tools = tools
#         self._llm_chain = llm.bind_tools(tools)
#         self.logger = logger
        
#         # Initialize graph with main agent components
#         self._init_graph()
#         self.logger.log_template_init_complete(f"{role_name} (MAIN AGENT)")
    
#     def get_role_info(self) -> Dict[str, Any]:
#         """Get information about this agent's role - required by executor and Agent Card"""
#         return {
#             "role_name": self.role_name,
#             "system_prompt": self.system_prompt,  # Use the property
#             "tools": [tool.name for tool in self._tools],
#             "tool_count": len(self._tools),
#             "metadata": {
#                 "type": "main_agent",
#                 "source": "policy_config",
#                 "description": getattr(self.main_agent_config, 'description', f'Main agent: {self.role_name}'),
#                 "capabilities": getattr(self.main_agent_config, 'capabilities', []),
#                 "model": getattr(self.main_agent_config, 'model', {}),
#                 **getattr(self.main_agent_config, 'metadata', {})  # Merge any existing metadata
#             }
#         }

#     def requires_human_review(self) -> bool:
#         """Check if this main agent requires human review - required by executor"""
#         return getattr(self.main_agent_config, 'human_review', False)

#     @property
#     def system_prompt(self) -> str:
#         """Get the system prompt for this main agent from policy_config"""
#         return getattr(self.main_agent_config, 'system_prompt', f'You are {self.role_name}, a specialized AI assistant.')
    
#     # Optional: Add this method if you want to be explicit about main agent info
#     def get_main_agent_info(self) -> Dict[str, Any]:
#         """Get main agent specific info from policy_config"""
#         return {
#             "role_name": self.role_name,
#             "agent_type": "main_agent",
#             "config_source": "policy_yaml",
#             "system_prompt": self.system_prompt,
#             "tools": [tool.name for tool in self._tools],
#             "tool_count": len(self._tools),
#             "human_review_required": self.requires_human_review(),
#             "model_config": getattr(self.main_agent_config, 'model', {}),
#             "description": getattr(self.main_agent_config, 'description', ''),
#             "capabilities": getattr(self.main_agent_config, 'capabilities', []),
#             "metadata": getattr(self.main_agent_config, 'metadata', {})
#         }



# class RoleBasedAgentTemplate(AgentTemplate):
#     """
#     Extended AgentTemplate that incorporates role-specific behavior.
#     Preserves all existing AgentTemplate functionality while adding role context.
#     """
    
#     def __init__(self, role_name: str, role_config: Dict[str, Any], llm, tools: List[BaseTool], logger: AgentFactoryLogger):
#         self.logger = logger
#         self.logger.log_template_init_start(role_name)
        
#         super().__init__()
#         self.role_name = role_name
#         self.role_config = role_config
#         self._llm = llm
#         self._tools = tools
#         self._llm_chain = llm.bind_tools(tools)
#         print("self.role_name: ", self.role_name)
        
#         tool_names = [t.name for t in tools]
#         self.logger.log_llm_binding(len(tools), tool_names)
        
#         # Initialize graph with role-specific components
#         self._init_graph()
#         self.logger.log_template_init_complete(role_name)
    
#     async def _initialize_components(self):
#         """Override - components are already initialized in constructor."""
#         if self._graph is not None:
#             self.logger.log_components_already_initialized(self.role_name)
#             return
#         # Components already set up, just ensure graph is built
#         if self._graph is None:
#             self.logger.log_building_graph(self.role_name)
#             self._init_graph()
    
#     @property
#     def system_prompt(self) -> str:
#         """Get the system prompt for this role."""
#         return self.role_config["system_prompt"]
    
#     def get_role_info(self) -> Dict[str, Any]:
#         """Get information about this agent's role."""
#         return {
#             "role_name": self.role_name,
#             "system_prompt": self.system_prompt,
#             "tools": [tool.name for tool in self._tools],
#             "tool_count": len(self._tools),
#             "metadata": self.role_config["metadata"]
#         }
    
#     def requires_human_review(self) -> bool:
#         """Check if this role requires human review."""
#         return self.role_config.get("human_review", False)












# langgraph/agent_factory.py
"""
Agent Factory implementation that creates role-based agents.
Uses AgentComponents for ALL agents to ensure consistent policy engine usage.
"""

import asyncio
from typing import Dict, List, Any, Optional
from langchain_core.tools import BaseTool

from config.roles import get_roles
from _mcp.tools import TOOLS, BUNDLES
from config.agent_config import load_env_config
from langgraph.langgraph_agent import AgentComponents, AgentTemplate
from langgraph.agent_factory_logger import AgentFactoryLogger


class AgentFactory:
    def __init__(self):
        self.logger = AgentFactoryLogger()
        self.env_config = load_env_config()
        self._all_tools_cache = None
        self._roles = get_roles()  # Expert roles from roles.py
        
        # Get main agent config from policy
        try:
            from config.policy.policy_config import get_policy_config
            self.policy_config = get_policy_config()
            self.main_agent_config = self.policy_config.main_agent
        except Exception as e:
            self.logger.log_warning(f"Could not load main agent config: {e}")
            self.main_agent_config = None
        
        self.logger.log_factory_init(self._roles, BUNDLES, TOOLS)

    async def create_agent(self, role_name: str):
        """Create either main agent or expert role agent"""
        
        # Check if this is the main agent
        if self.main_agent_config and role_name == self.main_agent_config.name:
            return await self._create_main_agent(role_name)
        
        # Otherwise, create expert role agent
        return await self._create_expert_agent(role_name)
    
    async def _create_main_agent(self, role_name: str):
        """Create the main agent from policy configuration"""
        self.logger.log_agent_creation_start(f"{role_name} (MAIN AGENT)")
        
        if not self.main_agent_config:
            raise ValueError(f"Main agent config not available for: {role_name}")
        
        # Get tools for main agent from policy config
        main_agent_tools = getattr(self.main_agent_config, 'tools', [])
        main_agent_bundles = getattr(self.main_agent_config, 'tool_bundles', [])
        
        # Resolve tools from bundles
        all_allowed_tools = set(main_agent_tools)
        for bundle_name in main_agent_bundles:
            if bundle_name in BUNDLES:
                all_allowed_tools.update(BUNDLES[bundle_name])
        
        # Filter available tools
        filtered_tools = await self._filter_tools_for_main_agent(role_name, list(all_allowed_tools))
        
        # Create main agent LLM using AgentComponents (includes policy engine)
        main_agent_llm = self._create_llm_with_policy(role_name)
        
        self.logger.log_agent_creation_complete(f"{role_name} (MAIN)", len(filtered_tools))
        
        return MainAgentTemplate(
            role_name=role_name,
            main_agent_config=self.main_agent_config,
            llm=main_agent_llm,
            tools=filtered_tools,
            logger=self.logger
        )
    
    async def _create_expert_agent(self, role_name: str):
        """Create expert role agent from roles.py"""
        self.logger.log_agent_creation_start(f"{role_name} (EXPERT)")
        
        if role_name not in self._roles:
            available_roles = list(self._roles.keys())
            error_msg = self.logger.log_role_not_found(role_name, available_roles)
            raise ValueError(error_msg)
        
        role_config = self._roles[role_name]
        
        # Get tools and LLM for expert agent
        filtered_tools = await self._filter_tools_for_role(role_name)
        role_llm = self._create_llm_with_policy(role_name)
        
        self.logger.log_agent_creation_complete(f"{role_name} (EXPERT)", len(filtered_tools))
        
        return RoleBasedAgentTemplate(
            role_name=role_name,
            role_config=role_config,
            llm=role_llm,
            tools=filtered_tools,
            logger=self.logger
        )
    
    def _create_llm_with_policy(self, role_name: str):
        """Create LLM using AgentComponents (includes policy engine) for ALL agents"""
        self.logger.log_default_llm_creation(role_name)
        
        # ALL agents use AgentComponents for consistent policy engine usage
        components = AgentComponents(
            main_agent_config=self.main_agent_config,
            role_name=role_name  # Pass actual role name for policy decisions
        )
        return components.create_llm()
        
    async def _filter_tools_for_main_agent(self, role_name: str, allowed_tool_names: List[str]) -> List[BaseTool]:
        """Filter tools for main agent based on policy config"""
        self.logger.log_tool_filtering_start(role_name, allowed_tool_names)
        
        all_tools = await self._get_all_tools()
        
        # Filter tools by name - only include tools this main agent is allowed to use
        filtered_tools = []
        for tool in all_tools:
            if tool.name in allowed_tool_names:
                filtered_tools.append(tool)
                self.logger.log_tool_include(tool.name)
            else:
                self.logger.log_tool_exclude(tool.name)
        
        actual_tool_names = [tool.name for tool in filtered_tools]
        self.logger.log_tool_filtering_complete(role_name, actual_tool_names)
        
        return filtered_tools
    
    async def _get_all_tools(self) -> List[BaseTool]:
        """Get all available tools using existing AgentComponents"""
        if self._all_tools_cache is not None:
            self.logger.log_tools_cache_hit()
            return self._all_tools_cache
            
        self.logger.log_tools_fetch_start()
        components = AgentComponents(main_agent_config=self.main_agent_config)
        self._all_tools_cache = await components.create_tools()
        self.logger.log_tools_fetch_complete(self._all_tools_cache)

        return self._all_tools_cache

    async def _filter_tools_for_role(self, role_name: str) -> List[BaseTool]:
        """Filter the full tool set to only include tools allowed for this role"""
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
    
    def _resolve_role_tools(self, role_config: Dict[str, Any]) -> List[str]:
        """Resolve which tools a role should have access to"""
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


class MainAgentTemplate(AgentTemplate):
    """Main agent template using policy configuration"""
    
    def __init__(self, role_name: str, main_agent_config, llm, tools: List[BaseTool], logger):
        super().__init__()
        self.role_name = role_name
        self.main_agent_config = main_agent_config
        self._llm = llm
        self._tools = tools
        self._llm_chain = llm.bind_tools(tools)
        self.logger = logger
        
        # Initialize graph with main agent components
        self._init_graph()
        self.logger.log_template_init_complete(f"{role_name} (MAIN AGENT)")
    
    def get_role_info(self) -> Dict[str, Any]:
        """Get information about this agent's role - required by executor and Agent Card"""
        return {
            "role_name": self.role_name,
            "system_prompt": self.system_prompt,
            "tools": [tool.name for tool in self._tools],
            "tool_count": len(self._tools),
            "metadata": {
                "type": "main_agent",
                "source": "policy_config",
                "description": getattr(self.main_agent_config, 'description', f'Main agent: {self.role_name}'),
                "capabilities": getattr(self.main_agent_config, 'capabilities', []),
                "model": getattr(self.main_agent_config, 'model', {}),
                **getattr(self.main_agent_config, 'metadata', {})
            }
        }

    def requires_human_review(self) -> bool:
        """Check if this main agent requires human review - required by executor"""
        return getattr(self.main_agent_config, 'human_review', False)

    @property
    def system_prompt(self) -> str:
        """Get the system prompt for this main agent from policy_config"""
        return getattr(self.main_agent_config, 'system_prompt', f'You are {self.role_name}, a specialized AI assistant.')
    
    def get_main_agent_info(self) -> Dict[str, Any]:
        """Get main agent specific info from policy_config"""
        return {
            "role_name": self.role_name,
            "agent_type": "main_agent",
            "config_source": "policy_yaml",
            "system_prompt": self.system_prompt,
            "tools": [tool.name for tool in self._tools],
            "tool_count": len(self._tools),
            "human_review_required": self.requires_human_review(),
            "model_config": getattr(self.main_agent_config, 'model', {}),
            "description": getattr(self.main_agent_config, 'description', ''),
            "capabilities": getattr(self.main_agent_config, 'capabilities', []),
            "metadata": getattr(self.main_agent_config, 'metadata', {})
        }


class RoleBasedAgentTemplate(AgentTemplate):
    """Extended AgentTemplate that incorporates role-specific behavior"""
    
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
        """Override - components are already initialized in constructor"""
        if self._graph is not None:
            self.logger.log_components_already_initialized(self.role_name)
            return
        # Components already set up, just ensure graph is built
        if self._graph is None:
            self.logger.log_building_graph(self.role_name)
            self._init_graph()
    
    @property
    def system_prompt(self) -> str:
        """Get the system prompt for this role"""
        return self.role_config["system_prompt"]
    
    def get_role_info(self) -> Dict[str, Any]:
        """Get information about this agent's role"""
        return {
            "role_name": self.role_name,
            "system_prompt": self.system_prompt,
            "tools": [tool.name for tool in self._tools],
            "tool_count": len(self._tools),
            "metadata": self.role_config["metadata"]
        }
    
    def requires_human_review(self) -> bool:
        """Check if this role requires human review"""
        return self.role_config.get("human_review", False)
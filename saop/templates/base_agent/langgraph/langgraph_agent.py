# langgraph_agent.py
import asyncio
import copy
import logging
import os
from typing import Any, Dict, List, TypedDict, Optional

from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage, AIMessage
from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import MessagesState
from langchain_core.tools import BaseTool

from config.agent_config import load_env_config
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.langchain_chains import chains

from telemetry.langgraph_trace_utils import track_agent
from _mcp.tools import wrap_tools_with_telemetry

# Policy Engine Integration
from config.policy.policy_eng import policy_select_model, policy_filter_tools, get_policy_engine


logging.basicConfig(level=logging.INFO)
log = logging.getLogger("langgraph_agent")


class AgentState(MessagesState):
    """Using MessagesState ensures proper message handling"""
    pass


# class PolicyAwareLLM:
#     """Clean wrapper that handles all policy logic for model selection"""
    
#     def __init__(self, role_name: str, main_agent_config: Any):
#         self.role_name = role_name
#         # Store the main agent config which contains the default model settings
#         self.main_agent_config = main_agent_config
#         self.current_model_config = None
#         self._llm = None
    
#     def get_llm(self):
#         """Get LLM instance, switching models if policy requires"""
        
#         # 1. Get the default model configuration from the main agent's settings
#         default_model_config = self.main_agent_config.model
        
#         # 2. Apply policy to select the final model configuration
#         #    (This function should now return a dictionary)
#         selected_model_config = policy_select_model(self.role_name, default_model_config)
        
#         # 3. Only recreate the LLM if the configuration has changed
#         if self._llm is None or selected_model_config != self.current_model_config:
#             if self.current_model_config is not None:
#                 # Log the specific model name for clarity
#                 old_model = self.current_model_config.get('model', 'N/A')
#                 new_model = selected_model_config.get('model', 'N/A')
#                 log.info(f"Policy model switch for {self.role_name}: {old_model} -> {new_model}")

#             log.info(f"Initializing model with config: {selected_model_config}")
            
#             # 4. Unpack the entire config dictionary into init_chat_model.
#             #    Remove the explicit api_key. LangChain will find it in the environment.
#             self._llm = init_chat_model(**selected_model_config)
            
#             self.current_model_config = selected_model_config
        
#         return self._llm


class PolicyAwareLLM:
    """Clean wrapper that handles all policy logic for model selection"""
    
    def __init__(self, role_name: str, main_agent_config: Any):
        self.role_name = role_name
        self.main_agent_config = main_agent_config
        self.current_model_config = None
        self._llm = None
    
    def get_llm(self):
        """Get LLM instance, switching models if policy requires"""
        
        # 1. Get the default model configuration from the main agent's settings
        default_model_config = self.main_agent_config.model
        
        # DEBUG: Log what we're starting with
        log.info(f"=== MODEL SELECTION DEBUG for {self.role_name} ===")
        log.info(f"Default model config type: {type(default_model_config)}")
        log.info(f"Default model config value: {default_model_config}")
        
        # 2. Apply policy to select the final model configuration
        selected_model_config = policy_select_model(self.role_name, default_model_config)
        
        # DEBUG: Log what policy returned
        log.info(f"Policy returned type: {type(selected_model_config)}")
        log.info(f"Policy returned value: {selected_model_config}")
        
        # DEBUG: Check if it's the expected dictionary format
        if isinstance(selected_model_config, dict):
            log.info("✅ Policy returned dict - checking required keys...")
            required_keys = ['model', 'model_provider']
            missing_keys = [key for key in required_keys if key not in selected_model_config]
            if missing_keys:
                log.warning(f"❌ Missing required keys: {missing_keys}")
            else:
                log.info("✅ All required keys present")
        elif isinstance(selected_model_config, str):
            log.warning(f"❌ Policy returned string instead of dict: '{selected_model_config}'")
            log.warning("This will cause issues when unpacking with **selected_model_config")
            
            # Show what would happen if we try to unpack it
            try:
                test_unpack = init_chat_model(**selected_model_config)  # This will fail
            except Exception as e:
                log.error(f"❌ Unpacking string would fail: {e}")
        else:
            log.error(f"❌ Policy returned unexpected type: {type(selected_model_config)}")
        
        # DEBUG: Compare with current config
        if self.current_model_config is not None:
            log.info(f"Current model config: {self.current_model_config}")
            config_changed = selected_model_config != self.current_model_config
            log.info(f"Config changed: {config_changed}")
        else:
            log.info("No previous config - first initialization")
        
        # 3. Only recreate the LLM if the configuration has changed
        if self._llm is None or selected_model_config != self.current_model_config:
            if self.current_model_config is not None:
                log.info(f"Model config change detected - recreating LLM")
                
                # Try to log old vs new model names safely
                try:
                    if isinstance(self.current_model_config, dict):
                        old_model = self.current_model_config.get('model', 'unknown')
                    else:
                        old_model = str(self.current_model_config)
                        
                    if isinstance(selected_model_config, dict):
                        new_model = selected_model_config.get('model', 'unknown')
                    else:
                        new_model = str(selected_model_config)
                        
                    log.info(f"Policy model switch for {self.role_name}: {old_model} -> {new_model}")
                except Exception as e:
                    log.warning(f"Could not log model switch details: {e}")

            log.info(f"Initializing model with config: {selected_model_config}")
            
            # 4. Try to unpack the config - this is where it will fail if wrong type
            try:
                if isinstance(selected_model_config, dict):
                    log.info("✅ Attempting to unpack dict config...")
                    self._llm = init_chat_model(**selected_model_config)
                    log.info("✅ LLM created successfully")
                else:
                    log.error(f"❌ Cannot unpack non-dict config: {selected_model_config}")
                    log.error("Falling back to default model config...")
                    
                    # Fallback to default config
                    if isinstance(default_model_config, dict):
                        self._llm = init_chat_model(**default_model_config)
                        log.info(f"✅ Fallback LLM created with default config")
                    else:
                        # Last resort - create with minimal config
                        log.error("Default config also not dict - using minimal fallback")
                        self._llm = init_chat_model(
                            model="gpt-4o-mini",
                            model_provider="openai"
                        )
                        log.info("✅ Minimal fallback LLM created")
                        
            except Exception as e:
                log.error(f"❌ Failed to create LLM: {e}")
                log.error(f"Config that failed: {selected_model_config}")
                raise
            
            self.current_model_config = selected_model_config
        else:
            log.info("Model config unchanged - reusing existing LLM")
        
        log.info("=== END MODEL SELECTION DEBUG ===")
        return self._llm


class PolicyAwareTools:
    """Clean wrapper that handles all policy logic for tool filtering"""
    
    def __init__(self, role_name: str, env_config: dict):
        self.role_name = role_name
        self.env_config = env_config
        self._filtered_tools = None
        self._all_tools = None
    
    async def get_tools(self) -> List[BaseTool]:
        """Get policy-filtered tools for this role"""
        if self._filtered_tools is not None:
            return self._filtered_tools
        
        # Get all available tools first
        if self._all_tools is None:
            self._all_tools = await self._fetch_all_tools()
        
        # Apply policy filtering
        tool_names = [tool.name for tool in self._all_tools]
        allowed_tool_names = policy_filter_tools(self.role_name, tool_names)
        
        # Filter to allowed tools only
        self._filtered_tools = [
            tool for tool in self._all_tools 
            if tool.name in allowed_tool_names
        ]
        
        if len(self._filtered_tools) != len(self._all_tools):
            blocked_count = len(self._all_tools) - len(self._filtered_tools)
            log.info(f"Policy filtered tools for {self.role_name}: {blocked_count} tools blocked by compliance rules")
        
        return self._filtered_tools
    
    async def _fetch_all_tools(self) -> List[BaseTool]:
        """Fetch all available tools from MCP servers"""
        client_config = {
            "local_mcp": {"url": self.env_config["MCP_BASE_URL"], "transport": "streamable_http"},
            "github_mcp": {
                "url": self.env_config["MCP_GITHUB_BASE_URL"],
                "transport": "streamable_http",
                "headers": {
                    "Authorization": f"Bearer {self.env_config['GITHUB_PAT']}",
                    "X-MCP-Toolsets": "repos",
                },
            },
        }
        client = MultiServerMCPClient(client_config)
        tools = await client.get_tools()
        return wrap_tools_with_telemetry(tools)


class AgentComponents:
    def __init__(self, main_agent_config: Any, role_name: str = None): # ADJUSTMENT 1: Added main_agent_config
        self.env_config = load_env_config()
        self.role_name = self._determine_role_name(role_name)
        
        # ADJUSTMENT 2: Pass main_agent_config to PolicyAwareLLM
        self.policy_llm = PolicyAwareLLM(self.role_name, main_agent_config) 
        self.policy_tools = PolicyAwareTools(self.role_name, self.env_config)
    
    def _determine_role_name(self, role_name: str = None) -> str:
        """Determine role name from: 1) parameter, 2) policy override, 3) env var, 4) default"""
        
        # 1. If explicitly passed, use it
        if role_name:
            print("ROLE NAME FROM LG AGENT", role_name)
            return role_name
        
        # 2. Check if policy config specifies a role override
        try:
            from config.policy.policy_config import get_policy_config
            config = get_policy_config()
            
            # Check if policy specifies which role to use
            if hasattr(config, 'system') and hasattr(config.system, 'active_role'):
                policy_role = config.system.active_role
                log.info(f"Policy override: using role {policy_role}")
                return policy_role
                
        except Exception as e:
            log.debug(f"Could not get role override from policy: {e}")
        
        # 3. Use environment variable
        env_role = os.getenv("AGENT_NAME")
        log.info(f"Using role from environment: {env_role}")
        return env_role

    def create_llm(self):
        """Get policy-aware LLM"""
        return self.policy_llm.get_llm()

    async def create_tools(self) -> List[BaseTool]:
        """Get policy-filtered tools"""
        return await self.policy_tools.get_tools()


class AgentTemplate:
    def __init__(self, role_name: Optional[str] = None):
        self._graph = None
        self._llm = None
        self._tools = None
        self._chains = chains or {}
        self._llm_chain = None
        self._checkpointer = None
        
        # Get main agent configuration from policy, not expert roles
        self.main_agent_config = self._get_main_agent_config()
        self.role_name = self.main_agent_config.name
        self._components = None

    def _get_main_agent_config(self):
        """Get main agent configuration from policy YAML"""
        try:
            from config.policy.policy_config import get_policy_config
            config = get_policy_config()
            log.info(f"Using main agent config: {config.main_agent.name}")
            return config.main_agent
        except Exception as e:
            log.error(f"Could not get main agent config from policy: {e}")
            # Fallback to environment-based role determination
            env_role = os.getenv("AGENT_NAME", "general_support")
            log.warning(f"Falling back to environment role: {env_role}")
            
            # Create minimal config for fallback
            from types import SimpleNamespace
            return SimpleNamespace(
                name=env_role,
                system_prompt="You are a helpful assistant.",
                tools=[],
                tool_bundles=[]
            )

    async def _initialize_components(self):
        if self._graph is not None:
            return
        
        # Create components using main agent role, not expert role lookup
        self._components = AgentComponents(
            main_agent_config=self.main_agent_config, 
            role_name=self.role_name
        )

        
        self._llm = self._components.create_llm()
        self._tools = await self._components.create_tools()
        self._llm_chain = self._llm.bind_tools(self._tools)
        self._init_graph()
        
        log.info(f"Main agent '{self.role_name}' initialized with {len(self._tools)} tools")

    def _init_graph(self):
        tool_node = ToolNode(self._tools)
        builder = StateGraph(AgentState)

        builder.add_node("router", self._router_node)
        builder.add_node("call_model", self._call_model_node)
        builder.add_node("tools", tool_node)
        builder.add_node("handle_error", self._handle_error_node)

        builder.set_entry_point("router")
        builder.add_edge("router", "call_model")
        builder.add_conditional_edges(
            "call_model",
            self._should_continue,
            {
                "tools": "tools",
                "handle_error": "handle_error",
                END: END,
            },
        )
        builder.add_edge("tools", "call_model")
        builder.add_edge("handle_error", END)

        self._graph = builder.compile(checkpointer=self._checkpointer)

    @track_agent(node_name="_router_node", is_agent=True, agent_role="router")
    async def _router_node(self, state: AgentState, config: RunnableConfig = None) -> Dict[str, Any]:
        log.info("IN ROUTER NODE - Main Agent")
        # Main agent router - could add routing logic to expert roles here
        return {"messages": state["messages"]}

    @track_agent(node_name="_call_model_node", is_agent=True, agent_role="brain")
    async def _call_model_node(self, state: AgentState, config: RunnableConfig = None) -> Dict[str, Any]:
        log.info(f"IN CALL MODEL NODE - Main Agent: {self.role_name}")
        messages = state["messages"]
        
        # Refresh LLM (will switch models if policy changed)
        if self._components:
            self._llm = self._components.policy_llm.get_llm()
            self._llm_chain = self._llm.bind_tools(self._tools)
        
        # Debug: Log the message structure
        log.debug(f"Number of messages in state: {len(messages)}")
        for i, msg in enumerate(messages):
            msg_type = type(msg).__name__
            if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls'):
                log.debug(f"  [{i}] {msg_type} with tool_calls: {bool(msg.tool_calls)}")
            else:
                log.debug(f"  [{i}] {msg_type}")

        try:
            # Pass the entire message history to the LLM
            response = await self._llm_chain.ainvoke(messages)
            
            # Log tool calls if present
            if hasattr(response, 'tool_calls') and response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call['name']
                    tool_args = tool_call['args']

                    log.info(f"🤖 Main Agent ({self.role_name}) decided to use:")
                    log.info(f"🛠️ TOOL NAME:  **{tool_name}**")
                    log.info(f"🗣️ TOOL ARGUMENTS: {tool_args}") 
                    matching_tool = next((t for t in self._tools if t.name == tool_name), None)
                    if matching_tool:
                        log.info(f"📖 TOOL DESCRIPTION: {matching_tool.description}")

            else:
                log.info(f"Main Agent ({self.role_name}) responding directly without tools.")
            
            print("---------------------------------------------")
            log.info(messages)
            log.info([response])
            print("---------------------------------------------")
            return {"messages": messages + [response]}

        except Exception as e:
            log.exception(f"Error in main agent ({self.role_name}) model call: %s", e)
            # Create an error message
            error_msg = AIMessage(content=f"I encountered an error: {str(e)}. Please try again.")
            return {"messages": [error_msg], "error": True}

    def _should_continue(self, state: AgentState) -> str:
        log.info("IN SHOULD CONTINUE - Main Agent")
        messages = state["messages"]
        last = messages[-1]
        
        # Check if there was an error flag set
        if state.get("error"):
            log.info("Error flag detected, routing to error handler")
            return "handle_error"

        # If the last message is from the AI and it has tool_calls,
        # we should transition to the 'tools' node to execute the tool
        if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            log.info("AI message has tool calls, routing to tools")
            return "tools"

        # Otherwise, we're done (either a final response or after tool execution)
        log.info("Conversation complete, ending")
        return END

    @track_agent(node_name="_handle_error_node", is_agent=False)
    async def _handle_error_node(self, state: AgentState, config: RunnableConfig = None) -> Dict[str, Any]:
        log.info(f"IN HANDLE ERROR NODE - Main Agent: {self.role_name}")
        error_msg = HumanMessage(
            content="An unexpected error occurred. Please try again or rephrase your request."
        )
        return {"messages": [error_msg]}

    async def ainvoke(self, input_message: str, config: Dict[str, Any] = {}) -> Dict[str, Any]:
        """Main agent invocation - handles the primary conversation flow"""
        log.info(f"Main agent ({self.role_name}) processing request")
        
        await self._initialize_components()
        final_state = await self._graph.ainvoke(
            {"messages": [HumanMessage(content=input_message)]}, config
        )
        
        # Extract result from final state
        try:
            if final_state and "messages" in final_state and final_state["messages"]:
                messages: List[BaseMessage] = final_state["messages"]
                
                # Search backwards for the last AIMessage
                last_ai_message = next((msg for msg in reversed(messages) if isinstance(msg, AIMessage)), None)

                if last_ai_message:
                    output_content = last_ai_message.content
                    final_output = {"result": output_content}
                else:
                    log.error("No AIMessage found in the final state messages.")
                    final_output = {"result": "No AI response was generated."}
            else:
                log.error("Graph execution finished with an empty or invalid final state.")
                final_output = {"result": "I was unable to process your request."}
                
        except Exception as e:
            log.error(f"Unexpected error in result extraction: {e}")
            final_output = {"result": f"Error extracting result: {str(e)}"}
    
        log.info(f"Main agent ({self.role_name}) completed processing")
        print(f"--- MAIN AGENT ({self.role_name.upper()}) OUTPUT ---")
        print(f"{final_output}")
        print("-" * (len(self.role_name) + 25))
        
        return final_output
    
    def get_state(self) -> Dict[str, Any]:
        """Get current state of the main agent"""
        return {
            "role_name": self.role_name,
            "is_main_agent": True,
            "tools_count": len(self._tools) if self._tools else 0,
            "config_source": "policy_main_agent"
        }
    
    def get_main_agent_info(self) -> Dict[str, Any]:
        """Get information about the main agent configuration"""
        return {
            "name": self.main_agent_config.name,
            "system_prompt": getattr(self.main_agent_config, 'system_prompt', ''),
            "tools": getattr(self.main_agent_config, 'tools', []),
            "tool_bundles": getattr(self.main_agent_config, 'tool_bundles', []),
            "human_review": getattr(self.main_agent_config, 'human_review', False),
            "metadata": getattr(self.main_agent_config, 'metadata', {})
        }


def policy_select_model(role_name: str, current_model: Any) -> Any:
    """
    Integration point for langchain_chains.py
    Select model based on policy rules.
    """
    log.info(f"=== POLICY SELECT MODEL DEBUG ===")
    log.info(f"Input role_name: {role_name}")
    log.info(f"Input current_model type: {type(current_model)}")
    log.info(f"Input current_model value: {current_model}")
    
    engine = get_policy_engine()
    result = engine.select_model(role_name, current_model)
    
    log.info(f"Policy engine returned type: {type(result)}")
    log.info(f"Policy engine returned value: {result}")
    log.info(f"=== END POLICY SELECT MODEL DEBUG ===")
    
    return result
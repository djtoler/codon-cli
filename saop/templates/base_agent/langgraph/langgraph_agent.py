
# langgraph_agent.py
import asyncio
import copy
import logging
from typing import Any, Dict, List, TypedDict

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

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("langgraph_agent")


class AgentState(MessagesState):
    """Using MessagesState ensures proper message handling"""
    pass

class AgentComponents:
    def __init__(self):
        self.env_config = load_env_config()

    def create_llm(self):
        return init_chat_model(
            model=self.env_config["MODEL_NAME"],
            openai_api_key=self.env_config["MODEL_API_KEY"],
            model_provider=self.env_config["MODEL_PROVIDER"],
        )

    async def create_tools(self) -> List[BaseTool]:
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
        # print(tools)
        
        return wrap_tools_with_telemetry(tools)


class AgentTemplate:
    def __init__(self):
        self._graph = None
        self._llm = None
        self._tools = None
        self._chains = chains or {}
        self._llm_chain = None
        self._checkpointer = None

    async def _initialize_components(self):
        if self._graph is not None:
            return
        components = AgentComponents()
        self._llm = components.create_llm()
        self._tools = await components.create_tools()
        self._llm_chain = self._llm.bind_tools(self._tools)
        self._init_graph()

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
        log.info("IN ROUTER NODE")
        # Just pass through the state without modification
        return {"messages": state["messages"]}

    @track_agent(node_name="_call_model_node", is_agent=True, agent_role="brain")
    async def _call_model_node(self, state: AgentState, config: RunnableConfig = None) -> Dict[str, Any]:
        log.info("IN CALL MODEL NODE")
        messages = state["messages"]
        
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

                    log.info(f"🤖 Agent decided to use:")
                    log.info(f"🛠️ TOOL NAME:  **{tool_name}**")
                    log.info(f"🗣️ TOOL ARGUMENTS: {tool_args}") 
                    matching_tool = next((t for t in self._tools if t.name == tool_name), None)
                    if matching_tool:
                        log.info(f"📖 TOOL DESCRIPTION: {matching_tool.description}")

            else:
                log.info("Agent decided not to use a tool and will respond directly. 🗣️")
            print("---------------------------------------------")
            log.info(messages)
            log.info([response])
            print("---------------------------------------------")
            return {"messages": messages + [response]}

        except Exception as e:
            log.exception("Error calling LLM: %s", e)
            # Create an error message
            error_msg = AIMessage(content=f"I encountered an error: {str(e)}. Please try again.")
            return {"messages": [error_msg], "error": True}

    def _should_continue(self, state: AgentState) -> str:
        log.info("IN SHOULD CONTINUE")
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
        log.info("IN HANDLE ERROR NODE")
        error_msg = HumanMessage(
            content="An unexpected error occurred. Please try again or rephrase your request."
        )
        return {"messages": [error_msg]}

    # In langgraph_agent.py -> AgentTemplate

    # In langgraph_agent.py -> AgentTemplate

# In langgraph_agent.py -> AgentTemplate

    async def ainvoke(self, input_message: str, config: Dict[str, Any] = {}) -> Dict[str, Any]:
        # This part of the function remains the same
        await self._initialize_components()
        final_state = await self._graph.ainvoke(
            {"messages": [HumanMessage(content=input_message)]}, config
        )
        
        # --- Corrected result extraction logic ---
        try:
            if final_state and "messages" in final_state and final_state["messages"]:
                messages: List[BaseMessage] = final_state["messages"]
                print("RESULT*****: ", messages)
                
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
    
        print(f"--- FINAL AGENT OUTPUT --- \n{final_output}\n--------------------------")
        return final_output
    
    def get_state(self) -> Dict[str, Any]:
        return {}

















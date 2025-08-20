import asyncio
import os
from typing import Any, Dict, List
from dotenv import load_dotenv

# LangChain and LangGraph imports
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import MessagesState

# Import the custom configuration loader
from agent_config import load_env_config
# Import the new MultiServerMCPClient from the correct library
from langchain_mcp_adapters.client import MultiServerMCPClient

# Load environment configuration from your file
env_config = load_env_config()

# --- Initialize the Model and Client ---
model = init_chat_model(env_config["MODEL_NAME"],
                        openai_api_key=env_config["MODEL_API_KEY"],
                        model_provider=env_config["MODEL_PROVIDER"])


# --- Main Execution Function ---
async def main():
    """
    Sets up the LangGraph agent, loads tools from the MCP server,
    and runs a conversational query to test a tool call.
    """
    print("🚀 Setting up LangGraph agent with MCP tools...")

    # Set up the MultiServerMCPClient
    client_config = {
        "mcp_server": {
            "url": env_config["MCP_BASE_URL"],
            "transport": "streamable_http"
        }
    }

    client = MultiServerMCPClient(client_config)

    # Note: `get_tools()` is an async method and must be awaited.
    tools = await client.get_tools()
    print(f"✅ Discovered the following tools: {[tool.name for tool in tools]}")
    
    model_with_tools = model.bind_tools(tools)

    tool_node = ToolNode(tools)

    # --- Define Graph Nodes and Edges ---

    # Make the node function async and await the model call
    async def call_model(state: MessagesState) -> Dict[str, List[BaseMessage]]:
        messages = state["messages"]
        response = await model_with_tools.ainvoke(messages)
        return {"messages": [response]}

    def should_continue(state: MessagesState) -> str:
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools"
        return END

    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    builder.add_node("tools", tool_node)

    builder.add_edge(START, "call_model")
    builder.add_conditional_edges(
        "call_model",
        should_continue,
        {"tools": "tools", END: END}
    )
    builder.add_edge("tools", "call_model")

    graph = builder.compile()

    # --- Test the Graph ---

    # Use ainvoke and await the result
    greet_query = {"messages": [HumanMessage(content="Say hi to my friend Tim.")]}
    print("\n▶️ Invoking agent to test the 'greet' tool...")
    response = await graph.ainvoke(greet_query)
    print(f"✅ Final agent response: {response['messages'][-1].content}")

    # Use ainvoke and await the result
    simple_query = {"messages": [HumanMessage(content="What's your name?")]}
    print("\n▶️ Invoking agent for a simple query...")
    response = await graph.ainvoke(simple_query)
    print(f"✅ Final agent response: {response['messages'][-1].content}")


if __name__ == "__main__":
    asyncio.run(main())

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

    # Configure the MultiServerMCPClient to connect to both local and remote servers
    client_config = {
        "local_mcp": {
            "url": env_config["MCP_BASE_URL"],
            "transport": "streamable_http"
        },
        "github_mcp": {
            "url": env_config["MCP_GITHUB_BASE_URL"],
            "transport": "streamable_http",
            "headers": {
                "Authorization": f"Bearer {env_config['GITHUB_PAT']}",
                "X-MCP-Toolsets": "repos"
            }
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

    # --- Test the Graph with the new GitHub tool ---
    
    # Test a query that requires a GitHub tool
    github_query = {"messages": [HumanMessage(content="Name a couple of the toolsets available in the remote-server.md file at the github/github-mcp-server/docs repository?")]}
    print("\n▶️ Invoking agent to test the 'get_file_contents' tool...")
    response = await graph.ainvoke(github_query)
    print(f"✅ Final agent response: {response['messages'][-1].content}")

    # You can also keep your other tests to verify they still work
    greet_query = {"messages": [HumanMessage(content="Say hi to my friend Tim.")]}
    print("\n▶️ Invoking agent to test the 'greet' tool...")
    response = await graph.ainvoke(greet_query)
    print(f"✅ Final agent response: {response['messages'][-1].content}")

    # Search GitHub file
    greet_query = {"messages": [HumanMessage(content="Search a github file to find the following string.")]}
    print("\n▶️ Invoking agent to test the 'GitHub' toolset...")
    response = await graph.ainvoke(greet_query)
    print(f"✅ Final agent response: {response['messages'][-1].content}")


if __name__ == "__main__":
    asyncio.run(main())
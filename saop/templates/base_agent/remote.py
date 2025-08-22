


# import asyncio
# from fastmcp import Client
# from fastmcp.client.transports import StreamableHttpTransport
# import json

# # IMPORTANT: Hard-coding your PAT is a security risk.
# # This is for temporary local testing only.
# # Replace 'YOUR_HARDCODED_PAT_HERE' with your actual GitHub PAT.
# GITHUB_PAT = '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'

# # Use the base URL for the all-inclusive server
# GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"

# async def main():
#     if GITHUB_PAT == 'YOUR_HARDCODED_PAT_HERE':
#         print("Error: Please replace 'YOUR_HARDCODED_PAT_HERE' with your actual GitHub PAT.")
#         return

#     headers = {
#         "Authorization": f"Bearer {GITHUB_PAT}",
#         "X-MCP-Toolsets": "repos"
#     }

#     transport = StreamableHttpTransport(
#         url=GITHUB_MCP_URL,
#         headers=headers
#     )

#     client = Client(transport)
#     print("Client configured with the 'repos' toolset. 🎯")

#     try:
#         async with client:
#             print("Successfully connected to the remote GitHub MCP Server. ✨")
            
#             file_params = {
#                 "owner": "golang",
#                 "repo": "go",
#                 "path": "README.md"
#             }
            
#             print(f"\nRetrieving file contents for {file_params['owner']}/{file_params['repo']}/{file_params['path']}...")
            
#             file_result = await client.call_tool("get_file_contents", file_params)
            
#             if file_result.is_error:
#                 print(f"Error retrieving file: {file_result.content}")
#             else:
#                 # Correctly access the file content from the EmbeddedResource
#                 file_content = file_result.content[1].resource.text
                
#                 # Normalize the content to handle line breaks and other whitespace
#                 normalized_content = ' '.join(file_content.split())
                
#                 # Your exact search query
#                 query_string = "that makes it easy to build simple, reliable, and efficient software."
                
#                 if query_string in normalized_content:
#                     print(f"✅ Success! Found the phrase in {file_params['path']}.")
#                     print("\n--- Snippet of the content ---")
#                     # Find the start of the phrase to print a context snippet
#                     start_index = normalized_content.find(query_string)
#                     snippet_start = max(0, start_index - 50)
#                     snippet_end = min(len(normalized_content), start_index + len(query_string) + 50)
#                     print(normalized_content[snippet_start:snippet_end].strip())
#                     print("--- End of snippet ---")
#                 else:
#                     print(f"❌ The phrase was not found in {file_content}.")

#     except Exception as e:
#         print(f"An unexpected error occurred: {e}")

# if __name__ == "__main__":
#     asyncio.run(main())
















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
            "url": env_config["LOCAL_MCP_BASE_URL"],
            "transport": "streamable_http"
        },
        "github_mcp": {
            "url": env_config["GITHUB_MCP_BASE_URL"],
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

    # --- Test Cases ---

    # Test a query that requires the GitHub tool
    github_query = {"messages": [HumanMessage(content="What are the contents of the README.md file in the golang/go repository?")]}
    print("\n▶️ Invoking agent to test the 'get_file_contents' tool...")
    response = await graph.ainvoke(github_query)
    # The response will contain the content of the file
    print(f"✅ Final agent response: {response['messages'][-1].content}")

    # Test your other tools to verify they still work
    greet_query = {"messages": [HumanMessage(content="Say hi to my friend Tim.")]}
    print("\n▶️ Invoking agent to test the 'greet' tool...")
    response = await graph.ainvoke(greet_query)
    print(f"✅ Final agent response: {response['messages'][-1].content}")

    # Test another simple query
    simple_query = {"messages": [HumanMessage(content="What's your name?")]}
    print("\n▶️ Invoking agent for a simple query...")
    response = await graph.ainvoke(simple_query)
    print(f"✅ Final agent response: {response['messages'][-1].content}")


if __name__ == "__main__":
    asyncio.run(main())
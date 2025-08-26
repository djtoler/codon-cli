# import asyncio
# import uvicorn

# from a2a.server.apps.jsonrpc import A2AStarletteApplication
# from a2a.server.request_handlers import DefaultRequestHandler
# from a2a.types import AgentCard, AgentCapabilities, AgentSkill
# from a2a.server.tasks import InMemoryTaskStore

# from langgraph_executor import LangGraphA2AExecutor
# from langgraph_tool_wrapper import create_agent


# async def main():
#     print("🚀 Setting up LangGraph agent with MCP tools...")

#     # 1. Instantiate the A2A Executor
#     # This assumes LangGraphA2AExecutor's constructor takes an EventQueue.
#     # The LangGraph object will be created inside the executor's `initialize` method.
#     executor = LangGraphA2AExecutor(event_queue=None) # Pass a valid EventQueue instance if needed

#     # 2. Asynchronously initialize the executor and its LangGraph agent
#     await executor.initialize()
    
#     # 3. Define the Agent Card
#     agent_card = AgentCard(
#         name="LangGraph MCP Agent",
#         description="An agent powered by LangGraph that uses MCP tools to interact with various services.",
#         url="http://localhost:9999/",
#         version="1.0.0",
#         defaultInputModes=["text"],
#         defaultOutputModes=["text"],
#         capabilities=AgentCapabilities(streaming=True),
#         skills=[
#             AgentSkill(
#                 id="query-github-repo",
#                 name="Query GitHub Repository",
#                 description="Accesses GitHub repositories to retrieve file contents.",
#                 tags=["github", "repository"]
#             ),
#             AgentSkill(
#                 id="greet",
#                 name="Greet Friend",
#                 description="Greets a friend by name.",
#                 tags=["social"]
#             ),
#         ]
#     )

#     # 4. Instantiate the Request Handler
#     request_handler = DefaultRequestHandler(
#         agent_executor=executor,
#         task_store=InMemoryTaskStore()
#     )

#     # 5. Create the Starlette application
#     starlette_app = A2AStarletteApplication(
#         agent_card=agent_card,
#         http_handler=request_handler
#     )

#     # Debug: Let's see what attributes this object has
#     print("\n🔍 Debugging A2AStarletteApplication attributes:")
#     print("Available attributes and methods:")
#     for attr in dir(starlette_app):
#         if not attr.startswith('_'):
#             print(f"  - {attr}")
    
#     # Try to find the actual ASGI app
#     actual_app = None
    
#     # Common attribute names for the underlying app
#     possible_attrs = ['app', 'application', 'asgi', 'asgi_app', 'starlette_app', '_app']
    
#     for attr in possible_attrs:
#         if hasattr(starlette_app, attr):
#             actual_app = getattr(starlette_app, attr)
#             print(f"\n✅ Found underlying app as '{attr}' attribute")
#             break
    
#     # If we didn't find it, check if it's a Starlette instance itself
#     if actual_app is None:
#         from starlette.applications import Starlette
#         if isinstance(starlette_app, Starlette):
#             actual_app = starlette_app
#             print("\n✅ A2AStarletteApplication is a Starlette instance")
#         else:
#             print("\n⚠️ Could not determine the ASGI app. Trying to use A2AStarletteApplication directly...")
#             actual_app = starlette_app

#     # 6. Run the server using uvicorn
    
#     # Build the underlying ASGI app
#     asgi_app = starlette_app.build()

#     # 7. Run the server using uvicorn
#     config = uvicorn.Config(asgi_app, host="0.0.0.0", port=9999)

#     server = uvicorn.Server(config)
#     print("\n✅ A2A Server ready. Listening on http://localhost:9999")
#     print("Access the agent card at http://localhost:9999/.well-known/agent.json")
#     await server.serve()

# if __name__ == "__main__":
#     asyncio.run(main())












import asyncio
import uvicorn
import yaml
from pydantic import ValidationError

from a2a.server.apps.jsonrpc import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.types import AgentCard
from a2a.server.tasks import InMemoryTaskStore

from langgraph_executor import LangGraphA2AExecutor
from langgraph_tool_wrapper import create_agent


def create_agent_card_from_yaml_file(file_path: str) -> AgentCard:
    """
    Reads a YAML file, parses it, and converts it into a Pydantic AgentCard model.
    """
    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        # Validate and convert the data using the Pydantic model
        print("AGENT CARD: ", AgentCard(**data))
        return AgentCard(**data)
    except FileNotFoundError:
        print(f"❌ Error: The file '{file_path}' was not found.")
        raise
    except ValidationError as e:
        print(f"❌ Pydantic validation failed for AgentCard: {e}")
        raise
    except yaml.YAMLError as e:
        print(f"❌ YAML parsing failed: {e}")
        raise


async def main():
    print("🚀 Setting up LangGraph agent with MCP tools...")

    # 1. Instantiate the A2A Executor
    executor = LangGraphA2AExecutor(event_queue=None)

    # 2. Asynchronously initialize the executor and its LangGraph agent
    await executor.initialize()
    
    # 3. Create the Agent Card from the external YAML file
    # Make sure 'agent_card.yaml' is in the same directory as this script
    agent_card = create_agent_card_from_yaml_file('a2a_agent_card.yaml')
    
    # Optional: Print the loaded AgentCard to verify it worked
    print("\n✅ Agent Card loaded successfully from YAML:")
    print(agent_card.model_dump_json(indent=2))

    # 4. Instantiate the Request Handler
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore()
    )

    # 5. Create the Starlette application
    starlette_app = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler
    )

    # Debug: Let's see what attributes this object has
    print("\n🔍 Debugging A2AStarletteApplication attributes:")
    print("Available attributes and methods:")
    for attr in dir(starlette_app):
        if not attr.startswith('_'):
            print(f"  - {attr}")
    
    # Try to find the actual ASGI app
    actual_app = None
    
    # Common attribute names for the underlying app
    possible_attrs = ['app', 'application', 'asgi', 'asgi_app', 'starlette_app', '_app']
    
    for attr in possible_attrs:
        if hasattr(starlette_app, attr):
            actual_app = getattr(starlette_app, attr)
            print(f"\n✅ Found underlying app as '{attr}' attribute")
            break
    
    # If we didn't find it, check if it's a Starlette instance itself
    if actual_app is None:
        from starlette.applications import Starlette
        if isinstance(starlette_app, Starlette):
            actual_app = starlette_app
            print("\n✅ A2AStarletteApplication is a Starlette instance")
        else:
            print("\n⚠️ Could not determine the ASGI app. Trying to use A2AStarletteApplication directly...")
            actual_app = starlette_app

    # 6. Run the server using uvicorn
    
    # Build the underlying ASGI app
    asgi_app = starlette_app.build()

    # 7. Run the server using uvicorn
    config = uvicorn.Config(asgi_app, host="0.0.0.0", port=9999)

    server = uvicorn.Server(config)
    print("\n✅ A2A Server ready. Listening on http://localhost:9999")
    print("Access the agent card at http://localhost:9999/.well-known/agent.json")
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())


import asyncio
import uvicorn
import yaml
from pydantic import ValidationError

from a2a.server.apps.jsonrpc import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.types import AgentCard
from a2a.server.tasks import InMemoryTaskStore

from langgraph_executor import LangGraphA2AExecutor

def create_agent_card_from_yaml_file(file_path: str) -> AgentCard:
    """
    Reads a YAML file, parses it, and converts it into a Pydantic AgentCard model.
    """
    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
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

    # 6. Build the underlying ASGI app
    asgi_app = starlette_app.build()

    # 7. Run the server using uvicorn
    config = uvicorn.Config(asgi_app, host="0.0.0.0", port=9999)
    server = uvicorn.Server(config)
    print("\n✅ A2A Server ready. Listening on http://localhost:9999")
    print("Access the agent card at http://localhost:9999/.well-known/agent.json")
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
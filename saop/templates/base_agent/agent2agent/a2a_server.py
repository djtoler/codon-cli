# agent2agent/a2a_server.py
"""
Clean A2A server with environment-based configuration.
"""
import asyncio
import uvicorn
from a2a.server.apps.jsonrpc import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from langgraph.langgraph_executor import LangGraphA2AExecutor
from banner import start_saop_baner

from .a2a_utils import create_agent_card_from_yaml_file
from config.agent_config import load_env_config

# Optional security import
try:
    from api.wrapper import wrap_a2a_with_security
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False

class A2AServer:
    """A2A server with configurable security and observability."""
    
    def __init__(self):
        self.config = load_env_config()
        self.executor = None
        self.app = None
    
    async def initialize(self):
        # Initialize LangGraph executor
        print("🚀 Setting up LangGraph agent with MCP tools...")

        self.executor = LangGraphA2AExecutor()
        await self.executor.initialize()
        
        # Create A2A application
        agent_card = create_agent_card_from_yaml_file('a2a_agent_card.yaml')
        request_handler = DefaultRequestHandler(
            agent_executor=self.executor,
            task_store=InMemoryTaskStore()
        )
        
        starlette_app = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler
        )
        
        # Build ASGI pipeline
        asgi_app = starlette_app.build()
        
        # Apply security wrapper if available
        if SECURITY_AVAILABLE:
            asgi_app = wrap_a2a_with_security(
                a2a_asgi_app=asgi_app,
                config=self.config,  # Pass config explicitly
                title=self.config.get("AGENT_NAME", "SAOP Agent"),
                version=self.config.get("AGENT_VERSION", "1.0.0")
            )
            print("🔐 FastAPI security wrapper enabled")
        else:
            print("⚠️  Security wrapper not available - running without authentication")
        
        # Apply observability
        self.app = OpenTelemetryMiddleware(asgi_app)
        print("📊 OpenTelemetry middleware enabled")
    
    async def serve(self):
        if not self.app:
            raise RuntimeError("Server not initialized. Call initialize() first.")
        
        host = self.config.get("A2A_HOST")
        port = self.config["A2A_PORT"]
        
        config = uvicorn.Config(
            self.app, 
            host=host, 
            port=port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        print(f"\n✅ A2A Server ready at http://{host}:{port}")
        
        if SECURITY_AVAILABLE:
            print(f"🔑 Authentication endpoint: http://{host}:{port}/auth/token")
            print(f"📋 API documentation: http://{host}:{port}/docs")
            print(f"🩺 Health check: http://{host}:{port}/health")
        
        print(f"🤖 Agent card: http://{host}:{port}/.well-known/agent-card.json")
        print(f"🔭 Observability: {self.config.get('OTEL_EXPORTER_OTLP_ENDPOINT')}")
        
        start_saop_baner()
        
        await server.serve()

async def main():
    server = A2AServer()
    await server.initialize()
    await server.serve()


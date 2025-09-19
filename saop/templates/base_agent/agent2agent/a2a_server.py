# agent2agent/a2a_server.py - Simplified server
"""
Clean A2A server with dynamic agent card generation from roles.
"""
import asyncio
import uvicorn
from a2a.server.apps.jsonrpc import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from langgraph.langgraph_executor import LangGraphA2AExecutor
from banner import start_saop_baner
from agent2agent.a2a_card_generator import generate_agent_card_for_executor
from config.agent_config import load_env_config


# Optional security import
try:
    from api.wrapper import wrap_a2a_with_security
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False


# Updated A2AServer
class A2AServer:
    """A2A server with centralized role configuration."""
    
    def __init__(self):
        self.config = load_env_config()
        self.role_name = None  # Will be determined from policy
        self.executor = None
        self.app = None
        
    async def initialize(self):
        """Initialize server with role from policy configuration"""
        
        # Get role from centralized policy configuration
        try:
            from config.policy.policy_eng import get_main_agent_role_name
            self.role_name = get_main_agent_role_name()
            print(f"🚀 Setting up LangGraph agent for role: {self.role_name}")
        except Exception as e:
            print(f"❌ Failed to determine main agent role: {e}")
            print("💡 Configure main_agent.name in policy YAML or set AGENT_NAME environment variable")
            raise
        
        # Pass role to executor (it will use the same policy logic)
        self.executor = LangGraphA2AExecutor()  # No role_name needed - uses policy
        success = await self.executor.initialize()
        
        if not success:
            print(f"⚠️ Server starting in degraded mode: {self.executor.get_initialization_error()}")
            print("🔧 Fix the role configuration and restart for full functionality")
        
        print(f"🎭 Using role: {self.executor.role_name}")  # Show what role was determined
        
        # Generate dynamic agent card - automatically detects main agent vs expert role
        agent_card = generate_agent_card_for_executor(self.executor)
        
        # Create A2A application
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
                config=self.config,
                title=self.config.get("AGENT_NAME", f"SAOP Agent ({self.executor.role_name})"),
                version=self.config.get("AGENT_VERSION", "1.0.0")
            )
            print("🔐 FastAPI security wrapper enabled")
        else:
            print("⚠️ Security wrapper not available - running without authentication")
        
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
        
        # Enhanced startup messaging
        print(f"\n✅ A2A Server ready at http://{host}:{port}")
        print(f"🎭 Role: {self.executor.role_name}")
        print(f"🚥 Status: {'Degraded Mode' if self.executor.is_degraded() else 'Full Functionality'}")
        
        if SECURITY_AVAILABLE:
            print(f"🔑 Authentication endpoint: http://{host}:{port}/auth/token")
            print(f"📋 API documentation: http://{host}:{port}/docs")
        
        print(f"🩺 Health check: http://{host}:{port}/health")
        print(f"🤖 Agent card: http://{host}:{port}/.well-known/agent-card.json")
        print(f"🔭 Observability: {self.config.get('OTEL_EXPORTER_OTLP_ENDPOINT')}")
        
        start_saop_baner()
        await server.serve()


async def main():
    """Main entry point - no role parameter needed."""
    server = A2AServer()
    await server.initialize()
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
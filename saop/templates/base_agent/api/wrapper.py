# api/wrapper.py
"""
Security wrapper for A2A applications.
Provides enterprise-grade authentication around existing A2A servers.
"""
import logging
import os
from typing import Optional, List
from fastapi import FastAPI
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from config.agent_config import load_env_config, EnvironmentConfig

from api.routes import router as auth_router
from api.middleware import A2AAuthContextMiddleware

logger = logging.getLogger(__name__)





class A2ASecurityWrapper:
    """
    Enterprise security wrapper for A2A applications.
    Wraps existing A2A ASGI apps with FastAPI authentication while
    preserving all original A2A functionality and endpoints.
    Includes JWT principal injection into A2A RequestContext.
    """
    
    def __init__(
        self,
        a2a_asgi_app,
        config: Optional[EnvironmentConfig] = None,
        title: Optional[str] = None,
        version: Optional[str] = None,
        enable_cors: bool = True,
        cors_origins: Optional[List[str]] = None
    ):
        # Load configuration if not provided
        self.config = config or load_env_config()
        
        # Use config values with fallbacks to parameters
        self.title = title or self.config.get('AGENT_NAME', 'SAOP Agent')
        self.version = version or self.config.get('AGENT_VERSION', '1.0.0')
        self.a2a_app = a2a_asgi_app
        
        # Parse CORS origins from config if not provided
        if cors_origins is None:
            cors_env = os.getenv("CORS_ORIGINS", "")
            cors_origins = [origin.strip() for origin in cors_env.split(",") if origin.strip()]
        
        self.fastapi_app = self._create_secured_app(enable_cors, cors_origins)
        logger.info(f"Security wrapper initialized for {self.title} v{self.version}")

    def _create_secured_app(self, enable_cors: bool, cors_origins: Optional[List[str]]) -> FastAPI:
        """Create FastAPI wrapper with authentication and security middleware"""
        
        app = FastAPI(
            title=self.title,
            version=self.version,
            description=f"Enterprise SAOP agent with OAuth2 + API Key authentication",
            docs_url="/docs",
            redoc_url="/redoc",
            openapi_url="/openapi.json"
        )

        from api.routes import create_main_api_router
        main_api_router = create_main_api_router()
        app.include_router(main_api_router)
        logger.info("SSE streaming endpoints enabled at /api/v1/streaming")

        # Add CORS middleware if enabled
        if enable_cors:
            # Use configured origins or fallback to defaults
            allowed_origins = cors_origins or [
                "http://localhost:3000",  # React dev
                "http://localhost:8080",  # Vue dev  
                "http://localhost:5173",  # Vite dev
                "https://yourdomain.com"  # Production fallback
            ]
            
            app.add_middleware(
                CORSMiddleware,
                allow_origins=allowed_origins,
                allow_credentials=True,
                allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                allow_headers=["*"],
            )
            logger.info(f"CORS enabled for origins: {allowed_origins}")

        # Add A2A authentication context middleware
        app.add_middleware(A2AAuthContextMiddleware)
        logger.info("A2A authentication context injection enabled")

        # Add authentication routes with configured endpoint
        # Extract base prefix (e.g., "auth" from "auth/token")
        token_endpoint = self.config.get('TOKEN_ENDPOINT', 'auth/token')
        if '/' in token_endpoint:
            auth_prefix = f"/{token_endpoint.split('/')[0]}"
        else:
            auth_prefix = f"/{token_endpoint.lstrip('/')}"
        
        app.include_router(auth_router, prefix=auth_prefix, tags=["authentication"])

        # Health check endpoint at root level
        @app.get("/health")
        async def health_check():
            """Service health check endpoint"""
            return {
                "status": "healthy",
                "service": self.title,
                "version": self.version,
                "authentication": "enabled",
                "a2a_auth_injection": "enabled",
                "agent_name": self.config.get('AGENT_NAME'),
                "model_provider": self.config.get('MODEL_PROVIDER'),
                "a2a_port": self.config.get('A2A_PORT'),
                "mcp_enabled": bool(self.config.get('MCP_BASE_URL')),
                "config_loaded": True
            }

        # A2A info endpoint
        @app.get("/.well-known/agent-card.json")
        async def agent_card():
            """A2A agent card endpoint"""
            return {
                "name": self.title,
                "version": self.version,
                "description": f"Enterprise SAOP agent with security wrapper",
                "capabilities": [
                    "authentication",
                    "authorization", 
                    "a2a_auth_context",
                    "mcp_integration",
                    "observability"
                ],
                "endpoints": {
                    "health": "/health",
                    "auth": auth_prefix,
                    "docs": "/docs",
                    "a2a_host": self.config.get('A2A_HOST', '0.0.0.0'),
                    "a2a_port": self.config.get('A2A_PORT', 9999)
                },
                "security": {
                    "jwt_issuer": self.config.get('JWT_ISSUER'),
                    "jwt_audience": self.config.get('JWT_AUDIENCE'),
                    "api_key_header": self.config.get('API_KEY_HEADER'),
                    "a2a_auth_required": True,
                    "principal_injection": "enabled"
                }
            }

        # Mount the A2A app at root to preserve all existing endpoints
        # This should be last to avoid conflicts with FastAPI routes
        app.mount("/", self.a2a_app)
        
        logger.info("FastAPI security wrapper configured successfully")
        logger.info(f"Authentication endpoint: {auth_prefix}")
        logger.info(f"A2A authentication context injection: enabled")
        logger.info(f"A2A host: {self.config.get('A2A_HOST')}:{self.config.get('A2A_PORT')}")
        logger.info(f"MCP endpoint: {self.config.get('MCP_BASE_URL')}")
        
        return app

    def get_asgi_app(self):
        """Get the secured ASGI application"""
        return self.fastapi_app

    def get_config(self) -> EnvironmentConfig:
        """Get the loaded configuration"""
        return self.config


def wrap_a2a_with_security(
    a2a_asgi_app,
    config: Optional[EnvironmentConfig] = None,
    title: Optional[str] = None,
    version: Optional[str] = None,
    enable_cors: bool = True,
    cors_origins: Optional[List[str]] = None
) -> FastAPI:
    """
    Convenience function to wrap A2A ASGI app with enterprise security.
    
    Args:
        a2a_asgi_app: The A2A ASGI application to secure
        config: Environment configuration object (will load from env if None)
        title: Service title for API documentation (uses AGENT_NAME from config if None)
        version: Service version (uses AGENT_VERSION from config if None)
        enable_cors: Whether to enable CORS middleware
        cors_origins: List of allowed CORS origins (uses CORS_ORIGINS from config if None)
        
    Returns:
        Secured FastAPI ASGI application with JWT principal injection
    """
    wrapper = A2ASecurityWrapper(
        a2a_asgi_app=a2a_asgi_app,
        config=config,
        title=title,
        version=version,
        enable_cors=enable_cors,
        cors_origins=cors_origins
    )
    return wrapper.get_asgi_app()


# Example usage for testing
if __name__ == "__main__":
    # Load configuration
    config = load_env_config()
    
    # Create a simple ASGI app for testing
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    
    async def hello(request):
        # Check if authentication context is available
        user_principal = getattr(request.state, 'user_principal', None)
        return JSONResponse({
            "message": "Hello from A2A app!",
            "authenticated": user_principal is not None,
            "user": user_principal
        })
    
    test_a2a_app = Starlette(routes=[
        Route("/test", hello),
    ])
    
    # Wrap with security
    secured_app = wrap_a2a_with_security(test_a2a_app, config=config)
    
    print(f"Secured app created for {config['AGENT_NAME']} v{config['AGENT_VERSION']}")
    print(f"Available at: {config['A2A_HOST']}:{config['A2A_PORT']}")
    print(f"Health check: /health")
    print(f"Auth endpoint: /{config['TOKEN_ENDPOINT']}")
    print(f"API docs: /docs")
    print(f"Features: Authentication + A2A Context Injection")
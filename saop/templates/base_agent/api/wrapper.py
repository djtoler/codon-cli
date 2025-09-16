# api/wrapper.py (UPDATED)
"""
Security wrapper for A2A applications - cleaned up version
"""
import logging
import os
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.cors import CORSMiddleware
from config.agent_config import load_env_config, EnvironmentConfig

from api.router import create_main_router
from api.middleware import A2AAuthContextMiddleware

logger = logging.getLogger(__name__)

class A2ASecurityWrapper:
    """Enterprise security wrapper for A2A applications with clean separation"""
    
    def __init__(
        self,
        a2a_asgi_app,
        config: Optional[EnvironmentConfig] = None,
        title: Optional[str] = None,
        version: Optional[str] = None,
        enable_cors: bool = True,
        cors_origins: Optional[List[str]] = None
    ):
        self.config = config or load_env_config()
        self.title = title or self.config.get('AGENT_NAME', 'SAOP Agent')
        self.version = version or self.config.get('AGENT_VERSION', '1.0.0')
        self.a2a_app = a2a_asgi_app
        
        # Parse CORS origins from config if not provided
        if cors_origins is None:
            cors_env = os.getenv("CORS_ORIGINS", "")
            cors_origins = [origin.strip() for origin in cors_env.split(",") if origin.strip()]
        
        self.fastapi_app = self._create_secured_app(enable_cors, cors_origins)
        logger.info(f"Security wrapper initialized for {self.title} v{self.version}")

    def _setup_templates_and_static(self, app: FastAPI):
        """Setup Jinja2 templates and static files"""
        templates_dir = Path(self.config.get("TEMPLATES_DIR", "frontend/templates"))
        static_dir = Path(self.config.get("STATIC_DIR", "static"))
        
        templates_dir.mkdir(exist_ok=True)
        static_dir.mkdir(exist_ok=True)
        
        app.mount("frontend/static", StaticFiles(directory=str(static_dir)), name="static")
        
        templates = Jinja2Templates(directory=str(templates_dir))
        
        # Add template utilities
        def user_has_permission(user, permission_str: str) -> bool:
            if not user or not hasattr(user, 'permissions'):
                return False
            from api.auth import Permission
            try:
                permission = Permission(permission_str)
                return permission in user.permissions
            except (ValueError, AttributeError):
                return False
        
        def format_datetime(dt):
            if dt and hasattr(dt, 'strftime'):
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            return str(dt) if dt else "Never"
        
        templates.env.globals.update({
            "user_has_permission": user_has_permission,
            "format_datetime": format_datetime,
        })
        
        app.state.templates = templates
        logger.info(f"Templates configured: {templates_dir}")

    def _create_secured_app(self, enable_cors: bool, cors_origins: Optional[List[str]]) -> FastAPI:
        """Create FastAPI wrapper with clean architecture"""
        
        app = FastAPI(
            title=self.title,
            version=self.version,
            description=f"Enterprise SAOP agent with clean architecture",
            docs_url="/docs",
            redoc_url="/redoc",
            openapi_url="/openapi.json"
        )

        # Setup templates first
        self._setup_templates_and_static(app)

        # Include the main router (now cleanly separated)
        app.include_router(create_main_router())
        logger.info("Main router included with clean separation")

        # Add CORS middleware
        if enable_cors:
            allowed_origins = cors_origins or [
                "http://localhost:3000",
                "http://localhost:8080",
                "http://localhost:5173",
                "https://yourdomain.com"
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

        # Simple health check
        @app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "service": self.title,
                "version": self.version,
                "architecture": "clean_separation",
                "modules": ["auth", "agents", "streaming", "web"]
            }

        # A2A agent card
        @app.get("/.well-known/agent-card.json")
        async def agent_card():
            return {
                "name": self.title,
                "version": self.version,
                "description": f"Enterprise SAOP agent with clean architecture",
                "capabilities": [
                    "authentication", "authorization", "a2a_auth_context",
                    "mcp_integration", "observability", "web_interface"
                ],
                "endpoints": {
                    "health": "/health",
                    "auth": "/api/v1/auth",
                    "agents": "/api/v1/agents", 
                    "streaming": "/api/v1/streaming",
                    "web_dashboard": "/",
                    "docs": "/docs"
                }
            }

        # Mount A2A app
        app.mount("/a2a", self.a2a_app)
        
        logger.info("FastAPI security wrapper configured with clean architecture")
        return app

    def get_asgi_app(self):
        return self.fastapi_app

    def get_config(self) -> EnvironmentConfig:
        return self.config

def wrap_a2a_with_security(
    a2a_asgi_app,
    config: Optional[EnvironmentConfig] = None,
    **kwargs
) -> FastAPI:
    """Convenience function with clean architecture"""
    wrapper = A2ASecurityWrapper(a2a_asgi_app=a2a_asgi_app, config=config, **kwargs)
    return wrapper.get_asgi_app()
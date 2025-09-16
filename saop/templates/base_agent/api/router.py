# api/main_router.py
from fastapi import APIRouter
from api import _auth_routes, _agent_routes, _streaming_routes, _web_routes

def create_main_router() -> APIRouter:
    """Create the main router with clear separation of concerns"""
    main_router = APIRouter()
    
    # API routes with clear prefixing
    api_router = APIRouter(prefix="/api/v1")
    api_router.include_router(_auth_routes.router, prefix="/auth", tags=["authentication"])
    api_router.include_router(_agent_routes.router, prefix="/agents", tags=["agents"])
    api_router.include_router(_streaming_routes.router, prefix="/streaming", tags=["streaming"])
    
    main_router.include_router(api_router)
    
    # Web routes at root level
    main_router.include_router(_web_routes.create_web_router())
    
    return main_router
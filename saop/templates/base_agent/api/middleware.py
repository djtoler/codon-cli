# api/middleware.py (fixed version)
"""
middleware that blocks unauthorized A2A requests.
"""
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from api.auth import get_current_user, User
import logging
logger = logging.getLogger(__name__)


class A2AAuthContextMiddleware(BaseHTTPMiddleware):
    """
    Enhanced middleware that blocks unauthorized A2A requests and injects user context.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Add debug logging for streaming endpoints
        if "/streaming/" in request.url.path:
            logger.info(f"MIDDLEWARE DEBUG: {request.method} {request.url.path}")
            logger.info(f"MIDDLEWARE DEBUG: Query params: {dict(request.query_params)}")
            logger.info(f"MIDDLEWARE DEBUG: Headers: {dict(request.headers)}")
        
        # Skip auth for public endpoints
        if self._should_skip_auth_injection(request):
            if "/streaming/" in request.url.path:
                logger.info("MIDDLEWARE DEBUG: Skipping auth injection")
            return await call_next(request)
        
        # Extract user from auth headers
        try:
            token = self._extract_bearer_token(request)
            api_key = self._extract_api_key(request)
            
            if "/streaming/" in request.url.path:
                logger.info(f"MIDDLEWARE DEBUG: Extracted token: {token[:10] if token else None}...")
                logger.info(f"MIDDLEWARE DEBUG: Extracted API key: {api_key}")
            
            current_user = await get_current_user(token=token, api_key=api_key)
            
            if "/streaming/" in request.url.path:
                logger.info(f"MIDDLEWARE DEBUG: Current user: {current_user.username if current_user else None}")
                
        except Exception as e:
            if "/streaming/" in request.url.path:
                logger.error(f"MIDDLEWARE DEBUG: Auth extraction error: {e}")
            current_user = None
        
        # For A2A endpoints, REQUIRE authentication
        if self._is_a2a_endpoint(request):
            if not current_user:
                return JSONResponse(
                    content={
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32001,
                            "message": "Authentication required for A2A endpoints"
                        },
                        "id": None
                    },
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # Check A2A-specific permissions
            if not self._has_a2a_permissions(current_user):
                return JSONResponse(
                    content={
                        "jsonrpc": "2.0", 
                        "error": {
                            "code": -32002,
                            "message": "Insufficient permissions for A2A operations"
                        },
                        "id": None
                    },
                    status_code=403
                )
        
        # Inject user context into request state
        if current_user:
            request.state.authenticated_user = current_user
            request.state.user_principal = {
                "username": current_user.username,
                "roles": [role.value for role in current_user.roles],
                "permissions": [perm.value for perm in current_user.permissions],
                "auth_method": "API_KEY" if current_user.username.startswith("apikey:") else "JWT"
            }
        
        if "/streaming/" in request.url.path:
            logger.info(f"MIDDLEWARE DEBUG: Proceeding to endpoint")
        
        response = await call_next(request)
        
        if "/streaming/" in request.url.path:
            logger.info(f"MIDDLEWARE DEBUG: Response status: {response.status_code}")
        
        return response
    
    def _should_skip_auth_injection(self, request: Request) -> bool:
        """Skip auth injection for public endpoints"""
        public_paths = [
            "/health",
            "/docs",
            "/redoc", 
            "/openapi.json",
            "/auth/health",  # Auth health check should be public
            "/.well-known/agent-card.json"  # Agent card should be public
        ]
        path = request.url.path
        return any(path.startswith(public) for public in public_paths)
    
    def _is_a2a_endpoint(self, request: Request) -> bool:
        """Check if request is for A2A protocol endpoints"""
        path = request.url.path
        method = request.method
        
        # A2A endpoints: root path with POST method (JSON-RPC)
        if path == "/" and method == "POST":
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                return True
        
        return False
    
    def _has_a2a_permissions(self, user: User) -> bool:
        """Check if user has permissions for A2A operations"""
        from api.auth import Permission
        
        required_permissions = [Permission.SUBMIT_TASK, Permission.READ_AGENT]
        user_permissions = user.permissions
        
        # User needs at least one of the required permissions
        return any(perm in user_permissions for perm in required_permissions)
    
    def _extract_bearer_token(self, request: Request) -> Optional[str]:
        """Extract JWT token from Authorization header OR query parameters"""
        # First try header (for regular requests)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]
        
        # Fallback to query parameters (for EventSource/SSE requests)
        token_query = request.query_params.get("token")
        if token_query:
            return token_query
        
        return None
    
    def _extract_api_key(self, request: Request) -> Optional[str]:
        """Extract API key from configured header OR query parameters"""
        from api.auth import auth_provider
        
        # First try header (for regular requests)
        api_key_header = auth_provider.config["API_KEY_HEADER"]
        api_key = request.headers.get(api_key_header)
        if api_key:
            return api_key
        
        # Fallback to query parameters (for EventSource/SSE requests)
        api_key_query = request.query_params.get("api_key")
        if api_key_query:
            return api_key_query
        
        return None
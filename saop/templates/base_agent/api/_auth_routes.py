# api/auth_routes.py
"""
Clean class-based authentication routes - OAuth2, JWT, user management
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from api.auth import (
    auth_provider,
    require_authentication,
    require_role,
    require_permission,
    Token,
    User,
    Role,
    Permission
)

logger = logging.getLogger(__name__)


# Response Models
class UserResponse(BaseModel):
    """Standard user response model"""
    username: str
    email: str
    full_name: str
    roles: List[Role]
    permissions: List[Permission]
    disabled: bool
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None


class HealthResponse(BaseModel):
    """Authentication service health response"""
    status: str = Field(description="Service health status")
    authentication: str = Field(description="Authentication availability")
    timestamp: str = Field(description="Response timestamp")
    version: Optional[str] = None


class UserListResponse(BaseModel):
    """Admin user list response"""
    users: List[Dict[str, Any]]
    total_count: int
    active_count: int
    disabled_count: int


class ApiKeyListResponse(BaseModel):
    """Admin API key list response"""
    api_keys: List[Dict[str, Any]]
    total_count: int
    active_count: int
    inactive_count: int


class AuthenticationError(Exception):
    """Custom authentication error"""
    def __init__(self, message: str, status_code: int = status.HTTP_401_UNAUTHORIZED):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuthResponseBuilder:
    """Builds consistent authentication responses"""
    
    @staticmethod
    def build_user_response(user: User) -> UserResponse:
        """Build standardized user response"""
        return UserResponse(
            username=user.username,
            email=user.email or "",
            full_name=user.full_name or "",
            roles=user.roles,
            permissions=user.permissions,
            disabled=user.disabled,
            created_at=getattr(user, 'created_at', None),
            last_login=getattr(user, 'last_login', None)
        )
    
    @staticmethod
    def build_health_response() -> HealthResponse:
        """Build health check response"""
        return HealthResponse(
            status="healthy",
            authentication="available",
            timestamp=datetime.utcnow().isoformat(),
            version=getattr(auth_provider, 'version', '1.0.0')
        )


class UserListBuilder:
    """Builds user management responses"""
    
    @staticmethod
    def build_user_list() -> UserListResponse:
        """Build admin user list with statistics"""
        users = []
        active_count = 0
        disabled_count = 0
        
        for username, user_data in auth_provider.users_db.items():
            user_info = {
                "username": user_data["username"],
                "email": user_data.get("email", ""),
                "full_name": user_data.get("full_name", ""),
                "roles": [role.value for role in user_data.get("roles", [])],
                "disabled": user_data.get("disabled", False),
                "created_at": user_data.get("created_at"),
                "last_login": user_data.get("last_login")
            }
            
            if user_info["disabled"]:
                disabled_count += 1
            else:
                active_count += 1
            
            users.append(user_info)
        
        return UserListResponse(
            users=users,
            total_count=len(users),
            active_count=active_count,
            disabled_count=disabled_count
        )
    
    @staticmethod
    def build_api_key_list() -> ApiKeyListResponse:
        """Build admin API key list with statistics"""
        keys = []
        active_count = 0
        inactive_count = 0
        
        for key_value, key_data in auth_provider.api_keys_db.items():
            key_info = {
                "key_id": key_value[-8:] + "...",
                "name": key_data.get("name", ""),
                "user": key_data.get("user", ""),
                "roles": [role.value for role in key_data.get("roles", [])],
                "active": key_data.get("active", False),
                "created_at": key_data.get("created_at"),
                "last_used": key_data.get("last_used")
            }
            
            if key_info["active"]:
                active_count += 1
            else:
                inactive_count += 1
            
            keys.append(key_info)
        
        return ApiKeyListResponse(
            api_keys=keys,
            total_count=len(keys),
            active_count=active_count,
            inactive_count=inactive_count
        )


class AuthenticationService:
    """Core authentication service operations"""
    
    def __init__(self):
        self.response_builder = AuthResponseBuilder()
        self.user_list_builder = UserListBuilder()
    
    def authenticate_user(self, username: str, password: str) -> User:
        """Authenticate user with enhanced error handling"""
        try:
            user = auth_provider.authenticate_user(username, password)
            if not user:
                logger.warning(f"Authentication failed for user: {username}")
                raise AuthenticationError(
                    "Incorrect username or password",
                    status.HTTP_401_UNAUTHORIZED
                )
            
            logger.info(f"User authenticated successfully: {username}")
            return user
            
        except Exception as e:
            logger.error(f"Authentication error for {username}: {e}")
            if isinstance(e, AuthenticationError):
                raise
            raise AuthenticationError("Authentication service unavailable")
    
    def create_access_token(self, user: User) -> Token:
        """Create JWT access token with proper configuration"""
        try:
            expires_minutes = auth_provider.config.get("JWT_EXPIRE_MINUTES", 30)
            access_token_expires = timedelta(minutes=expires_minutes)
            
            access_token = auth_provider.create_access_token(
                user=user,
                expires_delta=access_token_expires
            )
            
            logger.info(f"Access token created for user: {user.username}")
            
            return Token(
                access_token=access_token,
                token_type="bearer",
                expires_in=expires_minutes * 60
            )
            
        except Exception as e:
            logger.error(f"Token creation failed for {user.username}: {e}")
            raise AuthenticationError("Token creation failed")
    
    def get_current_user_info(self, user: User) -> UserResponse:
        """Get enhanced user information"""
        try:
            return self.response_builder.build_user_response(user)
        except Exception as e:
            logger.error(f"Error building user response for {user.username}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving user information"
            )
    
    def get_health_status(self) -> HealthResponse:
        """Get authentication service health"""
        try:
            return self.response_builder.build_health_response()
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unhealthy"
            )
    
    def get_all_users(self) -> UserListResponse:
        """Get all users with statistics (admin only)"""
        try:
            return self.user_list_builder.build_user_list()
        except Exception as e:
            logger.error(f"Error retrieving user list: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving user list"
            )
    
    def get_all_api_keys(self) -> ApiKeyListResponse:
        """Get all API keys with statistics (admin only)"""
        try:
            return self.user_list_builder.build_api_key_list()
        except Exception as e:
            logger.error(f"Error retrieving API key list: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving API key list"
            )


class AuthRouteHandler:
    """Handles all authentication route operations"""
    
    def __init__(self):
        self.auth_service = AuthenticationService()
    
    async def login_for_access_token(self, form_data: OAuth2PasswordRequestForm) -> Token:
        """Handle OAuth2 login flow"""
        try:
            user = self.auth_service.authenticate_user(form_data.username, form_data.password)
            return self.auth_service.create_access_token(user)
            
        except AuthenticationError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=e.message,
                headers={"WWW-Authenticate": "Bearer"}
            )
        except Exception as e:
            logger.error(f"Unexpected error in login: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service error"
            )
    
    async def get_current_user(self, current_user: User) -> UserResponse:
        """Get current user information"""
        return self.auth_service.get_current_user_info(current_user)
    
    async def get_health(self) -> HealthResponse:
        """Get service health"""
        return self.auth_service.get_health_status()
    
    async def list_all_users(self, current_user: User) -> UserListResponse:
        """List all users (admin only)"""
        logger.info(f"Admin {current_user.username} requested user list")
        return self.auth_service.get_all_users()
    
    async def list_all_api_keys(self, current_user: User) -> ApiKeyListResponse:
        """List all API keys (admin only)"""
        logger.info(f"Admin {current_user.username} requested API key list")
        return self.auth_service.get_all_api_keys()


# Create router with clean class-based handlers
def create_auth_router() -> APIRouter:
    """Create authentication router with class-based handlers"""
    router = APIRouter()
    handler = AuthRouteHandler()
    
    @router.post("/token", response_model=Token)
    async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
        """OAuth2 password flow endpoint"""
        return await handler.login_for_access_token(form_data)
    
    @router.get("/users/me", response_model=UserResponse)
    async def read_users_me(current_user: User = Depends(require_authentication)):
        """Get current authenticated user information"""
        return await handler.get_current_user(current_user)
    
    @router.get("/health", response_model=HealthResponse)
    async def auth_health():
        """Authentication service health check"""
        return await handler.get_health()
    
    @router.get("/admin/users", response_model=UserListResponse)
    async def list_users(current_user: User = Depends(require_role(Role.ADMIN))):
        """List all users with statistics (admin only)"""
        return await handler.list_all_users(current_user)
    
    @router.get("/admin/api-keys", response_model=ApiKeyListResponse)
    async def list_api_keys(current_user: User = Depends(require_permission(Permission.MANAGE_KEYS))):
        """List all API keys with statistics (admin only)"""
        return await handler.list_all_api_keys(current_user)
    
    return router


# Export the router
router = create_auth_router()
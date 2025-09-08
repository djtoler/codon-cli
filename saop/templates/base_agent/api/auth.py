# api/auth.py
"""
Authentication provider for SAOP agent platform.
Handles JWT token validation and API key authentication.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Set
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from pydantic import BaseModel
from enum import Enum

from config.agent_config import load_env_config

class Role(str, Enum):
    ADMIN = "admin"
    DEVELOPER = "developer" 
    VIEWER = "viewer"

class Permission(str, Enum):
    CREATE_AGENT = "agent:create"
    READ_AGENT = "agent:read"
    UPDATE_AGENT = "agent:update"
    DELETE_AGENT = "agent:delete"
    SUBMIT_TASK = "task:submit"
    VIEW_TASK = "task:view"
    VIEW_TRACES = "traces:view"
    VIEW_METRICS = "metrics:view"
    MANAGE_USERS = "admin:users"
    MANAGE_KEYS = "admin:keys"

# Role permissions mapping
ROLE_PERMISSIONS = {
    Role.VIEWER: {
        Permission.READ_AGENT,
        Permission.SUBMIT_TASK,
        Permission.VIEW_TASK,
        Permission.VIEW_TRACES
    },
    Role.DEVELOPER: {
        Permission.CREATE_AGENT,
        Permission.READ_AGENT,
        Permission.UPDATE_AGENT,
        Permission.SUBMIT_TASK,
        Permission.VIEW_TASK,
        Permission.VIEW_TRACES,
        Permission.VIEW_METRICS
    },
    Role.ADMIN: {
        Permission.CREATE_AGENT,
        Permission.READ_AGENT,
        Permission.UPDATE_AGENT,
        Permission.DELETE_AGENT,
        Permission.SUBMIT_TASK,
        Permission.VIEW_TASK,
        Permission.VIEW_TRACES,
        Permission.VIEW_METRICS,
        Permission.MANAGE_USERS,
        Permission.MANAGE_KEYS
    }
}

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: Optional[int] = None

class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: bool = False
    roles: List[Role] = []
    permissions: List[Permission] = []

class UserInDB(User):
    hashed_password: str

class AuthenticationProvider:
    """
    Centralized authentication provider for SAOP platform.
    Handles JWT validation, API key authentication, and user management.
    """
    
    def __init__(self):
        self.config = load_env_config()
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        # Configure OAuth2 with proper token endpoint
        token_endpoint = self.config.get("TOKEN_ENDPOINT", "auth/token")
        if not token_endpoint.startswith("/"):
            token_endpoint = f"/{token_endpoint}"
        
        self.oauth2_scheme = OAuth2PasswordBearer(
            tokenUrl=token_endpoint.lstrip("/"),  # Remove leading slash for tokenUrl
            auto_error=False
        )
        
        self.api_key_header = APIKeyHeader(
            name=self.config["API_KEY_HEADER"],
            auto_error=False
        )
        self._initialize_users()
        self._initialize_api_keys()
    
    def _initialize_users(self):
        """Initialize user database from configuration"""
        self.users_db = {
            self.config["DEFAULT_ADMIN_USERNAME"]: {
                "username": self.config["DEFAULT_ADMIN_USERNAME"],
                "full_name": self.config.get("DEFAULT_ADMIN_FULL_NAME", "Administrator"),
                "email": self.config["DEFAULT_ADMIN_EMAIL"],
                "hashed_password": self.config["DEFAULT_ADMIN_PASSWORD_HASH"],
                "disabled": False,
                "roles": [Role.ADMIN]
            },
            self.config["DEFAULT_DEV_USERNAME"]: {
                "username": self.config["DEFAULT_DEV_USERNAME"],
                "full_name": self.config.get("DEFAULT_DEV_FULL_NAME", "Developer"),
                "email": self.config["DEFAULT_DEV_EMAIL"],
                "hashed_password": self.config["DEFAULT_DEV_PASSWORD_HASH"],
                "disabled": False,
                "roles": [Role.DEVELOPER]
            }
        }
    
    def _initialize_api_keys(self):
        """Initialize API key database from configuration"""
        self.api_keys_db = {
            self.config["DEFAULT_DEV_API_KEY"]: {
                "name": "Development API Key",
                "user": self.config["DEFAULT_DEV_USERNAME"],
                "roles": [Role.DEVELOPER],
                "active": True
            }
        }
    
    def get_user_permissions(self, roles: List[Role]) -> List[Permission]:
        """Get all permissions for given roles"""
        permissions = set()
        for role in roles:
            permissions.update(ROLE_PERMISSIONS.get(role, set()))
        return list(permissions)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def hash_password(self, password: str) -> str:
        """Generate password hash"""
        return self.pwd_context.hash(password)
    
    def get_user(self, username: str) -> Optional[UserInDB]:
        """Get user by username"""
        if username in self.users_db:
            user_data = self.users_db[username].copy()
            user_data["permissions"] = self.get_user_permissions(user_data["roles"])
            return UserInDB(**user_data)
        return None
    
    def authenticate_user(self, username: str, password: str) -> Optional[UserInDB]:
        """Authenticate user credentials"""
        user = self.get_user(username)
        if not user or user.disabled:
            return None
        
        if not self.verify_password(password, user.hashed_password):
            return None
        
        return user
    
    def create_access_token(self, user: UserInDB, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token for user"""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.config["JWT_EXPIRE_MINUTES"])
        
        payload = {
            "sub": user.username,
            "exp": expire,
            "iat": datetime.utcnow(),
            "iss": self.config["JWT_ISSUER"],
            "aud": self.config["JWT_AUDIENCE"],
            "roles": [role.value for role in user.roles],
            "permissions": [perm.value for perm in user.permissions]
        }
        
        return jwt.encode(payload, self.config["JWT_SECRET_KEY"], algorithm=self.config["JWT_ALGORITHM"])
    
    def validate_token(self, token: str) -> Optional[User]:
        """Validate JWT token and return user"""
        try:
            payload = jwt.decode(
                token,
                self.config["JWT_SECRET_KEY"],
                algorithms=[self.config["JWT_ALGORITHM"]],
                audience=self.config["JWT_AUDIENCE"],
                issuer=self.config["JWT_ISSUER"]
            )
            
            username = payload.get("sub")
            if not username:
                return None
            
            roles = [Role(role) for role in payload.get("roles", [])]
            permissions = [Permission(perm) for perm in payload.get("permissions", [])]
            
            return User(
                username=username,
                roles=roles,
                permissions=permissions
            )
            
        except (JWTError, ValueError):
            return None
    
    def validate_api_key(self, api_key: str) -> Optional[User]:
        """Validate API key and return service user"""
        if api_key not in self.api_keys_db:
            return None
        
        key_data = self.api_keys_db[api_key]
        if not key_data["active"]:
            return None
        
        roles = key_data["roles"]
        permissions = self.get_user_permissions(roles)
        
        return User(
            username=f"apikey:{key_data['name']}",
            email=f"{key_data['user']}@service.local",
            full_name=f"API Key: {key_data['name']}",
            roles=roles,
            permissions=permissions
        )

# Global authentication provider instance
auth_provider = AuthenticationProvider()

# FastAPI dependency functions
async def get_current_user(
    token: Optional[str] = Depends(auth_provider.oauth2_scheme),
    api_key: Optional[str] = Depends(auth_provider.api_key_header)
) -> Optional[User]:
    """Get current authenticated user from token or API key"""
    if api_key:
        user = auth_provider.validate_api_key(api_key)
        if user:
            return user
    
    if token:
        user = auth_provider.validate_token(token)
        if user:
            return user
    
    return None

async def require_authentication(
    current_user: Optional[User] = Depends(get_current_user)
) -> User:
    """Require valid authentication"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if current_user.disabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled"
        )
    
    return current_user

def require_permission(permission: Permission):
    """Dependency factory for permission-based access control"""
    def permission_checker(current_user: User = Depends(require_authentication)) -> User:
        if permission not in current_user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value}"
            )
        return current_user
    return permission_checker

def require_role(role: Role):
    """Dependency factory for role-based access control"""
    def role_checker(current_user: User = Depends(require_authentication)) -> User:
        if role not in current_user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role required: {role.value}"
            )
        return current_user
    return role_checker
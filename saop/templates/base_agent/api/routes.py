# api/routes.py
"""
Authentication routes for SAOP agent platform.
Provides OAuth2 token endpoints and user management.
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List

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

router = APIRouter()

# Response models
class UserResponse(BaseModel):
    username: str
    email: str
    full_name: str
    roles: List[Role]
    permissions: List[Permission]
    disabled: bool

class HealthResponse(BaseModel):
    status: str
    authentication: str
    timestamp: str

# OAuth2 token endpoint
@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 password flow endpoint.
    
    Authenticate with username/password to receive JWT access token.
    Use this token in Authorization header: Bearer <token>
    """
    user = auth_provider.authenticate_user(form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=auth_provider.config["JWT_EXPIRE_MINUTES"])
    access_token = auth_provider.create_access_token(
        user=user, 
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=auth_provider.config["JWT_EXPIRE_MINUTES"] * 60
    )

# User info endpoint
@router.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(require_authentication)):
    """
    Get current authenticated user information.
    
    Returns user details, roles, and permissions.
    Works with both JWT tokens and API keys.
    """
    return UserResponse(
        username=current_user.username,
        email=current_user.email or "",
        full_name=current_user.full_name or "",
        roles=current_user.roles,
        permissions=current_user.permissions,
        disabled=current_user.disabled
    )

# Health check endpoint
@router.get("/health", response_model=HealthResponse)
async def auth_health():
    """
    Authentication service health check.
    
    Public endpoint to verify auth service is running.
    """
    from datetime import datetime
    
    return HealthResponse(
        status="healthy",
        authentication="available",
        timestamp=datetime.utcnow().isoformat()
    )

# Protected demo endpoint
@router.get("/protected")
async def protected_demo(current_user: User = Depends(require_authentication)):
    """
    Demo protected endpoint.
    
    Requires valid authentication (JWT token or API key).
    Shows user context and available permissions.
    """
    auth_method = "API Key" if current_user.username.startswith("apikey:") else "JWT"
    
    return {
        "message": f"Hello {current_user.username}! This is a protected endpoint.",
        "user": {
            "username": current_user.username,
            "roles": [role.value for role in current_user.roles],
            "permissions": [perm.value for perm in current_user.permissions]
        },
        "auth_method": auth_method
    }

# Admin endpoints
@router.get("/admin/users")
async def list_users(current_user: User = Depends(require_role(Role.ADMIN))):
    """
    List all users (admin only).
    
    Requires admin role.
    """
    users = []
    for username, user_data in auth_provider.users_db.items():
        users.append({
            "username": user_data["username"],
            "email": user_data["email"],
            "full_name": user_data["full_name"],
            "roles": [role.value for role in user_data["roles"]],
            "disabled": user_data["disabled"]
        })
    
    return {"users": users}

@router.get("/admin/api-keys")
async def list_api_keys(current_user: User = Depends(require_permission(Permission.MANAGE_KEYS))):
    """
    List all API keys (admin/key manager only).
    
    Requires MANAGE_KEYS permission.
    """
    keys = []
    for key_value, key_data in auth_provider.api_keys_db.items():
        keys.append({
            "key_id": key_value[-8:] + "...",  # Show last 8 chars only
            "name": key_data["name"],
            "user": key_data["user"],
            "roles": [role.value for role in key_data["roles"]],
            "active": key_data["active"]
        })
    
    return {"api_keys": keys}

# Developer endpoints
@router.get("/developer/permissions")
async def check_permissions(current_user: User = Depends(require_role(Role.DEVELOPER))):
    """
    Check current user permissions (developer+ only).
    
    Useful for debugging permission issues.
    """
    return {
        "username": current_user.username,
        "roles": [role.value for role in current_user.roles],
        "permissions": [perm.value for perm in current_user.permissions],
        "can_create_agent": Permission.CREATE_AGENT in current_user.permissions,
        "can_view_metrics": Permission.VIEW_METRICS in current_user.permissions,
        "can_manage_users": Permission.MANAGE_USERS in current_user.permissions
    }

# Agent management endpoints (examples)
@router.post("/agents")
async def create_agent(current_user: User = Depends(require_permission(Permission.CREATE_AGENT))):
    """
    Create new agent (developer+ only).
    
    Placeholder endpoint demonstrating permission-based access.
    """
    return {
        "message": "Agent creation endpoint",
        "created_by": current_user.username,
        "note": "This is a placeholder - implement actual agent creation logic"
    }

@router.get("/agents")
async def list_agents(current_user: User = Depends(require_permission(Permission.READ_AGENT))):
    """
    List agents (all authenticated users).
    
    Viewers can read agents, developers can create/modify.
    """
    return {
        "message": "Agent listing endpoint",
        "user": current_user.username,
        "permissions": [perm.value for perm in current_user.permissions],
        "note": "This is a placeholder - implement actual agent listing logic"
    }

# Task management endpoints (examples)
@router.post("/tasks")
async def submit_task(current_user: User = Depends(require_permission(Permission.SUBMIT_TASK))):
    """
    Submit task to agent (all authenticated users).
    
    Basic permission check for task submission.
    """
    return {
        "message": "Task submission endpoint",
        "submitted_by": current_user.username,
        "note": "This is a placeholder - implement actual task submission logic"
    }

@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    current_user: User = Depends(require_permission(Permission.VIEW_TASK))
):
    """
    Get task details (all authenticated users).
    
    Basic permission check for task viewing.
    """
    return {
        "task_id": task_id,
        "message": "Task details endpoint",
        "requested_by": current_user.username,
        "note": "This is a placeholder - implement actual task retrieval logic"
    }
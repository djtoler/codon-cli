# api/agent_routes.py
"""
Clean class-based agent management API endpoints
"""
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.auth import require_permission, require_authentication, User, Permission, Role
from api.utils.agent_utils import agent_manager, AgentInfo

logger = logging.getLogger(__name__)


# Request Models
class CreateAgentRequest(BaseModel):
    """Request model for creating new agents"""
    name: str = Field(description="Agent display name")
    description: Optional[str] = Field(None, description="Agent description")
    system_prompt: str = Field(description="Agent system prompt")
    tools: List[str] = Field(default_factory=list, description="Agent tools")
    tool_bundles: List[str] = Field(default_factory=list, description="Agent tool bundles")
    tags: List[str] = Field(default_factory=list, description="Agent tags")
    human_review: bool = Field(default=False, description="Requires human review")


class UpdateAgentRequest(BaseModel):
    """Request model for updating agents"""
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: Optional[List[str]] = None
    tool_bundles: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    human_review: Optional[bool] = None


# Response Models
class AgentListResponse(BaseModel):
    """Response for agent listing"""
    agents: List[Dict[str, Any]]
    total_count: int
    online_count: int
    domains: List[str]
    total_active_tasks: int


class AgentDetailResponse(BaseModel):
    """Detailed agent response"""
    agent: Dict[str, Any]
    related_agents: List[Dict[str, Any]]
    recent_tasks: List[Dict[str, Any]]


class AgentCreationResponse(BaseModel):
    """Response for agent creation"""
    success: bool
    agent_id: str
    message: str
    created_by: str
    created_at: datetime


class PermissionCheckResponse(BaseModel):
    """Response for permission checking"""
    username: str
    roles: List[str]
    permissions: List[str]
    agent_capabilities: Dict[str, bool]
    system_access: Dict[str, bool]


class AgentListBuilder:
    """Builds agent list responses with statistics"""
    
    @staticmethod
    def build_agent_list(user: User) -> AgentListResponse:
        """Build comprehensive agent list with stats"""
        try:
            agents = agent_manager.get_agents_for_templates()
            
            # Calculate statistics
            total_count = len(agents)
            online_count = len([a for a in agents if a.get("status") == "online"])
            total_active_tasks = sum(a.get("active_tasks", 0) for a in agents)
            
            # Get unique domains
            domains = list(set(a.get("domain", "General") for a in agents))
            domains.sort()
            
            # Filter agents based on user permissions if needed
            filtered_agents = AgentListBuilder._filter_agents_by_permission(agents, user)
            
            return AgentListResponse(
                agents=filtered_agents,
                total_count=total_count,
                online_count=online_count,
                domains=domains,
                total_active_tasks=total_active_tasks
            )
            
        except Exception as e:
            logger.error(f"Error building agent list for user {user.username}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to retrieve agent list"
            )
    
    @staticmethod
    def _filter_agents_by_permission(agents: List[Dict[str, Any]], user: User) -> List[Dict[str, Any]]:
        """Filter agents based on user permissions"""
        # For now, return all agents if user has READ_AGENT permission
        # In the future, you might want to filter based on user roles or agent visibility
        if Permission.READ_AGENT in user.permissions:
            return agents
        return []


class AgentDetailBuilder:
    """Builds detailed agent responses"""
    
    @staticmethod
    def build_agent_detail(agent_id: str, user: User) -> AgentDetailResponse:
        """Build detailed agent information"""
        try:
            agent_info = agent_manager.get_agent_by_id(agent_id)
            
            if not agent_info:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Agent '{agent_id}' not found"
                )
            
            # Get agent as dict
            agent_dict = agent_info.to_dict()
            
            # Find related agents (same domain)
            all_agents = agent_manager.get_all_agents()
            related_agents = [
                a.to_dict() for a in all_agents 
                if a.domain == agent_info.domain and a.agent_id != agent_id
            ][:5]  # Limit to 5 related agents
            
            # Get recent tasks (would come from task history in real implementation)
            recent_tasks = AgentDetailBuilder._get_recent_tasks(agent_id)
            
            return AgentDetailResponse(
                agent=agent_dict,
                related_agents=related_agents,
                recent_tasks=recent_tasks
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error building agent detail for {agent_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to retrieve agent details"
            )
    
    @staticmethod
    def _get_recent_tasks(agent_id: str) -> List[Dict[str, Any]]:
        """Get recent tasks for an agent (placeholder implementation)"""
        # This would integrate with your task history system
        from saop.templates.base_agent.api._streaming_routes import active_tasks
        
        recent_tasks = []
        for task_id, task_data in active_tasks.items():
            if task_data.get("agent_role") == agent_id:
                recent_tasks.append({
                    "task_id": task_id[:8] + "...",
                    "status": task_data.get("status"),
                    "created_at": task_data.get("created_at"),
                    "message_preview": task_data.get("message_preview", "")[:100]
                })
        
        # Sort by creation time (most recent first)
        recent_tasks.sort(
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )
        
        return recent_tasks[:10]  # Return last 10 tasks


class PermissionAnalyzer:
    """Analyzes user permissions and capabilities"""
    
    @staticmethod
    def analyze_user_permissions(user: User) -> PermissionCheckResponse:
        """Comprehensive permission analysis"""
        try:
            # Basic user info
            roles = [role.value for role in user.roles]
            permissions = [perm.value for perm in user.permissions]
            
            # Agent-specific capabilities
            agent_capabilities = {
                "can_create_agent": Permission.CREATE_AGENT in user.permissions,
                "can_read_agent": Permission.READ_AGENT in user.permissions,
                "can_modify_agent": Permission.CREATE_AGENT in user.permissions,  # Assuming same permission
                "can_delete_agent": Role.ADMIN in user.roles,  # Only admins can delete
                "can_deploy_agent": Permission.CREATE_AGENT in user.permissions
            }
            
            # System access capabilities
            system_access = {
                "can_view_metrics": Permission.VIEW_METRICS in user.permissions,
                "can_manage_users": Permission.MANAGE_USERS in user.permissions,
                "can_manage_keys": Permission.MANAGE_KEYS in user.permissions,
                "can_submit_tasks": Permission.SUBMIT_TASK in user.permissions,
                "can_view_tasks": Permission.VIEW_TASK in user.permissions,
                "is_admin": Role.ADMIN in user.roles,
                "is_developer": Role.DEVELOPER in user.roles
            }
            
            return PermissionCheckResponse(
                username=user.username,
                roles=roles,
                permissions=permissions,
                agent_capabilities=agent_capabilities,
                system_access=system_access
            )
            
        except Exception as e:
            logger.error(f"Error analyzing permissions for {user.username}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to analyze user permissions"
            )


class AgentManagementService:
    """Core agent management operations"""
    
    def __init__(self):
        self.list_builder = AgentListBuilder()
        self.detail_builder = AgentDetailBuilder()
        self.permission_analyzer = PermissionAnalyzer()
    
    def create_agent(self, request: CreateAgentRequest, user: User) -> AgentCreationResponse:
        """Create new agent (placeholder for future implementation)"""
        try:
            # This is where you'd implement actual agent creation
            # For now, return a placeholder response
            
            agent_id = f"{request.name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            logger.info(f"Agent creation requested by {user.username}: {request.name}")
            
            # In real implementation, you would:
            # 1. Validate the request
            # 2. Create agent configuration
            # 3. Deploy agent to infrastructure
            # 4. Update agent registry
            # 5. Return actual agent details
            
            return AgentCreationResponse(
                success=True,
                agent_id=agent_id,
                message=f"Agent '{request.name}' creation initiated. This is a placeholder response.",
                created_by=user.username,
                created_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Agent creation failed for user {user.username}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Agent creation failed"
            )
    
    def list_agents(self, user: User) -> AgentListResponse:
        """Get comprehensive agent list"""
        return self.list_builder.build_agent_list(user)
    
    def get_agent_detail(self, agent_id: str, user: User) -> AgentDetailResponse:
        """Get detailed agent information"""
        return self.detail_builder.build_agent_detail(agent_id, user)
    
    def check_permissions(self, user: User) -> PermissionCheckResponse:
        """Analyze user permissions and capabilities"""
        return self.permission_analyzer.analyze_user_permissions(user)


class AgentRouteHandler:
    """Handles all agent route operations"""
    
    def __init__(self):
        self.agent_service = AgentManagementService()
    
    async def create_agent(self, request: CreateAgentRequest, user: User) -> AgentCreationResponse:
        """Handle agent creation request"""
        logger.info(f"Create agent request from {user.username}: {request.name}")
        return self.agent_service.create_agent(request, user)
    
    async def list_agents(self, user: User) -> AgentListResponse:
        """Handle agent listing request"""
        logger.debug(f"Agent list requested by {user.username}")
        return self.agent_service.list_agents(user)
    
    async def get_agent_detail(self, agent_id: str, user: User) -> AgentDetailResponse:
        """Handle agent detail request"""
        logger.debug(f"Agent detail requested by {user.username}: {agent_id}")
        return self.agent_service.get_agent_detail(agent_id, user)
    
    async def check_permissions(self, user: User) -> PermissionCheckResponse:
        """Handle permission check request"""
        logger.debug(f"Permission check requested by {user.username}")
        return self.agent_service.check_permissions(user)


def create_agent_router() -> APIRouter:
    """Create agent management router with class-based handlers"""
    router = APIRouter()
    handler = AgentRouteHandler()
    
    @router.post("/", response_model=AgentCreationResponse)
    async def create_agent(
        request: CreateAgentRequest,
        current_user: User = Depends(require_permission(Permission.CREATE_AGENT))
    ):
        """Create new agent (developer+ only)"""
        return await handler.create_agent(request, current_user)
    
    @router.get("/", response_model=AgentListResponse)
    async def list_agents(current_user: User = Depends(require_permission(Permission.READ_AGENT))):
        """List all agents with comprehensive information"""
        return await handler.list_agents(current_user)
    
    @router.get("/{agent_id}", response_model=AgentDetailResponse)
    async def get_agent_detail(
        agent_id: str,
        current_user: User = Depends(require_permission(Permission.READ_AGENT))
    ):
        """Get detailed information about a specific agent"""
        return await handler.get_agent_detail(agent_id, current_user)
    
    @router.get("/developer/permissions", response_model=PermissionCheckResponse)
    async def check_permissions(current_user: User = Depends(require_authentication)):
        """Check current user permissions and capabilities"""
        return await handler.check_permissions(current_user)
    
    return router


# Export the router
router = create_agent_router()
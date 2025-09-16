# api/web_routes.py
"""
Clean web routes for HTML interface using class-based agent utilities
"""
import logging
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from typing import Optional, List, Dict, Any

from api.auth import get_current_user, User
from api.utils.agent_utils import agent_manager
from api._streaming_routes import active_tasks

logger = logging.getLogger(__name__)


class WebRouteHandler:
    """Handler for web route operations"""
    
    def __init__(self):
        self.agent_manager = agent_manager
    
    def get_dashboard_context(self, request: Request, user: Optional[User]) -> Dict[str, Any]:
        """Build context for dashboard page"""
        # Could add system metrics, recent activity, etc.
        return {
            "request": request,
            "user": user,
            "page_title": "Dashboard",
            "system_status": "healthy",
            "total_agents": len(self.agent_manager.get_all_agents()),
            "total_active_tasks": len(active_tasks)
        }
    
    def get_agents_context(self, request: Request) -> Dict[str, Any]:
        """Build context for agents list page"""
        try:
            agents = self.agent_manager.get_agents_for_templates()
            
            # Calculate summary stats
            total_agents = len(agents)
            online_agents = len([a for a in agents if a["status"] == "online"])
            total_active_tasks = sum(a["active_tasks"] for a in agents)
            
            return {
                "request": request,
                "user": None,  # Authentication handled by JavaScript
                "page_title": "Agents",
                "agents": agents,
                "stats": {
                    "total_agents": total_agents,
                    "online_agents": online_agents,
                    "offline_agents": total_agents - online_agents,
                    "total_active_tasks": total_active_tasks
                }
            }
        except Exception as e:
            logger.error(f"Error loading agents for web interface: {e}")
            return {
                "request": request,
                "user": None,
                "page_title": "Agents - Error",
                "agents": [],
                "error_message": "Unable to load agents. Please try again later.",
                "stats": {"total_agents": 0, "online_agents": 0, "offline_agents": 0, "total_active_tasks": 0}
            }
    
    def get_agent_detail_context(self, request: Request, agent_id: str) -> Dict[str, Any]:
        """Build context for agent detail page"""
        try:
            agent_info = self.agent_manager.get_agent_by_id(agent_id)
            
            if not agent_info:
                return {
                    "request": request,
                    "error_code": 404,
                    "error_message": f"Agent '{agent_id}' not found",
                    "page_title": "Agent Not Found"
                }
            
            # Get detailed active tasks for this agent
            agent_active_tasks = self._get_agent_active_tasks(agent_id)
            
            # Convert to dict and enhance with additional details
            agent_dict = agent_info.to_dict()
            agent_dict["active_tasks_detail"] = agent_active_tasks
            agent_dict["total_capabilities"] = agent_info.capability_count
            
            return {
                "request": request,
                "user": None,  # Authentication handled by JavaScript
                "page_title": f"Agent: {agent_info.name}",
                "agent": agent_dict
            }
            
        except Exception as e:
            logger.error(f"Error loading agent detail for {agent_id}: {e}")
            return {
                "request": request,
                "error_code": 500,
                "error_message": f"Error loading agent details: {str(e)}",
                "page_title": "Agent Error"
            }
    
    def get_task_console_context(self, request: Request) -> Dict[str, Any]:
        """Build context for task console page"""
        try:
            # Transform active tasks for display
            visible_tasks = []
            for task_id, task_data in active_tasks.items():
                visible_tasks.append({
                    "task_id": task_id,
                    "task_id_short": task_id[:8] + "...",
                    "status": task_data["status"],
                    "created_at": task_data["created_at"],
                    "agent_role": task_data["agent_role"],
                    "agent_name": task_data["agent_role"].replace("_", " ").title(),
                    "message_preview": task_data["message_preview"],
                    "user": task_data.get("user", "unknown")
                })
            
            # Sort by creation time (newest first)
            visible_tasks.sort(
                key=lambda x: x["created_at"] if x["created_at"] else "",
                reverse=True
            )
            
            # Calculate stats
            status_counts = {}
            for task in visible_tasks:
                status = task["status"]
                status_counts[status] = status_counts.get(status, 0) + 1
            
            return {
                "request": request,
                "current_user": None,  # Will be handled by JavaScript
                "page_title": "Task Console",
                "tasks": visible_tasks,
                "stats": {
                    "total_tasks": len(visible_tasks),
                    "status_counts": status_counts
                }
            }
            
        except Exception as e:
            logger.error(f"Error loading task console: {e}")
            return {
                "request": request,
                "current_user": None,
                "page_title": "Task Console - Error",
                "tasks": [],
                "error_message": "Unable to load tasks. Please try again later.",
                "stats": {"total_tasks": 0, "status_counts": {}}
            }
    
    def _get_agent_active_tasks(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get detailed active tasks for a specific agent"""
        agent_tasks = []
        
        for task_id, task_data in active_tasks.items():
            if task_data.get("agent_role") == agent_id:
                # Truncate message preview safely
                message_preview = task_data.get("message_preview", "")
                if len(message_preview) > 50:
                    message_preview = message_preview[:47] + "..."
                
                agent_tasks.append({
                    "task_id": task_id,
                    "task_id_short": task_id[:8] + "...",
                    "status": task_data.get("status", "unknown"),
                    "created_at": task_data.get("created_at"),
                    "message_preview": message_preview,
                    "user": task_data.get("user", "unknown")
                })
        
        # Sort by creation time (newest first)
        agent_tasks.sort(
            key=lambda x: x["created_at"] if x["created_at"] else "",
            reverse=True
        )
        
        return agent_tasks






def create_web_router() -> APIRouter:
    """Create web router for HTML pages with clean class-based utilities"""
    router = APIRouter(tags=["web"])
    route_handler = WebRouteHandler()
    
    @router.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request, user: Optional[User] = Depends(get_current_user)):
        """Main dashboard page"""
        context = route_handler.get_dashboard_context(request, user)
        return request.app.state.templates.TemplateResponse("dashboard.html", context)
    
    @router.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        """Login page"""
        context = {
            "request": request,
            "page_title": "Login",
            "app_name": "SAOP Agent Platform"
        }
        return request.app.state.templates.TemplateResponse("login.html", context)
    
    @router.get("/agents", response_class=HTMLResponse)
    async def agents_page(request: Request):
        """Agents list page - authentication handled by JavaScript"""
        context = route_handler.get_agents_context(request)
        
        # Handle errors in template selection
        if "error_message" in context:
            return request.app.state.templates.TemplateResponse("error.html", context)
        
        return request.app.state.templates.TemplateResponse("agents.html", context)
    
    @router.get("/agents/{agent_id}", response_class=HTMLResponse)
    async def agent_detail(request: Request, agent_id: str):
        """Agent detail page with enhanced information"""
        context = route_handler.get_agent_detail_context(request, agent_id)
        
        # Handle errors (404, 500, etc.)
        if "error_code" in context:
            return request.app.state.templates.TemplateResponse("error.html", context)
        
        return request.app.state.templates.TemplateResponse("agent_detail.html", context)
    
    @router.get("/console", response_class=HTMLResponse)
    async def task_console(request: Request):
        """Task console page - authentication handled by JavaScript"""
        context = route_handler.get_task_console_context(request)
        
        # Handle errors in template selection
        if "error_message" in context:
            return request.app.state.templates.TemplateResponse("error.html", context)
        
        return request.app.state.templates.TemplateResponse("task_console.html", context)
    
    @router.get("/health", response_class=HTMLResponse)
    async def health_page(request: Request):
        """System health page for administrators"""
        try:
            # Gather system health information
            agents = agent_manager.get_all_agents()
            total_agents = len(agents)
            online_agents = len([a for a in agents if a.status.value == "online"])
            
            health_data = {
                "system_status": "healthy",
                "agents": {
                    "total": total_agents,
                    "online": online_agents,
                    "offline": total_agents - online_agents
                },
                "tasks": {
                    "active": len(active_tasks),
                    "by_status": {}
                }
            }
            
            # Count tasks by status
            for task_data in active_tasks.values():
                status = task_data.get("status", "unknown")
                health_data["tasks"]["by_status"][status] = health_data["tasks"]["by_status"].get(status, 0) + 1
            
            context = {
                "request": request,
                "page_title": "System Health",
                "health_data": health_data
            }
            
        except Exception as e:
            logger.error(f"Error gathering health data: {e}")
            context = {
                "request": request,
                "page_title": "System Health - Error",
                "error_message": f"Unable to gather health data: {str(e)}"
            }
        
        return request.app.state.templates.TemplateResponse("health.html", context)
    

    
    return router
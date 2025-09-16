# api/streaming_routes.py
"""
Clean class-based Server-Sent Events (SSE) streaming endpoints for real-time task execution
"""
import asyncio
import json
import uuid
import logging
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.auth import require_authentication, User, Permission, Role, auth_provider
from agent2agent.a2a_tasks import A2ATask
from langgraph.langgraph_executor import LangGraphA2AExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.types import Message, TextPart, Role as MessageRole, TaskState
from telemetry.langgraph_trace_utils import extract_llm_metadata
from opentelemetry import trace

logger = logging.getLogger(__name__)

# Global task registry - could be moved to a proper task store
active_tasks: Dict[str, Dict[str, Any]] = {}


# Request/Response Models
class TaskSubmissionRequest(BaseModel):
    """Request model for task submission"""
    message: str = Field(description="Task message/prompt")
    agent_role: Optional[str] = Field("general_support", description="Agent role to use")
    stream_traces: bool = Field(True, description="Enable trace streaming")
    stream_costs: bool = Field(True, description="Enable cost streaming")


class TaskSubmissionResponse(BaseModel):
    """Response for task submission"""
    task_id: str
    status: str
    stream_url: str
    created_at: datetime
    agent_role: str


class TaskInfo(BaseModel):
    """Task information model"""
    task_id: str
    status: str
    created_at: datetime
    agent_role: str
    message_preview: str
    user: str


class TaskListResponse(BaseModel):
    """Response for task listing"""
    tasks: List[TaskInfo]
    total_count: int
    status_counts: Dict[str, int]


class SSEEvent(BaseModel):
    """Server-Sent Event model"""
    event: str  # 'progress', 'trace', 'cost', 'completion', 'error', 'connection', 'keepalive'
    data: Dict[str, Any]
    timestamp: datetime
    task_id: str


class TaskAuthenticationService:
    """Handles authentication for streaming endpoints - simplified working version"""
    
    @staticmethod
    def authenticate_request(request: Request, api_key: Optional[str] = None, token: Optional[str] = None) -> Optional[User]:
        """Authenticate streaming request - simple version that works"""
        try:
            logger.info(f"=== STREAMING AUTH ATTEMPT ===")
            logger.info(f"Request URL: {request.url}")
            logger.info(f"API key provided: {api_key}")
            logger.info(f"Token provided: {token}")
            
            # Primary method: API key in query params (for EventSource)
            if api_key:
                logger.info(f"Authenticating with API key: {api_key}")
                user = auth_provider.validate_api_key(api_key)
                if user:
                    logger.info(f"✓ Authentication successful: {user.username}")
                    return user
                else:
                    logger.error(f"API key validation failed for: {api_key}")
                    logger.info(f"Available API keys: {list(auth_provider.api_keys_db.keys())}")
            
            # Fallback: Bearer token in header
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                bearer_token = auth_header[7:]
                logger.info(f"Authenticating with bearer token: {bearer_token[:10]}...")
                user = auth_provider.validate_token(bearer_token)
                if user:
                    logger.info(f"✓ Bearer token authentication successful: {user.username}")
                    return user
                else:
                    logger.error(f"Bearer token validation failed")
            
            # Fallback: API key in header  
            api_key_header = request.headers.get("x-api-key") or request.headers.get("X-API-Key")
            if api_key_header:
                logger.info(f"Authenticating with API key header: {api_key_header}")
                user = auth_provider.validate_api_key(api_key_header)
                if user:
                    logger.info(f"✓ API key header authentication successful: {user.username}")
                    return user
                else:
                    logger.error(f"API key header validation failed")
            
            # Fallback: Token in query params
            if token:
                logger.info(f"Authenticating with token query: {token[:10]}...")
                user = auth_provider.validate_token(token)
                if user:
                    logger.info(f"✓ Token query authentication successful: {user.username}")
                    return user
                else:
                    logger.error(f"Token query validation failed")
            
            logger.error("❌ All authentication methods failed")
            return None
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None


class TaskAccessControl:
    """Handles task access control"""
    
    @staticmethod
    def can_access_task(user: Optional[User], task_data: Dict[str, Any]) -> bool:
        """Check if user can access a specific task"""
        if not user:
            return False
        
        # Admins can access all tasks
        if Role.ADMIN in user.roles:
            return True
        
        # Users can access their own tasks
        task_user = task_data.get("user", "")
        if user.username == task_user:
            return True
        
        # Handle API key username format variations
        if user.username.startswith("apikey:") and task_user == "dev":
            return True
        
        return False


class SSEEventQueue(EventQueue):
    """Enhanced event queue for SSE broadcasting"""
    
    def __init__(self):
        super().__init__()
        self.subscribers: Dict[str, List[asyncio.Queue]] = {}
    
    def subscribe_to_task(self, task_id: str) -> asyncio.Queue:
        """Subscribe to events for a specific task"""
        if task_id not in self.subscribers:
            self.subscribers[task_id] = []
        
        subscriber_queue = asyncio.Queue()
        self.subscribers[task_id].append(subscriber_queue)
        logger.debug(f"New subscriber for task {task_id}, total: {len(self.subscribers[task_id])}")
        return subscriber_queue
    
    def unsubscribe_from_task(self, task_id: str, subscriber_queue: asyncio.Queue):
        """Unsubscribe from task events"""
        if task_id in self.subscribers:
            try:
                self.subscribers[task_id].remove(subscriber_queue)
                if not self.subscribers[task_id]:
                    del self.subscribers[task_id]
                logger.debug(f"Subscriber removed from task {task_id}")
            except ValueError:
                pass
    
    async def enqueue_event(self, event):
        """Override to broadcast events to subscribers"""
        await super().enqueue_event(event)
        
        # Broadcast to SSE subscribers
        task_id = getattr(event, 'taskId', None) or getattr(event, 'contextId', None)
        if task_id and task_id in self.subscribers:
            sse_event = self._convert_a2a_to_sse_event(event, task_id)
            await self._broadcast_to_subscribers(task_id, sse_event)
    
    async def _broadcast_to_subscribers(self, task_id: str, sse_event: SSEEvent):
        """Broadcast event to all subscribers of a task"""
        if task_id not in self.subscribers:
            return
        
        failed_subscribers = []
        for subscriber_queue in self.subscribers[task_id]:
            try:
                await subscriber_queue.put(sse_event)
            except Exception as e:
                logger.warning(f"Failed to send event to subscriber: {e}")
                failed_subscribers.append(subscriber_queue)
        
        # Remove failed subscribers
        for failed_queue in failed_subscribers:
            try:
                self.subscribers[task_id].remove(failed_queue)
            except ValueError:
                pass
    
    def _convert_a2a_to_sse_event(self, a2a_event, task_id: str) -> SSEEvent:
        """Convert A2A event to SSE event format"""
        event_type = "progress"
        data = {}
        
        if hasattr(a2a_event, 'state'):
            if a2a_event.state == TaskState.working:
                event_type = "progress"
                data = {"status": "working", "message": "Agent is processing your request..."}
            elif a2a_event.state == TaskState.completed:
                event_type = "completion"
                if hasattr(a2a_event, 'status') and hasattr(a2a_event.status, 'message'):
                    message_parts = a2a_event.status.message.parts
                    content = " ".join([part.root.text for part in message_parts if part.root.kind == "text"])
                    data = {"status": "completed", "result": content, "final": True}
            elif a2a_event.state == TaskState.failed:
                event_type = "error"
                error_msg = "Unknown error occurred"
                if hasattr(a2a_event, 'status') and hasattr(a2a_event.status, 'message'):
                    message_parts = a2a_event.status.message.parts
                    error_msg = " ".join([part.root.text for part in message_parts if part.root.kind == "text"])
                data = {"status": "error", "error": error_msg, "final": True}
        
        return SSEEvent(
            event=event_type,
            data=data,
            timestamp=datetime.utcnow(),
            task_id=task_id
        )


class EnhancedA2ATask(A2ATask):
    """A2A Task with enhanced SSE event emission"""
    
    def __init__(self, executor, context: RequestContext, event_queue: SSEEventQueue, 
                 stream_traces: bool = True, stream_costs: bool = True):
        super().__init__(executor, context, event_queue)
        self.stream_traces = stream_traces
        self.stream_costs = stream_costs
        self.task_start_time = datetime.utcnow()
    
    async def run(self):
        """Enhanced run with streaming events"""
        try:
            await self._emit_sse_event("progress", {
                "status": "starting",
                "message": "Initializing agent execution..."
            })
            
            await super().run()
            
            if self.stream_traces:
                await self._emit_trace_event()
            
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            await self._emit_sse_event("error", {"error": str(e), "final": True})
            raise
    
    async def _emit_sse_event(self, event_type: str, data: Dict[str, Any]):
        """Emit custom SSE event"""
        task_id = getattr(self.context, 'task_id', None)
        if not task_id:
            logger.warning("No task_id available for SSE event")
            return
            
        event = SSEEvent(
            event=event_type,
            data=data,
            timestamp=datetime.utcnow(),
            task_id=task_id
        )
        
        await self.event_queue._broadcast_to_subscribers(task_id, event)
    
    async def _emit_trace_event(self):
        """Emit trace information"""
        try:
            current_span = trace.get_current_span()
            span_context = current_span.get_span_context()
            
            await self._emit_sse_event("trace", {
                "trace_id": format(span_context.trace_id, '032x'),
                "span_id": format(span_context.span_id, '016x'),
                "duration_ms": (datetime.utcnow() - self.task_start_time).total_seconds() * 1000,
                "agent_role": getattr(self.executor, 'role_name', 'unknown')
            })
        except Exception as e:
            logger.warning(f"Failed to emit trace event: {e}")


class RequestContextFactory:
    """Factory for creating request contexts"""
    
    @staticmethod
    def create_context(task_id: str, context_id: str, message_text: str, user_principal: str) -> RequestContext:
        """Create a RequestContext for A2A framework"""
        message = Message(
            messageId=str(uuid.uuid4()),
            role=MessageRole.user,
            parts=[TextPart(text=message_text)]
        )
        
        # Create wrapper that mimics RequestContext
        class SimpleRequestContext:
            def __init__(self, task_id: str, context_id: str, message: Message, user_principal: str):
                self.task_id = task_id
                self.context_id = context_id
                self.message = message
                self.user_principal = user_principal
                
                # Try to copy methods from real RequestContext
                try:
                    real_context = RequestContext()
                    for attr_name in dir(real_context):
                        if not attr_name.startswith('_') and callable(getattr(real_context, attr_name)):
                            setattr(self, attr_name, getattr(real_context, attr_name))
                except Exception as e:
                    logger.warning(f"Could not create real RequestContext: {e}")
        
        return SimpleRequestContext(task_id, context_id, message, user_principal)


class TaskExecutionService:
    """Handles task execution with streaming"""
    
    def __init__(self, event_queue: SSEEventQueue):
        self.event_queue = event_queue
        self.context_factory = RequestContextFactory()
    
    async def submit_task(self, request: TaskSubmissionRequest, user: User) -> TaskSubmissionResponse:
        """Submit and start task execution"""
        task_id = str(uuid.uuid4())
        context_id = str(uuid.uuid4())
        
        try:
            # Create request context
            context = self.context_factory.create_context(
                task_id=task_id,
                context_id=context_id,
                message_text=request.message,
                user_principal=user.username
            )
            
            # Store task info
            task_data = {
                "task_id": task_id,
                "status": "submitted",
                "created_at": datetime.utcnow(),
                "agent_role": request.agent_role,
                "message_preview": request.message[:100] + "..." if len(request.message) > 100 else request.message,
                "user": user.username,
                "stream_traces": request.stream_traces,
                "stream_costs": request.stream_costs
            }
            active_tasks[task_id] = task_data
            
            logger.info(f"Task {task_id} submitted by {user.username}")
            
            # Start task execution asynchronously
            asyncio.create_task(self._execute_task(context, request.agent_role, request.stream_traces, request.stream_costs))
            
            return TaskSubmissionResponse(
                task_id=task_id,
                status="submitted",
                stream_url=f"/api/v1/streaming/tasks/{task_id}/stream",
                created_at=task_data["created_at"],
                agent_role=request.agent_role
            )
            
        except Exception as e:
            logger.error(f"Task submission failed for user {user.username}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to submit task: {str(e)}"
            )
    
    async def _execute_task(self, context: RequestContext, agent_role: str, stream_traces: bool, stream_costs: bool):
        """Execute task with streaming events"""
        task_id = getattr(context, 'task_id', None)
        if not task_id:
            logger.error("No task_id in context for execution")
            return
        
        try:
            # Update status
            if task_id in active_tasks:
                active_tasks[task_id]["status"] = "executing"
            
            # Send progress events
            await self._send_event(task_id, "progress", {
                "status": "initializing",
                "message": "Setting up agent..."
            })
            
            # Create and initialize executor
            executor = LangGraphA2AExecutor(role_name=agent_role)
            await executor.initialize()
            
            await self._send_event(task_id, "progress", {
                "status": "running",
                "message": "Agent is processing your request..."
            })
            
            # Create and execute enhanced task
            enhanced_task = EnhancedA2ATask(executor, context, self.event_queue, stream_traces, stream_costs)
            await enhanced_task.run()
            
            # Mark as completed
            if task_id in active_tasks:
                active_tasks[task_id]["status"] = "completed"
            
            await self._send_event(task_id, "completion", {
                "status": "completed",
                "message": "Task completed successfully",
                "final": True
            })
            
        except Exception as e:
            logger.error(f"Task execution failed for {task_id}: {e}")
            
            if task_id in active_tasks:
                active_tasks[task_id]["status"] = "failed"
                active_tasks[task_id]["error"] = str(e)
            
            await self._send_event(task_id, "error", {
                "error": str(e),
                "final": True
            })
    
    async def _send_event(self, task_id: str, event_type: str, data: Dict[str, Any]):
        """Send SSE event to subscribers"""
        event = SSEEvent(
            event=event_type,
            data=data,
            timestamp=datetime.utcnow(),
            task_id=task_id
        )
        
        await self.event_queue._broadcast_to_subscribers(task_id, event)
        
        # Update task status
        if task_id in active_tasks:
            if event_type == "completion":
                active_tasks[task_id]["status"] = "completed"
            elif event_type == "error":
                active_tasks[task_id]["status"] = "failed"
            elif event_type == "progress":
                active_tasks[task_id]["status"] = "executing"


class TaskListService:
    """Handles task listing and filtering"""
    
    def __init__(self, access_control: TaskAccessControl):
        self.access_control = access_control
    
    async def get_user_tasks(self, user: User) -> TaskListResponse:
        """Get tasks visible to user"""
        try:
            visible_tasks = []
            status_counts = {}
            
            for task_id, task_data in active_tasks.items():
                if self.access_control.can_access_task(user, task_data):
                    task_info = TaskInfo(
                        task_id=task_id,
                        status=task_data["status"],
                        created_at=task_data["created_at"],
                        agent_role=task_data["agent_role"],
                        message_preview=task_data["message_preview"],
                        user=task_data["user"]
                    )
                    visible_tasks.append(task_info)
                    
                    # Count statuses
                    status = task_data["status"]
                    status_counts[status] = status_counts.get(status, 0) + 1
            
            return TaskListResponse(
                tasks=visible_tasks,
                total_count=len(visible_tasks),
                status_counts=status_counts
            )
            
        except Exception as e:
            logger.error(f"Error retrieving tasks for user {user.username}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to retrieve task list"
            )


class SSEStreamService:
    """Handles SSE streaming for tasks"""
    
    def __init__(self, event_queue: SSEEventQueue, access_control: TaskAccessControl):
        self.event_queue = event_queue
        self.access_control = access_control
    
    async def create_event_stream(self, task_id: str, user: User) -> AsyncGenerator[str, None]:
        """Create SSE event stream for a task"""
        # Validate task access
        if task_id not in active_tasks:
            raise HTTPException(status_code=404, detail="Task not found")
        
        task_info = active_tasks[task_id]
        if not self.access_control.can_access_task(user, task_info):
            raise HTTPException(status_code=403, detail="Access denied to this task")
        
        subscriber_queue = self.event_queue.subscribe_to_task(task_id)
        
        try:
            # Send connection event
            initial_event = SSEEvent(
                event="connection",
                data={
                    "status": "connected",
                    "task_id": task_id,
                    "message": f"Streaming events for task {task_id}"
                },
                timestamp=datetime.utcnow(),
                task_id=task_id
            )
            yield f"data: {initial_event.json()}\n\n"
            
            # Check if task is already completed
            if task_info.get("status") in ["completed", "failed"]:
                final_event = SSEEvent(
                    event="completion" if task_info["status"] == "completed" else "error",
                    data={
                        "status": task_info["status"],
                        "message": f"Task already {task_info['status']}",
                        "error": task_info.get("error") if task_info["status"] == "failed" else None,
                        "final": True
                    },
                    timestamp=datetime.utcnow(),
                    task_id=task_id
                )
                yield f"data: {final_event.json()}\n\n"
                return
            
            # Stream events with timeout handling
            timeout_count = 0
            max_timeouts = 10  # 5 minutes of keepalives
            
            while timeout_count < max_timeouts:
                try:
                    event = await asyncio.wait_for(subscriber_queue.get(), timeout=30.0)
                    yield f"data: {event.json()}\n\n"
                    timeout_count = 0  # Reset on successful event
                    
                    if event.data.get("final", False):
                        break
                        
                except asyncio.TimeoutError:
                    timeout_count += 1
                    # Send keepalive
                    keepalive = SSEEvent(
                        event="keepalive",
                        data={
                            "timestamp": datetime.utcnow().isoformat(),
                            "timeout_count": timeout_count
                        },
                        timestamp=datetime.utcnow(),
                        task_id=task_id
                    )
                    yield f"data: {keepalive.json()}\n\n"
                    
                    # Check if task completed while waiting
                    current_status = active_tasks.get(task_id, {}).get("status")
                    if current_status in ["completed", "failed"]:
                        final_event = SSEEvent(
                            event="completion" if current_status == "completed" else "error",
                            data={
                                "status": current_status,
                                "message": f"Task {current_status}",
                                "final": True
                            },
                            timestamp=datetime.utcnow(),
                            task_id=task_id
                        )
                        yield f"data: {final_event.json()}\n\n"
                        break
                    
                except Exception as e:
                    logger.error(f"Stream error for task {task_id}: {e}")
                    error_event = SSEEvent(
                        event="error",
                        data={"error": f"Stream error: {str(e)}", "final": True},
                        timestamp=datetime.utcnow(),
                        task_id=task_id
                    )
                    yield f"data: {error_event.json()}\n\n"
                    break
            
            # Handle timeout
            if timeout_count >= max_timeouts:
                timeout_event = SSEEvent(
                    event="error",
                    data={"error": "Stream timeout - no events received", "final": True},
                    timestamp=datetime.utcnow(),
                    task_id=task_id
                )
                yield f"data: {timeout_event.json()}\n\n"
                
        finally:
            self.event_queue.unsubscribe_from_task(task_id, subscriber_queue)


class StreamingRouteHandler:
    """Main handler for streaming routes"""
    
    def __init__(self):
        self.event_queue = SSEEventQueue()
        self.auth_service = TaskAuthenticationService()
        self.access_control = TaskAccessControl()
        self.execution_service = TaskExecutionService(self.event_queue)
        self.list_service = TaskListService(self.access_control)
        self.stream_service = SSEStreamService(self.event_queue, self.access_control)
    
    async def submit_task(self, request: TaskSubmissionRequest, user: User) -> TaskSubmissionResponse:
        """Handle task submission"""
        if Permission.SUBMIT_TASK not in user.permissions:
            raise HTTPException(status_code=403, detail="Permission denied: SUBMIT_TASK required")
        
        return await self.execution_service.submit_task(request, user)
    
    async def list_tasks(self, user: User) -> TaskListResponse:
        """Handle task listing"""
        if Permission.VIEW_TASK not in user.permissions:
            raise HTTPException(status_code=403, detail="Permission denied: VIEW_TASK required")
        
        return await self.list_service.get_user_tasks(user)
    
    async def get_task_details(self, task_id: str, user: User) -> Dict[str, Any]:
        """Handle task detail retrieval"""
        if Permission.VIEW_TASK not in user.permissions:
            raise HTTPException(status_code=403, detail="Permission denied: VIEW_TASK required")
        
        if task_id not in active_tasks:
            raise HTTPException(status_code=404, detail="Task not found")
        
        task_data = active_tasks[task_id]
        if not self.access_control.can_access_task(user, task_data):
            raise HTTPException(status_code=403, detail="Access denied to this task")
        
        return task_data


def create_streaming_router() -> APIRouter:
    """Create streaming router with clean class-based handlers"""
    router = APIRouter()
    handler = StreamingRouteHandler()
    
    @router.post("/tasks/submit", response_model=TaskSubmissionResponse)
    async def submit_streaming_task(
        request: TaskSubmissionRequest,
        current_user: User = Depends(require_authentication)
    ):
        """Submit a task for streaming execution"""
        return await handler.submit_task(request, current_user)
    
    # CRITICAL: /tasks/stream MUST come BEFORE /tasks/{task_id}/stream
    @router.get("/tasks/stream")
    async def stream_task_list_updates(
        request: Request,
        api_key: Optional[str] = None,
        token: Optional[str] = None
    ):
        """Stream task list updates via SSE - USE MIDDLEWARE AUTH"""
        
        logger.info(f"DEBUG: ENDPOINT REACHED: /tasks/stream")
        
        # Use the user that middleware already authenticated
        user = getattr(request.state, 'authenticated_user', None)
        
        logger.info(f"DEBUG: Middleware authenticated user: {user.username if user else None}")
        
        if not user:
            logger.error(f"DEBUG: No authenticated user from middleware")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        logger.info(f"DEBUG: User authenticated: {user.username}")
        
        # Check permissions
        if Permission.VIEW_TASK not in user.permissions:
            logger.error(f"DEBUG: Permission check failed for user: {user.username}")
            raise HTTPException(status_code=403, detail="Permission denied: VIEW_TASK required")
        
        logger.info(f"DEBUG: Permission check passed")
        logger.info(f"DEBUG: Starting task list stream for user: {user.username}")
        
        async def task_list_generator():
            try:
                logger.info(f"DEBUG: Generator started")
                # Send initial task list
                initial_task_list = await handler.list_tasks(user)
                logger.info(f"DEBUG: Got initial task list: {len(initial_task_list.tasks)} tasks")
                yield f"data: {json.dumps(initial_task_list.dict(), default=str)}\n\n"
                
                # Track last known state
                last_task_data = dict(active_tasks)
                
                while True:
                    await asyncio.sleep(2)  # Check every 2 seconds
                    
                    # Get current task list
                    current_task_list = await handler.list_tasks(user)
                    current_task_data = dict(active_tasks)
                    
                    # Check if anything changed
                    tasks_changed = False
                    
                    # Check for new tasks, removed tasks, or status changes
                    if len(current_task_data) != len(last_task_data):
                        tasks_changed = True
                    else:
                        # Check for status changes in existing tasks
                        for task_id, task_info in current_task_data.items():
                            if (task_id not in last_task_data or 
                                task_info.get('status') != last_task_data.get(task_id, {}).get('status')):
                                tasks_changed = True
                                break
                    
                    # Send update if something changed
                    if tasks_changed:
                        logger.info(f"DEBUG: Tasks changed, sending update")
                        yield f"data: {json.dumps(current_task_list.dict(), default=str)}\n\n"
                        last_task_data = current_task_data
                        
            except Exception as e:
                logger.error(f"DEBUG: Generator error: {e}")
                import traceback
                logger.error(f"DEBUG: Generator traceback: {traceback.format_exc()}")
                error_data = {"error": f"Stream error: {str(e)}"}
                yield f"data: {json.dumps(error_data)}\n\n"
        
        logger.info(f"DEBUG: Returning StreamingResponse")
        return StreamingResponse(
            task_list_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    @router.get("/tasks/{task_id}/stream")
    async def stream_task_events(
        task_id: str,
        request: Request,
        api_key: Optional[str] = None,
        token: Optional[str] = None
    ):
        """Stream task execution events via SSE - USE MIDDLEWARE AUTH"""
        
        logger.info(f"DEBUG: Individual task stream endpoint reached for task: {task_id}")
        
        # Use the user that middleware already authenticated
        user = getattr(request.state, 'authenticated_user', None)
        
        logger.info(f"DEBUG: Middleware authenticated user: {user.username if user else None}")
        
        if not user:
            logger.error(f"DEBUG: No authenticated user from middleware for task {task_id}")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        logger.info(f"DEBUG: User authenticated for task {task_id}: {user.username}")
        
        # Check permissions
        if Permission.VIEW_TASK not in user.permissions:
            logger.error(f"DEBUG: Permission check failed for user: {user.username}")
            raise HTTPException(status_code=403, detail="Permission denied: VIEW_TASK required")
        
        logger.info(f"DEBUG: Permission check passed for task {task_id}")
        logger.info(f"DEBUG: Starting individual task stream for task {task_id}, user: {user.username}")
        
        # Create stream using the authenticated user
        event_generator = handler.stream_service.create_event_stream(task_id, user)
        
        return StreamingResponse(
            event_generator,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    
    @router.get("/tasks", response_model=TaskListResponse)
    async def list_tasks(current_user: User = Depends(require_authentication)):
        """List tasks visible to current user"""
        return await handler.list_tasks(current_user)
    
    @router.get("/tasks/{task_id}")
    async def get_task_details(
        task_id: str,
        current_user: User = Depends(require_authentication)
    ):
        """Get detailed task information"""
        return await handler.get_task_details(task_id, current_user)
    
    # Debug endpoints for troubleshooting
    @router.get("/test-middleware-auth")
    async def test_middleware_auth(request: Request):
        """Test if middleware auth works"""
        logger.info(f"TEST: Endpoint reached!")
        
        user = getattr(request.state, 'authenticated_user', None)
        logger.info(f"TEST: Middleware user: {user.username if user else None}")
        
        if user:
            return {
                "status": "success", 
                "user": user.username,
                "method": "middleware_auth",
                "permissions": [p.value for p in user.permissions]
            }
        else:
            return {"status": "no_user", "message": "No authenticated user from middleware"}
    
    @router.get("/debug/auth-config")
    async def debug_auth_config():
        """Debug authentication configuration"""
        try:
            config_info = {
                "api_key_header_name": auth_provider.config.get("API_KEY_HEADER", "X-API-Key"),
                "expected_api_key": auth_provider.config.get("DEFAULT_DEV_API_KEY", "NOT_SET"),
                "api_keys_in_database": list(auth_provider.api_keys_db.keys()),
                "test_api_key_validation": None
            }
            
            # Test the API key that's in the database
            for api_key in auth_provider.api_keys_db.keys():
                user = auth_provider.validate_api_key(api_key)
                if user:
                    config_info["test_api_key_validation"] = {
                        "api_key": api_key,
                        "user": user.username,
                        "roles": [r.value for r in user.roles],
                        "permissions": [p.value for p in user.permissions]
                    }
                    break
            
            return config_info
            
        except Exception as e:
            return {"error": str(e)}

    @router.get("/debug/test-key")
    async def test_specific_key(api_key: str):
        """Test a specific API key"""
        try:
            logger.info(f"Testing API key: {api_key}")
            
            # Check if key exists in database
            exists_in_db = api_key in auth_provider.api_keys_db
            
            # Try to validate it
            user = auth_provider.validate_api_key(api_key)
            
            return {
                "api_key": api_key,
                "exists_in_database": exists_in_db,
                "validation_result": user.username if user else None,
                "all_keys_in_db": list(auth_provider.api_keys_db.keys())
            }
            
        except Exception as e:
            return {"error": str(e), "api_key": api_key}

    @router.get("/debug/middleware-test")
    async def test_middleware_auth_detailed(
        request: Request,
        api_key: Optional[str] = None,
        token: Optional[str] = None
    ):
        """Test if middleware is extracting auth correctly"""
        
        # Check what the middleware set
        middleware_user = getattr(request.state, 'authenticated_user', None)
        
        # Try direct auth
        from api.auth import get_current_user
        direct_user = await get_current_user(
            token=token,
            api_key=api_key
        )
        
        return {
            "middleware_extracted_user": middleware_user.username if middleware_user else None,
            "direct_auth_user": direct_user.username if direct_user else None,
            "query_api_key": api_key,
            "query_token": token,
            "header_auth": request.headers.get("authorization"),
            "header_api_key": request.headers.get("X-API-Key"),
            "all_headers": {k: v for k, v in request.headers.items() if 'api' in k.lower() or 'auth' in k.lower()}
        }
        
    return router


# Export the router
router = create_streaming_router()
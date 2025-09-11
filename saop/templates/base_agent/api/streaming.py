# api/streaming.py
"""
Server-Sent Events (SSE) streaming endpoints for real-time task execution.
Fixed version that properly handles RequestContext properties.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.auth import require_authentication, User, Permission, require_permission
from agent2agent.a2a_tasks import A2ATask
from langgraph.langgraph_executor import LangGraphA2AExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.types import Message, TextPart, Role, TaskState
from telemetry.langgraph_trace_utils import extract_llm_metadata
from opentelemetry import trace

# Global task registry
active_tasks: Dict[str, Dict[str, Any]] = {}

router = APIRouter()

# Pydantic models
class TaskSubmissionRequest(BaseModel):
    message: str
    agent_role: Optional[str] = "general_support"
    stream_traces: bool = True
    stream_costs: bool = True

class TaskInfo(BaseModel):
    task_id: str
    status: str
    created_at: datetime
    agent_role: str
    message_preview: str

class SSEEvent(BaseModel):
    event: str  # 'progress', 'trace', 'cost', 'completion', 'error'
    data: Dict[str, Any]
    timestamp: datetime
    task_id: str

# Enhanced Event Queue for SSE
class SSEEventQueue(EventQueue):
    """Event queue that can broadcast to SSE subscribers"""
    
    def __init__(self):
        super().__init__()
        self.subscribers: Dict[str, List[asyncio.Queue]] = {}
    
    def subscribe_to_task(self, task_id: str) -> asyncio.Queue:
        """Subscribe to events for a specific task"""
        if task_id not in self.subscribers:
            self.subscribers[task_id] = []
        
        subscriber_queue = asyncio.Queue()
        self.subscribers[task_id].append(subscriber_queue)
        return subscriber_queue
    
    def unsubscribe_from_task(self, task_id: str, subscriber_queue: asyncio.Queue):
        """Unsubscribe from task events"""
        if task_id in self.subscribers:
            try:
                self.subscribers[task_id].remove(subscriber_queue)
                if not self.subscribers[task_id]:
                    del self.subscribers[task_id]
            except ValueError:
                pass
    
    async def enqueue_event(self, event):
        """Override to broadcast events to subscribers"""
        await super().enqueue_event(event)
        
        # Broadcast to SSE subscribers
        task_id = getattr(event, 'taskId', None) or getattr(event, 'contextId', None)
        if task_id and task_id in self.subscribers:
            sse_event = self._convert_a2a_to_sse_event(event, task_id)
            
            for subscriber_queue in self.subscribers[task_id].copy():
                try:
                    await subscriber_queue.put(sse_event)
                except:
                    self.subscribers[task_id].remove(subscriber_queue)
    
    def _convert_a2a_to_sse_event(self, a2a_event, task_id: str) -> SSEEvent:
        """Convert A2A event to SSE event format"""
        event_type = "progress"
        data = {}
        
        if hasattr(a2a_event, 'state'):
            if a2a_event.state == TaskState.working:
                event_type = "progress"
                data = {
                    "status": "working",
                    "message": "Agent is processing your request..."
                }
            elif a2a_event.state == TaskState.completed:
                event_type = "completion"
                if hasattr(a2a_event, 'status') and hasattr(a2a_event.status, 'message'):
                    message_parts = a2a_event.status.message.parts
                    content = " ".join([part.root.text for part in message_parts if part.root.kind == "text"])
                    data = {
                        "status": "completed",
                        "result": content,
                        "final": True
                    }
            elif a2a_event.state == TaskState.failed:
                event_type = "error"
                error_msg = "Unknown error occurred"
                if hasattr(a2a_event, 'status') and hasattr(a2a_event.status, 'message'):
                    message_parts = a2a_event.status.message.parts
                    error_msg = " ".join([part.root.text for part in message_parts if part.root.kind == "text"])
                data = {
                    "status": "error",
                    "error": error_msg,
                    "final": True
                }
        
        return SSEEvent(
            event=event_type,
            data=data,
            timestamp=datetime.utcnow(),
            task_id=task_id
        )

# Global instance
sse_event_queue = SSEEventQueue()

# Enhanced A2A Task with streaming support
class EnhancedA2ATask(A2ATask):
    """Your existing A2ATask but with SSE event emission"""
    
    def __init__(self, executor, context: RequestContext, event_queue: SSEEventQueue, 
                 stream_traces: bool = True, stream_costs: bool = True):
        super().__init__(executor, context, event_queue)
        self.stream_traces = stream_traces
        self.stream_costs = stream_costs
        self.task_start_time = datetime.utcnow()
    
    async def run(self):
        """Enhanced run with streaming events"""
        try:
            # Send additional streaming events
            await self._emit_sse_event("progress", {
                "status": "starting",
                "message": "Initializing agent execution..."
            })
            
            # Call parent run method to preserve existing logic
            await super().run()
            
            # Emit cost/trace events after completion
            if self.stream_traces:
                await self._emit_trace_event()
            
        except Exception as e:
            await self._emit_sse_event("error", {
                "error": str(e),
                "final": True
            })
            raise
    
    async def _emit_sse_event(self, event_type: str, data: Dict[str, Any]):
        """Emit custom SSE event"""
        # Get task_id from context, with fallback
        task_id = getattr(self.context, 'task_id', None)
        if not task_id:
            print("Warning: No task_id available for SSE event")
            return
            
        event = SSEEvent(
            event=event_type,
            data=data,
            timestamp=datetime.utcnow(),
            task_id=task_id
        )
        
        # Send to SSE subscribers
        if task_id in self.event_queue.subscribers:
            for subscriber_queue in self.event_queue.subscribers[task_id].copy():
                try:
                    await subscriber_queue.put(event)
                except:
                    self.event_queue.subscribers[task_id].remove(subscriber_queue)
    
    async def _emit_trace_event(self):
        """Emit trace information"""
        current_span = trace.get_current_span()
        span_context = current_span.get_span_context()
        
        await self._emit_sse_event("trace", {
            "trace_id": format(span_context.trace_id, '032x'),
            "span_id": format(span_context.span_id, '016x'),
            "duration_ms": (datetime.utcnow() - self.task_start_time).total_seconds() * 1000,
            "agent_role": getattr(self.executor, 'role_name', 'unknown')
        })

# Simple RequestContext wrapper that stores what we need
class SimpleRequestContext:
    """Wrapper for RequestContext that ensures we have the properties we need"""
    
    def __init__(self, task_id: str, context_id: str, message: Message, user_principal: str):
        self.task_id = task_id
        self.context_id = context_id
        self.message = message
        self.user_principal = user_principal
        
        # Try to create a real RequestContext and copy its methods
        try:
            self._real_context = RequestContext()
            # Copy any methods from the real context
            for attr_name in dir(self._real_context):
                if not attr_name.startswith('_') and callable(getattr(self._real_context, attr_name)):
                    setattr(self, attr_name, getattr(self._real_context, attr_name))
        except:
            self._real_context = None
            print("Could not create real RequestContext, using simple wrapper")

# Helper function to create proper RequestContext
def create_request_context(task_id: str, context_id: str, message_text: str, user_principal: str) -> RequestContext:
    """Create a RequestContext that works with your A2A framework"""
    
    # Create the message
    message = Message(
        messageId=str(uuid.uuid4()),
        role=Role.user,
        parts=[TextPart(text=message_text)]
    )
    
    print(f"Creating RequestContext for task_id: {task_id}")
    
    # Since the A2A framework's RequestContext doesn't accept the parameters we need,
    # we'll use our wrapper that ensures we have the required properties
    context = SimpleRequestContext(
        task_id=task_id,
        context_id=context_id,
        message=message,
        user_principal=user_principal
    )
    
    print(f"Created context with task_id: {context.task_id}")
    return context

# API Endpoints
@router.post("/tasks/submit", response_model=Dict[str, str])
async def submit_streaming_task(
    request: TaskSubmissionRequest,
    current_user: User = Depends(require_permission(Permission.SUBMIT_TASK))
):
    """Submit a task for streaming execution"""
    task_id = str(uuid.uuid4())
    context_id = str(uuid.uuid4())
    
    try:
        # Create request context using the helper function
        context = create_request_context(
            task_id=task_id,
            context_id=context_id,
            message_text=request.message,
            user_principal=current_user.username
        )
        
        # Store task info
        active_tasks[task_id] = {
            "task_id": task_id,
            "status": "submitted",
            "created_at": datetime.utcnow(),
            "agent_role": request.agent_role,
            "message_preview": request.message[:100] + "..." if len(request.message) > 100 else request.message,
            "user": current_user.username,
            "stream_traces": request.stream_traces,
            "stream_costs": request.stream_costs
        }
        
        print(f"Task {task_id} submitted and stored in active_tasks")
        
        # Start task execution
        asyncio.create_task(execute_streaming_task(
            context, request.agent_role, request.stream_traces, request.stream_costs
        ))
        
        return {
            "task_id": task_id,
            "status": "submitted",
            "stream_url": f"/api/v1/streaming/tasks/{task_id}/stream"
        }
        
    except Exception as e:
        print(f"Error in submit_streaming_task: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to submit task: {str(e)}")

async def execute_streaming_task(
    context: RequestContext, 
    agent_role: str,
    stream_traces: bool,
    stream_costs: bool
):
    """Execute task with streaming"""
    task_id = getattr(context, 'task_id', None)
    
    if not task_id:
        print("Error: No task_id in context")
        return
    
    print(f"Starting execution for task {task_id}")
    
    try:
        if task_id in active_tasks:
            active_tasks[task_id]["status"] = "executing"
        
        # Send initial progress event
        await send_sse_event(task_id, "progress", {
            "status": "initializing",
            "message": "Setting up agent..."
        })
        
        # Create executor
        executor = LangGraphA2AExecutor(role_name=agent_role)
        await executor.initialize()
        
        await send_sse_event(task_id, "progress", {
            "status": "running",
            "message": "Agent is processing your request..."
        })
        
        # Create enhanced task
        enhanced_task = EnhancedA2ATask(
            executor, context, sse_event_queue, stream_traces, stream_costs
        )
        
        # Execute
        await enhanced_task.run()
        
        if task_id in active_tasks:
            active_tasks[task_id]["status"] = "completed"
        
        await send_sse_event(task_id, "completion", {
            "status": "completed",
            "message": "Task completed successfully",
            "final": True
        })
        
    except Exception as e:
        print(f"Error in execute_streaming_task: {e}")
        import traceback
        traceback.print_exc()
        
        if task_id in active_tasks:
            active_tasks[task_id]["status"] = "failed"
            active_tasks[task_id]["error"] = str(e)
        
        await send_sse_event(task_id, "error", {
            "error": str(e),
            "final": True
        })

async def send_sse_event(task_id: str, event_type: str, data: Dict[str, Any]):
    """Helper function to send SSE events"""
    if task_id in sse_event_queue.subscribers:
        event = SSEEvent(
            event=event_type,
            data=data,
            timestamp=datetime.utcnow(),
            task_id=task_id
        )
        
        for subscriber_queue in sse_event_queue.subscribers[task_id].copy():
            try:
                await subscriber_queue.put(event)
            except:
                sse_event_queue.subscribers[task_id].remove(subscriber_queue)

@router.get("/tasks/{task_id}/stream")
async def stream_task_events(
    task_id: str,
    request: Request,
    current_user: User = Depends(require_permission(Permission.VIEW_TASK))
):
    """Stream task execution events via SSE"""
    
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_info = active_tasks[task_id]
    
    # Check access
    from api.auth import Role as UserRole
    if (UserRole.ADMIN not in current_user.roles and 
        task_info.get("user") != current_user.username):
        raise HTTPException(status_code=403, detail="Access denied")
    
    async def event_stream() -> AsyncGenerator[str, None]:
        subscriber_queue = sse_event_queue.subscribe_to_task(task_id)
        
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
            
            # Stream events with shorter timeout
            timeout_count = 0
            max_timeouts = 10  # Allow 10 timeouts (5 minutes) before closing
            
            while timeout_count < max_timeouts:
                try:
                    event = await asyncio.wait_for(subscriber_queue.get(), timeout=30.0)
                    yield f"data: {event.json()}\n\n"
                    timeout_count = 0  # Reset timeout count on successful event
                    
                    if event.data.get("final", False):
                        break
                        
                except asyncio.TimeoutError:
                    timeout_count += 1
                    # Keepalive
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
                    
                    # Check if task completed while we were waiting
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
                    error_event = SSEEvent(
                        event="error",
                        data={"error": f"Stream error: {str(e)}", "final": True},
                        timestamp=datetime.utcnow(),
                        task_id=task_id
                    )
                    yield f"data: {error_event.json()}\n\n"
                    break
            
            # If we timed out too many times, send a final message
            if timeout_count >= max_timeouts:
                timeout_event = SSEEvent(
                    event="error",
                    data={"error": "Stream timeout - no events received", "final": True},
                    timestamp=datetime.utcnow(),
                    task_id=task_id
                )
                yield f"data: {timeout_event.json()}\n\n"
                    
        finally:
            sse_event_queue.unsubscribe_from_task(task_id, subscriber_queue)
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

@router.get("/tasks", response_model=List[TaskInfo])
async def list_tasks(
    current_user: User = Depends(require_permission(Permission.VIEW_TASK))
):
    """List tasks visible to current user"""
    from api.auth import Role as UserRole
    
    visible_tasks = []
    for task_id, task_data in active_tasks.items():
        if (UserRole.ADMIN in current_user.roles or 
            task_data.get("user") == current_user.username):
            
            visible_tasks.append(TaskInfo(
                task_id=task_id,
                status=task_data["status"],
                created_at=task_data["created_at"],
                agent_role=task_data["agent_role"],
                message_preview=task_data["message_preview"]
            ))
    
    return visible_tasks

@router.get("/tasks/{task_id}")
async def get_task_details(
    task_id: str,
    current_user: User = Depends(require_permission(Permission.VIEW_TASK))
):
    """Get detailed task information"""
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_data = active_tasks[task_id]
    
    # Check access
    from api.auth import Role as UserRole
    if (UserRole.ADMIN not in current_user.roles and 
        task_data.get("user") != current_user.username):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return task_data
import asyncio
import uuid
from typing import Optional, List

from a2a.types import (
    Message,
    TextPart,
    TaskStatusUpdateEvent,
    TaskStatus,
    TaskState,
    Role
)
from a2a.server.events.event_queue import EventQueue
from a2a.server.request_handlers.request_handler import RequestHandler

from langgraph_tool_wrapper import create_agent
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool

class LangGraphA2AExecutor:
    def __init__(self, event_queue: EventQueue):
        self.event_queue = event_queue
        self.graph = None  # will be set at startup
        self._tools: List[BaseTool] = []

    @property
    def tools(self) -> List[BaseTool]:
        return self._tools

    async def initialize(self):
        """
        Initialize the LangGraph agent and discover tools.
        """
        # Call create_agent, which now returns both the graph and the tools
        graph, tools = await create_agent()
        self.graph = graph
        self._tools = tools
        
        # Print the discovered tools here
        print(f"✅ LangGraphA2AExecutor has access to the following tools: {[tool.name for tool in self._tools]}")

    async def execute(self, request: RequestHandler, queue: EventQueue):
        # Determine the contextId from the request.message. It might be None for a new task.
        context_id = request.message.context_id or request.task_id
        
        if not request.message or not request.message.parts:
            failed_event = TaskStatusUpdateEvent(
                contextId=context_id,
                state=TaskState.failed,
                status=TaskStatus(
                    state=TaskState.failed,
                    message=Message(
                        messageId=str(uuid.uuid4()),
                        role=Role.agent,
                        parts=[TextPart(text="No text content found in the message.")]
                    ),
                ),
                taskId=request.task_id,
                final=True,
            )
            await queue.enqueue_event(failed_event)
            return

        # Correctly extract the user message text by checking the 'kind'
        user_text = ""
        for part in request.message.parts:
            print('PARTS: ', request.message.parts)
            if part.root.kind == "text":
                user_text += part.root.text

        if not user_text:
            failed_event = TaskStatusUpdateEvent(
                contextId=context_id,
                state=TaskState.failed,
                status=TaskStatus(
                    state=TaskState.failed,
                    message=Message(
                        messageId=str(uuid.uuid4()),
                        role=Role.agent,
                        parts=[TextPart(text="No text content found in the message.")]
                    ),
                ),
                taskId=request.task_id,
                final=True,
            )
            await queue.enqueue_event(failed_event)
            return

        try:
            # Send message into LangGraph
            response = await self.graph.ainvoke(
                {"messages": [HumanMessage(content=user_text)]}
            )
            agent_reply = response["messages"][-1].content
            print("AGENT REPLY:", agent_reply)

            success_event = TaskStatusUpdateEvent(
                contextId=context_id,
                state=TaskState.completed,
                status=TaskStatus(
                    state=TaskState.completed,
                    message=Message(
                        messageId=str(uuid.uuid4()),
                        role=Role.agent,
                        parts=[TextPart(text=agent_reply)]
                    ),
                ),
                taskId=request.task_id,
                final=True,
            )
            await queue.enqueue_event(success_event)

        except Exception as e:
            error_event = TaskStatusUpdateEvent(
                contextId=context_id,
                state=TaskState.failed,
                status=TaskStatus(
                    state=TaskState.failed,
                    message=Message(
                        messageId=str(uuid.uuid4()),
                        role=Role.agent,
                        parts=[TextPart(text=f"Execution error: {e}")]
                    )
                ),
                taskId=request.task_id,
                final=True,
            )
            await queue.enqueue_event(error_event)

    async def cancel(self, task_id: str, queue: EventQueue):
        """
        Cancel a task and enqueue a failed TaskStatusUpdateEvent.
        """
        cancel_event = TaskStatusUpdateEvent(
            contextId=task_id,
            state=TaskState.failed,
            status=TaskStatus(
                state=TaskState.failed,
                message=Message(
                    messageId=str(uuid.uuid4()),
                    role=Role.agent,
                    parts=[TextPart(text="Task was cancelled.")]
                )
            ),
            taskId=task_id,
            final=True,
        )
        await queue.enqueue_event(cancel_event)
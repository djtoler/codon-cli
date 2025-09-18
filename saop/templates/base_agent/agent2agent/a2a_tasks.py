# a2a_task.py

import asyncio
import uuid
from typing import Optional, List, cast
from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.types import (
    Message,
    TextPart,
    TaskStatusUpdateEvent,
    TaskStatus,
    TaskState,
    Role
)
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

class A2ATask:
    def __init__(self, executor: AgentExecutor, context: RequestContext, event_queue: EventQueue):
        self.executor = executor
        self.context = context
        self.event_queue = event_queue

    async def run(self):
        user_text = "".join(part.root.text for part in self.context.message.parts if part.root.kind == "text")

        try:
            working_event = TaskStatusUpdateEvent(
                contextId=self.context.context_id,
                state=TaskState.working,
                status=TaskStatus(
                    state=TaskState.working,
                    message=Message(
                        messageId=str(uuid.uuid4()),
                        role=Role.agent,
                        parts=[TextPart(text="Thinking...")]
                    )
                ),
                taskId=self.context.task_id,
                final=False,
            )
            await self.event_queue.enqueue_event(working_event)

            # Let the agent run and return its final, unparsed output.
            final_response = await self.executor._run_agent(user_text)
            
            # Get the final message from the graph's output
            final_agent_message = final_response['result']

            # Convert to an A2A Message without any custom synthesis logic
            synthesized_text = ""
            if isinstance(final_agent_message, BaseMessage):
                synthesized_text = final_agent_message.content
            else:
                # Fallback for unexpected output types
                synthesized_text = str(final_agent_message)

            final_a2a_message = Message(
                messageId=str(uuid.uuid4()),
                role=Role.agent,
                parts=[TextPart(text=synthesized_text)]
            )
            
            success_event = TaskStatusUpdateEvent(
                contextId=self.context.context_id,
                state=TaskState.completed,
                status=TaskStatus(
                    state=TaskState.completed,
                    message=final_a2a_message,
                ),
                taskId=self.context.task_id,
                final=True,
            )
            await self.event_queue.enqueue_event(success_event)
            print("FINAL RESPONSE: ", final_response)
            return final_response
            
        except Exception as e:
            print(f"An unexpected error occurred in executor: {e}")
            error_event = TaskStatusUpdateEvent(
                contextId=self.context.context_id,
                state=TaskState.failed,
                status=TaskStatus(
                    state=TaskState.failed,
                    message=Message(
                        messageId=str(uuid.uuid4()),
                        role=Role.agent,
                        parts=[TextPart(text=f"Execution error: {e}")]
                    )
                ),
                taskId=self.context.task_id,
                final=True,
            )
            await self.event_queue.enqueue_event(error_event)
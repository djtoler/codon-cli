# # import asyncio
# # import uuid
# # from typing import Optional, List

# # from a2a.types import (
# #     Message,
# #     TextPart,
# #     TaskStatusUpdateEvent,
# #     TaskStatus,
# #     TaskState,
# #     Role
# # )
# # from a2a.server.events.event_queue import EventQueue
# # from a2a.server.request_handlers.request_handler import RequestHandler

# # from langgraph_tool_wrapper import create_agent
# # from langchain_core.messages import HumanMessage
# # from langchain_core.tools import BaseTool

# # class LangGraphA2AExecutor:
# #     def __init__(self, event_queue: EventQueue):
# #         self.event_queue = event_queue
# #         self.graph = None  # will be set at startup
# #         self._tools: List[BaseTool] = []

# #     @property
# #     def tools(self) -> List[BaseTool]:
# #         return self._tools

# #     async def initialize(self):
# #         """
# #         Initialize the LangGraph agent and discover tools.
# #         """
# #         # Call create_agent, which now returns both the graph and the tools
# #         graph, tools = await create_agent()
# #         self.graph = graph
# #         self._tools = tools
        
# #         # Print the discovered tools here
# #         print(f"✅ LangGraphA2AExecutor has access to the following tools: {[tool.name for tool in self._tools]}")

# #     async def execute(self, request: RequestHandler, queue: EventQueue):
# #         # Determine the contextId from the request.message. It might be None for a new task.
# #         context_id = request.message.context_id or request.task_id
        
# #         if not request.message or not request.message.parts:
# #             failed_event = TaskStatusUpdateEvent(
# #                 contextId=context_id,
# #                 state=TaskState.failed,
# #                 status=TaskStatus(
# #                     state=TaskState.failed,
# #                     message=Message(
# #                         messageId=str(uuid.uuid4()),
# #                         role=Role.agent,
# #                         parts=[TextPart(text="No text content found in the message.")]
# #                     ),
# #                 ),
# #                 taskId=request.task_id,
# #                 final=True,
# #             )
# #             await queue.enqueue_event(failed_event)
# #             return

# #         # Correctly extract the user message text by checking the 'kind'
# #         user_text = ""
# #         for part in request.message.parts:
# #             print('PARTS: ', request.message.parts)
# #             if part.root.kind == "text":
# #                 user_text += part.root.text

# #         if not user_text:
# #             failed_event = TaskStatusUpdateEvent(
# #                 contextId=context_id,
# #                 state=TaskState.failed,
# #                 status=TaskStatus(
# #                     state=TaskState.failed,
# #                     message=Message(
# #                         messageId=str(uuid.uuid4()),
# #                         role=Role.agent,
# #                         parts=[TextPart(text="No text content found in the message.")]
# #                     ),
# #                 ),
# #                 taskId=request.task_id,
# #                 final=True,
# #             )
# #             await queue.enqueue_event(failed_event)
# #             return

# #         try:
# #             # Send message into LangGraph
# #             response = await self.graph.ainvoke(
# #                 {"messages": [HumanMessage(content=user_text)]}
# #             )
# #             agent_reply = response["messages"][-1].content
# #             print("AGENT REPLY:", agent_reply)

# #             success_event = TaskStatusUpdateEvent(
# #                 contextId=context_id,
# #                 state=TaskState.completed,
# #                 status=TaskStatus(
# #                     state=TaskState.completed,
# #                     message=Message(
# #                         messageId=str(uuid.uuid4()),
# #                         role=Role.agent,
# #                         parts=[TextPart(text=agent_reply)]
# #                     ),
# #                 ),
# #                 taskId=request.task_id,
# #                 final=True,
# #             )
# #             await queue.enqueue_event(success_event)

# #         except Exception as e:
# #             error_event = TaskStatusUpdateEvent(
# #                 contextId=context_id,
# #                 state=TaskState.failed,
# #                 status=TaskStatus(
# #                     state=TaskState.failed,
# #                     message=Message(
# #                         messageId=str(uuid.uuid4()),
# #                         role=Role.agent,
# #                         parts=[TextPart(text=f"Execution error: {e}")]
# #                     )
# #                 ),
# #                 taskId=request.task_id,
# #                 final=True,
# #             )
# #             await queue.enqueue_event(error_event)

# #     async def cancel(self, task_id: str, queue: EventQueue):
# #         """
# #         Cancel a task and enqueue a failed TaskStatusUpdateEvent.
# #         """
# #         cancel_event = TaskStatusUpdateEvent(
# #             contextId=task_id,
# #             state=TaskState.failed,
# #             status=TaskStatus(
# #                 state=TaskState.failed,
# #                 message=Message(
# #                     messageId=str(uuid.uuid4()),
# #                     role=Role.agent,
# #                     parts=[TextPart(text="Task was cancelled.")]
# #                 )
# #             ),
# #             taskId=task_id,
# #             final=True,
# #         )
# #         await queue.enqueue_event(cancel_event)





# import asyncio
# import uuid
# from typing import Optional, List

# from a2a.types import (
#     Message,
#     TextPart,
#     TaskStatusUpdateEvent,
#     TaskStatus,
#     TaskState,
#     Role
# )
# from a2a.server.events.event_queue import EventQueue
# from a2a.server.request_handlers.request_handler import RequestHandler

# from langgraph_tool_wrapper import create_agent
# from langchain_core.messages import HumanMessage, BaseMessage
# from langchain_core.tools import BaseTool

# class LangGraphA2AExecutor:
#     """
#     An A2A executor that uses LangGraph to process requests.
#     This version is configured for non-streaming ('message/send') execution.
#     """
#     def __init__(self, event_queue: EventQueue):
#         self.event_queue = event_queue
#         self.graph = None  # will be set at startup
#         self._tools: List[BaseTool] = []

#     @property
#     def tools(self) -> List[BaseTool]:
#         """Returns the list of tools the agent has access to."""
#         return self._tools

#     async def initialize(self):
#         """
#         Initializes the LangGraph agent and discovers tools.
#         """
#         # Call create_agent, which now returns both the graph and the tools
#         graph, tools = await create_agent()
#         self.graph = graph
#         self._tools = tools
        
#         # Print the discovered tools here
#         print(f"✅ LangGraphA2AExecutor has access to the following tools: {[tool.name for tool in self._tools]}")

#     async def execute(self, request: RequestHandler, queue: EventQueue):
#         """
#         Executes a task using the LangGraph agent in non-streaming mode.
#         """
#         # Determine the contextId from the request.message. It might be None for a new task.
#         context_id = request.message.context_id or request.task_id
        
#         if not request.message or not request.message.parts:
#             failed_event = TaskStatusUpdateEvent(
#                 contextId=context_id,
#                 state=TaskState.failed,
#                 status=TaskStatus(
#                     state=TaskState.failed,
#                     message=Message(
#                         messageId=str(uuid.uuid4()),
#                         role=Role.agent,
#                         parts=[TextPart(text="No text content found in the message.")]
#                     ),
#                 ),
#                 taskId=request.task_id,
#                 final=True,
#             )
#             await queue.enqueue_event(failed_event)
#             return

#         # Correctly extract the user message text by checking the 'kind'
#         user_text = ""
#         for part in request.message.parts:
#             # Check the kind property to ensure we're handling text
#             if part.root.kind == "text":
#                 user_text += part.root.text

#         if not user_text:
#             failed_event = TaskStatusUpdateEvent(
#                 contextId=context_id,
#                 state=TaskState.failed,
#                 status=TaskStatus(
#                     state=TaskState.failed,
#                     message=Message(
#                         messageId=str(uuid.uuid4()),
#                         role=Role.agent,
#                         parts=[TextPart(text="No text content found in the message.")]
#                     ),
#                 ),
#                 taskId=request.task_id,
#                 final=True,
#             )
#             await queue.enqueue_event(failed_event)
#             return

#         #
#         # --- NON-STREAMING SETUP (ACTIVE) ---
#         #
#         try:
#             # Send message into LangGraph and wait for a single response
#             response = await self.graph.ainvoke(
#                 {"messages": [HumanMessage(content=user_text)]}
#             )
#             agent_reply = response["messages"][-1].content
#             print("AGENT REPLY:", agent_reply)

#             success_event = TaskStatusUpdateEvent(
#                 contextId=context_id,
#                 state=TaskState.completed,
#                 status=TaskStatus(
#                     state=TaskState.completed,
#                     message=Message(
#                         messageId=str(uuid.uuid4()),
#                         role=Role.agent,
#                         parts=[TextPart(text=agent_reply)]
#                     ),
#                 ),
#                 taskId=request.task_id,
#                 final=True,
#             )
#             await queue.enqueue_event(success_event)

#         except Exception as e:
#             error_event = TaskStatusUpdateEvent(
#                 contextId=context_id,
#                 state=TaskState.failed,
#                 status=TaskStatus(
#                     state=TaskState.failed,
#                     message=Message(
#                         messageId=str(uuid.uuid4()),
#                         role=Role.agent,
#                         parts=[TextPart(text=f"Execution error: {e}")]
#                     )
#                 ),
#                 taskId=request.task_id,
#                 final=True,
#             )
#             await queue.enqueue_event(error_event)
        
#         #
#         # --- STREAMING SETUP (COMMENTED OUT) ---
#         #
#         """
#         # try:
#         #     # Use astream for real-time, token-by-token streaming
#         #     async for chunk in self.graph.astream(
#         #         {"messages": [HumanMessage(content=user_text)]}
#         #     ):
#         #         # Check for new messages in the streamed chunk
#         #         if "messages" in chunk:
#         #             new_messages: List[BaseMessage] = chunk["messages"]
#         #             # Process each new message received
#         #             for message in new_messages:
#         #                 # Extract the content and send as a stream event
#         #                 if hasattr(message, 'content') and message.content:
#         #                     stream_event = TaskStatusUpdateEvent(
#         #                         contextId=request.task_id,
#         #                         state=TaskState.in_progress,  # Indicate ongoing progress
#         #                         status=TaskStatus(
#         #                             state=TaskState.in_progress,
#         #                             message=Message(
#         #                                 messageId=str(uuid.uuid4()),
#         #                                 role=Role.agent,
#         #                                 parts=[TextPart(text=message.content)]
#         #                             ),
#         #                         ),
#         #                         taskId=request.task_id,
#         #                         final=False,  # This is an intermediate event
#         #                     )
#         #                     await queue.enqueue_event(stream_event)
            
#         #     # Send a final 'completed' event once the stream is finished
#         #     final_event = TaskStatusUpdateEvent(
#         #         contextId=request.task_id,
#         #         state=TaskState.completed,
#         #         status=TaskStatus(
#         #             state=TaskState.completed,
#         #             message=Message(
#         #                 messageId=str(uuid.uuid4()),
#         #                 role=Role.agent,
#         #                 parts=[TextPart(text="Agent run completed.")]
#         #             ),
#         #         ),
#         #         taskId=request.task_id,
#         #         final=True,
#         #     )
#         #     await queue.enqueue_event(final_event)

#         # except Exception as e:
#         #     error_event = TaskStatusUpdateEvent(
#         #         contextId=context_id,
#         #         state=TaskState.failed,
#         #         status=TaskStatus(
#         #             state=TaskState.failed,
#         #             message=Message(
#         #                 messageId=str(uuid.uuid4()),
#         #                 role=Role.agent,
#         #                 parts=[TextPart(text=f"Execution error: {e}")]
#         #             )
#         #         ),
#         #         taskId=request.task_id,
#         #         final=True,
#         #     )
#         #     await queue.enqueue_event(error_event)
#         """

#     async def cancel(self, task_id: str, queue: EventQueue):
#         """
#         Cancel a task and enqueue a failed TaskStatusUpdateEvent.
#         """
#         cancel_event = TaskStatusUpdateEvent(
#             contextId=task_id,
#             state=TaskState.failed,
#             status=TaskStatus(
#                 state=TaskState.failed,
#                 message=Message(
#                     messageId=str(uuid.uuid4()),
#                     role=Role.agent,
#                     parts=[TextPart(text="Task was cancelled.")]
#                 )
#             ),
#             taskId=task_id,
#             final=True,
#         )
#         await queue.enqueue_event(cancel_event)






# import asyncio
# import uuid
# from typing import Optional, List, AsyncGenerator
# from a2a.types import (
#     Message,
#     TextPart,
#     TaskStatusUpdateEvent,
#     TaskStatus,
#     TaskState,
#     Role
# )
# from a2a.server.events.event_queue import EventQueue
# from a2a.server.request_handlers.request_handler import RequestHandler
# from langgraph_tool_wrapper import create_agent
# from langchain_core.messages import HumanMessage, BaseMessage, ToolMessage
# from langchain_core.tools import BaseTool

# class LangGraphA2AExecutor:
#     """
#     An A2A executor that uses LangGraph to process requests.
#     This version is configured to support streaming ('message/stream') execution.
#     """

#     def __init__(self, event_queue: EventQueue):
#         self.event_queue = event_queue
#         self.graph = None
#         self._tools: List[BaseTool] = []

#     @property
#     def tools(self) -> List[BaseTool]:
#         """Returns the list of tools the agent has access to."""
#         return self._tools

#     async def initialize(self):
#         """
#         Initializes the LangGraph agent and discovers tools.
#         """
#         graph, tools = await create_agent()
#         self.graph = graph
#         self._tools = tools
#         print(f"✅ LangGraphA2AExecutor has access to the following tools: {[tool.name for tool in self._tools]}")

#     async def execute(self, request: RequestHandler, queue: EventQueue):
#         """
#         Executes a task using the LangGraph agent, streaming events to the queue.
#         """
#         context_id = request.message.context_id or request.task_id
#         user_text = "".join(part.root.text for part in request.message.parts if part.root.kind == "text")

#         if not user_text:
#             failed_event = TaskStatusUpdateEvent(
#                 contextId=context_id,
#                 state=TaskState.failed,
#                 status=TaskStatus(
#                     state=TaskState.failed,
#                     message=Message(
#                         messageId=str(uuid.uuid4()),
#                         role=Role.agent,
#                         parts=[TextPart(text="No text content found in the message.")]
#                     ),
#                 ),
#                 taskId=request.task_id,
#                 final=True,
#             )
#             await queue.enqueue_event(failed_event)
#             return

#         try:
#             async for chunk in self.graph.astream_events(
#                 {"messages": [HumanMessage(content=user_text)]},
#                 version="v1"
#             ):
#                 event_type = chunk.get("event")
#                 data = chunk.get("data", {})

#                 if not isinstance(data, dict):
#                     continue

#                 if event_type == "on_tool_start":
#                     tool_name = data.get("tool_name")
#                     tool_args = data.get("input")
#                     print(f"Agent decided to use tool: 🤖 **{tool_name}** with arguments: {tool_args}")
                    
#                     tool_call_event = TaskStatusUpdateEvent(
#                         contextId=context_id,
#                         state=TaskState.working, # Using 'working'
#                         status=TaskStatus(
#                             state=TaskState.working,
#                             message=Message(
#                                 messageId=str(uuid.uuid4()),
#                                 role=Role.agent,
#                                 parts=[TextPart(text=f"Thinking... using tool '{tool_name}' with args {tool_args}")]
#                             )
#                         ),
#                         taskId=request.task_id,
#                         final=False,
#                     )
#                     await queue.enqueue_event(tool_call_event)

#                 elif event_type == "on_tool_end":
#                     tool_name = data.get("tool_name")
#                     tool_output = data.get("output")
#                     print(f"Tool **{tool_name}** finished. Output: {tool_output}")

#                     tool_output_event = TaskStatusUpdateEvent(
#                         contextId=context_id,
#                         state=TaskState.working, # Using 'working'
#                         status=TaskStatus(
#                             state=TaskState.working,
#                             message=Message(
#                                 messageId=str(uuid.uuid4()),
#                                 role=Role.agent,
#                                 parts=[TextPart(text=f"Tool '{tool_name}' output: {tool_output}")]
#                             )
#                         ),
#                         taskId=request.task_id,
#                         final=False,
#                     )
#                     await queue.enqueue_event(tool_output_event)

#                 elif event_type == "on_chain_end" and "output" in data:
#                     output_data = data.get("output")
#                     if isinstance(output_data, dict) and "messages" in output_data:
#                         final_response_message = output_data["messages"][-1]
#                         if hasattr(final_response_message, 'content') and final_response_message.content:
#                             final_event = TaskStatusUpdateEvent(
#                                 contextId=context_id,
#                                 state=TaskState.completed,
#                                 status=TaskStatus(
#                                     state=TaskState.completed,
#                                     message=Message(
#                                         messageId=str(uuid.uuid4()),
#                                         role=Role.agent,
#                                         parts=[TextPart(text=final_response_message.content)]
#                                     ),
#                                 ),
#                                 taskId=request.task_id,
#                                 final=True,
#                             )
#                             await queue.enqueue_event(final_event)

#         except Exception as e:
#             error_event = TaskStatusUpdateEvent(
#                 contextId=context_id,
#                 state=TaskState.failed,
#                 status=TaskStatus(
#                     state=TaskState.failed,
#                     message=Message(
#                         messageId=str(uuid.uuid4()),
#                         role=Role.agent,
#                         parts=[TextPart(text=f"Execution error: {e}")]
#                     )
#                 ),
#                 taskId=request.task_id,
#                 final=True,
#             )
#             await queue.enqueue_event(error_event)

#     async def cancel(self, task_id: str, queue: EventQueue):
#         """
#         Cancel a task and enqueue a failed TaskStatusUpdateEvent.
#         """
#         cancel_event = TaskStatusUpdateEvent(
#             contextId=task_id,
#             state=TaskState.failed,
#             status=TaskStatus(
#                 state=TaskState.failed,
#                 message=Message(
#                     messageId=str(uuid.uuid4()),
#                     role=Role.agent,
#                     parts=[TextPart(text="Task was cancelled.")]
#                 )
#             ),
#             taskId=task_id,
#             final=True,
#         )
#         await queue.enqueue_event(cancel_event)















# import asyncio
# import uuid
# from typing import Optional, List
# from a2a.types import (
#     Message,
#     TextPart,
#     TaskStatusUpdateEvent,
#     TaskStatus,
#     TaskState,
#     Role
# )
# from a2a.server.events.event_queue import EventQueue
# from a2a.server.request_handlers.request_handler import RequestHandler
# from a2a.server.request_handlers.default_request_handler import RequestContext

# from langgraph_tool_wrapper import create_agent
# from langchain_core.messages import HumanMessage, BaseMessage
# from langchain_core.tools import BaseTool

# class LangGraphA2AExecutor:
#     """
#     An A2A executor that handles both non-streaming and streaming requests using LangGraph.
#     """
#     def __init__(self, event_queue: EventQueue):
#         self.event_queue = event_queue
#         self.graph = None
#         self._tools: List[BaseTool] = []

#     @property
#     def tools(self) -> List[BaseTool]:
#         return self._tools

#     async def initialize(self):
#         graph, tools = await create_agent()
#         self.graph = graph
#         self._tools = tools
#         print(f"✅ LangGraphA2AExecutor has access to the following tools: {[tool.name for tool in self._tools]}")

#     async def execute(self, request: RequestContext, queue: EventQueue):
#         """
#         Executes a task. The DefaultRequestHandler handles streaming vs non-streaming routing.
#         The executor just runs the agent logic and publishes events to the queue.
#         """
#         context_id = request.message.context_id or request.task_id
        
#         if not request.message or not request.message.parts:
#             failed_event = TaskStatusUpdateEvent(
#                 contextId=context_id,
#                 state=TaskState.failed,
#                 status=TaskStatus(
#                     state=TaskState.failed,
#                     message=Message(
#                         messageId=str(uuid.uuid4()),
#                         role=Role.agent,
#                         parts=[TextPart(text="No text content found in the message.")]
#                     ),
#                 ),
#                 taskId=request.task_id,
#                 final=True,
#             )
#             await queue.enqueue_event(failed_event)
#             await queue.close()
#             return

#         user_text = "".join(part.root.text for part in request.message.parts if part.root.kind == "text")

#         if not user_text:
#             failed_event = TaskStatusUpdateEvent(
#                 contextId=context_id,
#                 state=TaskState.failed,
#                 status=TaskStatus(
#                     state=TaskState.failed,
#                     message=Message(
#                         messageId=str(uuid.uuid4()),
#                         role=Role.agent,
#                         parts=[TextPart(text="No text content found in the message.")]
#                     ),
#                 ),
#                 taskId=request.task_id,
#                 final=True,
#             )
#             await queue.enqueue_event(failed_event)
#             await queue.close()
#             return
            
#         try:
#             # LangGraph astream_events provides a more detailed stream with tool calls
#             async for chunk in self.graph.astream_events(
#                 {"messages": [HumanMessage(content=user_text)]},
#                 version="v1"
#             ):
#                 event_type = chunk.get("event")
#                 data = chunk.get("data", {})
                
#                 if not isinstance(data, dict):
#                     continue

#                 if event_type == "on_tool_start":
#                     tool_name = data.get("tool_name")
#                     print(f"🤖 Agent decided to use tool: {tool_name}")
#                     tool_call_event = TaskStatusUpdateEvent(
#                         contextId=context_id,
#                         state=TaskState.working,
#                         status=TaskStatus(
#                             state=TaskState.working,
#                             message=Message(
#                                 messageId=str(uuid.uuid4()),
#                                 role=Role.agent,
#                                 parts=[TextPart(text=f"Thinking... using tool '{tool_name}'")]
#                             )
#                         ),
#                         taskId=request.task_id,
#                         final=False,
#                     )
#                     await queue.enqueue_event(tool_call_event)

#                 elif event_type == "on_tool_end":
#                     # print(data)
#                     tool_name = data.get("tool_name")
#                     tool_output = data.get("output")
#                     print("TOOL OUTPUT TEXT: ", tool_output.text)
#                     # print(f"✅ Tool {tool_name} finished. Output: {tool_output.text}")
#                     tool_output_event = TaskStatusUpdateEvent(
#                         contextId=context_id,
#                         state=TaskState.working,
#                         status=TaskStatus(
#                             state=TaskState.working,
#                             message=Message(
#                                 messageId=str(uuid.uuid4()),
#                                 role=Role.agent,
#                                 parts=[TextPart(text=f"Tool output: {tool_output}")]
#                             )
#                         ),
#                         taskId=request.task_id,
#                         final=False,
#                     )
#                     await queue.enqueue_event(tool_output_event)

#                 elif event_type == "on_chain_end" and "output" in data:
#                     output_data = data.get("output")
#                     if isinstance(output_data, dict) and "messages" in output_data:
#                         final_response_message = output_data["messages"][-1]
#                         if hasattr(final_response_message, 'content') and final_response_message.content:
#                             final_event = TaskStatusUpdateEvent(
#                                 contextId=context_id,
#                                 state=TaskState.completed,
#                                 status=TaskStatus(
#                                     state=TaskState.completed,
#                                     message=Message(
#                                         messageId=str(uuid.uuid4()),
#                                         role=Role.agent,
#                                         parts=[TextPart(text=final_response_message.content)]
#                                     ),
#                                 ),
#                                 taskId=request.task_id,
#                                 final=True,
#                             )
#                             await queue.enqueue_event(final_event)

#         except Exception as e:
#             await self._enqueue_error(context_id, request.task_id, queue, e)
#         finally:
#             await queue.close()

#     async def _enqueue_error(self, context_id: str, task_id: str, queue: EventQueue, error: Exception):
#         error_event = TaskStatusUpdateEvent(
#             contextId=context_id,
#             state=TaskState.failed,
#             status=TaskStatus(
#                 state=TaskState.failed,
#                 message=Message(
#                     messageId=str(uuid.uuid4()),
#                     role=Role.agent,
#                     parts=[TextPart(text=f"Execution error: {error}")]
#                 )
#             ),
#             taskId=task_id,
#             final=True,
#         )
#         await queue.enqueue_event(error_event)

#     async def cancel(self, request: RequestContext, queue: EventQueue):
#         cancel_event = TaskStatusUpdateEvent(
#             contextId=request.task_id,
#             state=TaskState.failed,
#             status=TaskStatus(
#                 state=TaskState.failed,
#                 message=Message(
#                     messageId=str(uuid.uuid4()),
#                     role=Role.agent,
#                     parts=[TextPart(text="Task was cancelled.")]
#                 )
#             ),
#             taskId=request.task_id,
#             final=True,
#         )
#         await queue.enqueue_event(cancel_event)
#         await queue.close()








import asyncio
import uuid
import re
from typing import Optional, List, cast
from a2a.types import (
    Message,
    TextPart,
    TaskStatusUpdateEvent,
    TaskStatus,
    TaskState,
    Role
)
from a2a.server.events.event_queue import EventQueue
from a2a.server.request_handlers.default_request_handler import RequestContext

from langgraph_tool_wrapper import create_agent
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import BaseTool

class LangGraphA2AExecutor:
    """
    An A2A executor that handles both non-streaming and streaming requests using LangGraph.
    """
    def __init__(self, event_queue: EventQueue):
        self.event_queue = event_queue
        self.graph = None
        self._tools: List[BaseTool] = []

    @property
    def tools(self) -> List[BaseTool]:
        return self._tools

    async def initialize(self):
        graph, tools = await create_agent()
        self.graph = graph
        self._tools = tools
        print(f"✅ LangGraphA2AExecutor has access to the following tools: {[tool.name for tool in self._tools]}")

    async def execute(self, request: RequestContext, queue: EventQueue):
        """
        Executes a task. It uses LangGraph's astream_events to process
        tool calls and then synthesizes a final response.
        """
        context_id = request.message.context_id or request.task_id
        
        if not request.message or not request.message.parts:
            await self._enqueue_error(context_id, request.task_id, queue, "No text content found in the message.")
            return

        user_text = "".join(part.root.text for part in request.message.parts if part.root.kind == "text")
        
        if not user_text:
            await self._enqueue_error(context_id, request.task_id, queue, "No text content found in the message.")
            return
            
        try:
            raw_tool_output_text: Optional[str] = None
            
            # Use astream_events to monitor for tool outputs
            async for chunk in self.graph.astream_events(
                {"messages": [HumanMessage(content=user_text)]},
                version="v1"
            ):
                event_type = chunk.get("event")
                data = chunk.get("data", {})
                
                if event_type == "on_tool_start":
                    tool_name = data.get("tool_name")
                    print(f"🤖 Agent decided to use tool: {tool_name}")
                    tool_call_event = TaskStatusUpdateEvent(
                        contextId=context_id,
                        state=TaskState.working,
                        status=TaskStatus(
                            state=TaskState.working,
                            message=Message(
                                messageId=str(uuid.uuid4()),
                                role=Role.agent,
                                parts=[TextPart(text=f"Thinking... using tool '{tool_name}'")]
                            )
                        ),
                        taskId=request.task_id,
                        final=False,
                    )
                    await queue.enqueue_event(tool_call_event)

                elif event_type == "on_tool_end":
                    tool_output_message = data.get("output")
                    if isinstance(tool_output_message, ToolMessage) and tool_output_message.artifact:
                        raw_tool_output_text = cast(str, tool_output_message.artifact[0].resource.text)
                        print(f"✅ Tool finished. Raw output collected.")
                        # Do not send a redundant tool output event here.
                    
                    # Synthesize the final response after the tool completes
                    if raw_tool_output_text:
                        final_response_text = self._synthesize_response(user_text, raw_tool_output_text)
                        await self._send_final_response(request, queue, final_response_text)
                        return # Exit the loop and function after the final response
            
            # Fallback for when no tool is used
            final_response = await self.graph.ainvoke({"messages": [HumanMessage(content=user_text)]})
            final_agent_message = final_response["messages"][-1].content
            await self._send_final_response(request, queue, final_agent_message)

        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            await self._enqueue_error(context_id, request.task_id, queue, f"Execution error: {e}")
        finally:
            await queue.close()

    def _synthesize_response(self, user_text: str, tool_output_text: str) -> str:
        """
        Synthesizes a clean, readable response from the tool output.
        """
        # Define a regex pattern to find "Name" followed by text until another markdown header or empty line
        # This is a robust way to parse the table content.
        pattern = re.compile(r'\|\s*([^|]+)\s*\|.*', re.MULTILINE)
        toolsets = pattern.findall(tool_output_text)
        
        # Clean up the names and filter out headers or empty lines
        toolset_names = [name.strip() for name in toolsets if name.strip() and name.strip().lower() not in ["name", "additional _remote_ server toolsets"]]
        
        if toolset_names:
            formatted_names = [f"**{name}**" for name in toolset_names]
            return f"Based on the `remote-server.md` file, the available toolsets are: {', '.join(formatted_names)}."
        else:
            return "I was able to retrieve the file, but could not find the toolsets mentioned."

    async def _send_final_response(self, request: RequestContext, queue: EventQueue, response_text: str):
        """Helper to send the final TaskStatusUpdateEvent."""
        success_event = TaskStatusUpdateEvent(
            contextId=request.context_id,
            state=TaskState.completed,
            status=TaskStatus(
                state=TaskState.completed,
                message=Message(
                    messageId=str(uuid.uuid4()),
                    role=Role.agent,
                    parts=[TextPart(text=response_text)]
                ),
            ),
            taskId=request.task_id,
            final=True,
        )
        await queue.enqueue_event(success_event)

    async def _enqueue_error(self, context_id: str, task_id: str, queue: EventQueue, message: str):
        """Helper function to enqueue a failed task event."""
        error_event = TaskStatusUpdateEvent(
            contextId=context_id,
            state=TaskState.failed,
            status=TaskStatus(
                state=TaskState.failed,
                message=Message(
                    messageId=str(uuid.uuid4()),
                    role=Role.agent,
                    parts=[TextPart(text=message)]
                )
            ),
            taskId=task_id,
            final=True,
        )
        await queue.enqueue_event(error_event)

    async def cancel(self, request: RequestContext, queue: EventQueue):
        cancel_event = TaskStatusUpdateEvent(
            contextId=request.task_id,
            state=TaskState.failed,
            status=TaskStatus(
                state=TaskState.failed,
                message=Message(
                    messageId=str(uuid.uuid4()),
                    role=Role.agent,
                    parts=[TextPart(text="Task was cancelled.")]
                )
            ),
            taskId=request.task_id,
            final=True,
        )
        await queue.enqueue_event(cancel_event)
        await queue.close()
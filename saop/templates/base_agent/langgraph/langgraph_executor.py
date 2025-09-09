
# import asyncio
# import uuid
# import re
# from typing import Optional, List, cast
# from a2a.types import (
#     Message,
#     TextPart,
#     TaskStatusUpdateEvent,
#     TaskStatus,
#     TaskState,
#     Role
# )
# from a2a.server.events.event_queue import EventQueue
# from a2a.server.request_handlers.default_request_handler import RequestContext

# from langgraph_tool_wrapper import create_agent
# from langchain_core.messages import HumanMessage, ToolMessage
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
#         Executes a task. It uses LangGraph's astream_events to process
#         tool calls and then synthesizes a final response.
#         """
#         context_id = request.message.context_id or request.task_id
        
#         if not request.message or not request.message.parts:
#             await self._enqueue_error(context_id, request.task_id, queue, "No text content found in the message.")
#             return

#         user_text = "".join(part.root.text for part in request.message.parts if part.root.kind == "text")
        
#         if not user_text:
#             await self._enqueue_error(context_id, request.task_id, queue, "No text content found in the message.")
#             return
            
#         try:
#             raw_tool_output_text: Optional[str] = None
            
#             # Use astream_events to monitor for tool outputs
#             async for chunk in self.graph.astream_events(
#                 {"messages": [HumanMessage(content=user_text)]},
#                 version="v1"
#             ):
#                 event_type = chunk.get("event")
#                 data = chunk.get("data", {})
                
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
#                     tool_output_message = data.get("output")
#                     if isinstance(tool_output_message, ToolMessage) and tool_output_message.artifact:
#                         raw_tool_output_text = cast(str, tool_output_message.artifact[0].resource.text)
#                         print(f"✅ Tool finished. Raw output collected.")
#                         # Do not send a redundant tool output event here.
                    
#                     # Synthesize the final response after the tool completes
#                     if raw_tool_output_text:
#                         final_response_text = self._synthesize_response(user_text, raw_tool_output_text)
#                         await self._send_final_response(request, queue, final_response_text)
#                         return # Exit the loop and function after the final response
            
#             # Fallback for when no tool is used
#             final_response = await self.graph.ainvoke({"messages": [HumanMessage(content=user_text)]})
#             final_agent_message = final_response["messages"][-1].content
#             await self._send_final_response(request, queue, final_agent_message)

#         except Exception as e:
#             print(f"An unexpected error occurred: {e}")
#             await self._enqueue_error(context_id, request.task_id, queue, f"Execution error: {e}")
#         finally:
#             await queue.close()








#     def _synthesize_response(self, user_text: str, tool_output_text: str) -> str:
#         """
#         Synthesizes a clean, readable response from the tool output.
#         """
#         # Define a regex pattern to find "Name" followed by text until another markdown header or empty line
#         # This is a robust way to parse the table content.
#         pattern = re.compile(r'\|\s*([^|]+)\s*\|.*', re.MULTILINE)
#         toolsets = pattern.findall(tool_output_text)
        
#         # Clean up the names and filter out headers or empty lines
#         toolset_names = [name.strip() for name in toolsets if name.strip() and name.strip().lower() not in ["name", "additional _remote_ server toolsets"]]
        
#         if toolset_names:
#             formatted_names = [f"**{name}**" for name in toolset_names]
#             return f"Based on the `remote-server.md` file, the available toolsets are: {', '.join(formatted_names)}."
#         else:
#             return "I was able to retrieve the file, but could not find the toolsets mentioned."

#     async def _send_final_response(self, request: RequestContext, queue: EventQueue, response_text: str):
#         """Helper to send the final TaskStatusUpdateEvent."""
#         success_event = TaskStatusUpdateEvent(
#             contextId=request.context_id,
#             state=TaskState.completed,
#             status=TaskStatus(
#                 state=TaskState.completed,
#                 message=Message(
#                     messageId=str(uuid.uuid4()),
#                     role=Role.agent,
#                     parts=[TextPart(text=response_text)]
#                 ),
#             ),
#             taskId=request.task_id,
#             final=True,
#         )
#         await queue.enqueue_event(success_event)







#     async def _enqueue_error(self, context_id: str, task_id: str, queue: EventQueue, message: str):
#         """Helper function to enqueue a failed task event."""
#         error_event = TaskStatusUpdateEvent(
#             contextId=context_id,
#             state=TaskState.failed,
#             status=TaskStatus(
#                 state=TaskState.failed,
#                 message=Message(
#                     messageId=str(uuid.uuid4()),
#                     role=Role.agent,
#                     parts=[TextPart(text=message)]
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



























# langgraph_executor.py
# # langgraph_executor.py

# import asyncio
# import uuid
# import re
# from typing import Optional, List, cast
# from a2a.server.agent_execution import AgentExecutor
# from a2a.server.agent_execution.context import RequestContext
# from a2a.server.events.event_queue import EventQueue
# from a2a.types import (
#     Message,
#     TextPart,
#     TaskStatusUpdateEvent,
#     TaskStatus,
#     TaskState,
#     Role
# )
# from langgraph_tool_wrapper import AgentTemplate
# from langchain_core.messages import HumanMessage, ToolMessage
# from langchain_core.tools import BaseTool

# class LangGraphA2AExecutor(AgentExecutor):
#     def __init__(self):
#         self.agent = AgentTemplate()

#     async def initialize(self):
#         await self.agent._initialize_components()
#         self._tools = self.agent._tools
#         print(f"✅ LangGraphA2AExecutor has access to the following tools: {[tool.name for tool in self._tools]}")
    
#     async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
#         """
#         Executes a task, synthesizes the final response, and publishes a single completion event.
#         """
#         user_text = "".join(part.root.text for part in context.message.parts if part.root.kind == "text")
        
#         try:
#             # First, send a 'working' status update
#             working_event = TaskStatusUpdateEvent(
#                 contextId=context.context_id,
#                 state=TaskState.working,
#                 status=TaskStatus(
#                     state=TaskState.working,
#                     message=Message(
#                         messageId=str(uuid.uuid4()),
#                         role=Role.agent,
#                         parts=[TextPart(text="Thinking...")]
#                     )
#                 ),
#                 taskId=context.task_id,
#                 final=False,
#             )
#             await event_queue.enqueue_event(working_event)

#             # Use the agent's ainvoke method to run the entire graph and get the final result.
#             final_response = await self.agent.ainvoke(user_text)
            
#             # The final message from the graph is typically a HumanMessage or AIMessage.
#             final_agent_message = final_response["messages"][-1]
            
#             # Now, you need to synthesize the response from the tool output.
#             # You must check if the agent used a tool and get the output.
#             # This logic depends on the final state of your graph.
#             # Let's assume the final message contains the tool output in its content.
#             if isinstance(final_agent_message, HumanMessage):
#                 synthesized_text = self._synthesize_response(user_text, final_agent_message.content)
#             else:
#                 synthesized_text = final_agent_message.content

#             # Convert the synthesized text to an A2A message
#             final_a2a_message = Message(
#                 messageId=str(uuid.uuid4()),
#                 role=Role.agent,
#                 parts=[TextPart(text=synthesized_text)]
#             )
            
#             # Send the final response as a completion event
#             success_event = TaskStatusUpdateEvent(
#                 contextId=context.context_id,
#                 state=TaskState.completed,
#                 status=TaskStatus(
#                     state=TaskState.completed,
#                     message=final_a2a_message,
#                 ),
#                 taskId=context.task_id,
#                 final=True,
#             )
#             await event_queue.enqueue_event(success_event)
            
#         except Exception as e:
#             print(f"An unexpected error occurred in executor: {e}")
#             error_event = TaskStatusUpdateEvent(
#                 contextId=context.context_id,
#                 state=TaskState.failed,
#                 status=TaskStatus(
#                     state=TaskState.failed,
#                     message=Message(
#                         messageId=str(uuid.uuid4()),
#                         role=Role.agent,
#                         parts=[TextPart(text=f"Execution error: {e}")]
#                     )
#                 ),
#                 taskId=context.task_id,
#                 final=True,
#             )
#             await event_queue.enqueue_event(error_event)

#     def _synthesize_response(self, user_text: str, tool_output_text: str) -> str:
#         """
#         Synthesizes a clean, readable response from the tool output.
#         """
#         # Define a regex pattern to find "Name" followed by text until another markdown header or empty line
#         pattern = re.compile(r'\|\s*([^|]+)\s*\|.*', re.MULTILINE)
#         toolsets = pattern.findall(tool_output_text)
        
#         # Clean up the names and filter out headers or empty lines
#         toolset_names = [name.strip() for name in toolsets if name.strip() and name.strip().lower() not in ["name", "additional _remote_ server toolsets"]]
        
#         if toolset_names:
#             formatted_names = [f"**{name}**" for name in toolset_names]
#             return f"Based on the `remote-server.md` file, the available toolsets are: {', '.join(formatted_names)}."
#         else:
#             return "I was able to retrieve the file, but could not find the toolsets mentioned."

#     async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
#         """Handles agent cancellation by publishing a cancellation event."""
#         cancel_event = TaskStatusUpdateEvent(
#             contextId=context.task_id,
#             state=TaskState.failed,
#             status=TaskStatus(
#                 state=TaskState.failed,
#                 message=Message(
#                     messageId=str(uuid.uuid4()),
#                     role=Role.agent,
#                     parts=[TextPart(text="Task was cancelled.")]
#                 )
#             ),
#             taskId=context.task_id,
#             final=True,
#         )
#         await event_queue.enqueue_event(cancel_event)
#         print("LangGraph agent cancel called. Cancellation event published.")






















# langgraph_executor.py

import asyncio
import uuid
from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue

from langgraph.langgraph_agent import AgentTemplate
from agent2agent.a2a_tasks import A2ATask
from agent2agent.a2a_utils import create_cancellation_event 

class LangGraphA2AExecutor(AgentExecutor):
    def __init__(self):
        self.agent = AgentTemplate()

    async def initialize(self):
        await self.agent._initialize_components()
        self._tools = self.agent._tools
        print(f"✅ LangGraphA2AExecutor has access to the following tools: {[tool.name for tool in self._tools]}")
    
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = A2ATask(self, context, event_queue)
        await task.run()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        cancel_event = create_cancellation_event(context)
        await event_queue.enqueue_event(cancel_event)
        print("LangGraph agent cancel called. Cancellation event published.")

    async def _run_agent(self, user_text: str):
        return await self.agent.ainvoke(user_text)
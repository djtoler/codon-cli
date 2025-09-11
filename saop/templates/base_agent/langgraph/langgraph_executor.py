# langgraph/langgraph_executor.py - Handle role resolution internally
import asyncio
import uuid
import sys
from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from langgraph.agent_factory import AgentFactory
from agent2agent.a2a_tasks import A2ATask
from agent2agent.a2a_utils import create_cancellation_event
from config.agent_config import load_env_config

class LangGraphA2AExecutor(AgentExecutor):
    def __init__(self, role_name: str = "general_support"):
        # Role is passed from server, not determined internally
        self.role_name = role_name
        self.factory = AgentFactory()
        self.agent = None
        self._initialization_error = None
        self._degraded_mode = False

    def suggest_similar_role(self, invalid_role: str, available_roles: list[str]) -> str:
        """Find the most similar role using fuzzy matching"""
        from difflib import get_close_matches
        matches = get_close_matches(invalid_role, available_roles, n=1, cutoff=0.6)
        return matches[0] if matches else None
    
    def prompt_user_for_action(self, invalid_role: str, available_roles: list[str], suggestion: str = None) -> str:
        """Prompt user for action when role is not found"""
        print(f"\nRole '{invalid_role}' not found.")
        
        if suggestion:
            print(f"Did you mean '{suggestion}'?")
        
        print("\nAvailable roles:")
        for i, role in enumerate(available_roles, 1):
            print(f"  {i}. {role}")
        
        print(f"\nOptions:")
        print(f"  y - Use default role ('general_support')")
        print(f"  n - Stop server and fix configuration")
        print(f"  d - Run in degraded mode (no agent)")
        if suggestion:
            print(f"  s - Use suggested role ('{suggestion}')")
        
        while True:
            try:
                choice = input("\nChoose [y/n/d" + ("/s" if suggestion else "") + "]: ").strip().lower()
                
                if choice == 'y':
                    return 'general_support'
                elif choice == 'n':
                    print("Stopping server. Please update your configuration.")
                    exit(1)
                elif choice == 'd':
                    return None  # Degraded mode
                elif choice == 's' and suggestion:
                    return suggestion
                else:
                    valid_options = "y/n/d" + ("/s" if suggestion else "")
                    print(f"Invalid choice. Please enter {valid_options}")
                    
            except KeyboardInterrupt:
                print("\nStopping server.")
                exit(1)

    async def initialize(self):
        print(f"Initializing LangGraphA2AExecutor for role: {self.role_name}")
        
        try:
            # Create role-based agent using the factory
            self.agent = await self.factory.create_agent(self.role_name)
            
            if self.agent is None:
                error_msg = f"Agent factory returned None for role '{self.role_name}'"
                self._initialization_error = error_msg
                print(f"Failed to initialize executor for role '{self.role_name}': {error_msg}")
                self._degraded_mode = True
                return False
            
            self._tools = self.agent._tools
            tool_names = [tool.name for tool in self._tools]
            
            # Enhanced logging with role info
            role_info = self.agent.get_role_info()
            print(f"Executor '{self.role_name}' initialized successfully with {len(self._tools)} tools: {tool_names}")
            
            if self.agent.requires_human_review():
                print("This role requires human review for certain actions")
            
            return True
            
        except ValueError as e:
            # Handle invalid role names with interactive prompt
            if "not found" in str(e).lower():
                # Extract available roles from error message
                available_roles = []
                if "Available roles:" in str(e):
                    try:
                        available_roles_str = str(e).split("Available roles:")[1].strip()
                        import ast
                        available_roles = ast.literal_eval(available_roles_str)
                    except:
                        # Fallback: get from factory if possible
                        try:
                            available_roles = self.factory.list_roles()
                        except:
                            available_roles = ["general_support", "math_specialist", "research_assistant"]
                
                # Get fuzzy match suggestion
                suggestion = self.suggest_similar_role(self.role_name, available_roles)
                
                # Prompt user for action
                chosen_role = self.prompt_user_for_action(self.role_name, available_roles, suggestion)
                
                if chosen_role is None:
                    # Degraded mode
                    self._initialization_error = f"Running in degraded mode - role '{self.role_name}' not found"
                    self._degraded_mode = True
                    print(f"Running in degraded mode: {self._initialization_error}")
                    return False
                else:
                    # Try with chosen role
                    print(f"Using role: {chosen_role}")
                    self.role_name = chosen_role
                    return await self.initialize()  # Recursive call with new role
            else:
                # Other ValueError
                self._initialization_error = str(e)
                self._degraded_mode = True
                print(f"Executor role '{self.role_name}' validation failed: {str(e)}")
                return False
            
        except Exception as e:
            # Handle any other initialization errors
            self._initialization_error = f"Failed to initialize agent: {str(e)}"
            self._degraded_mode = True
            print(f"Executor '{self.role_name}' runtime error: {str(e)}")
            return False

    def is_initialized(self) -> bool:
        """Check if the executor was successfully initialized"""
        return self.agent is not None and self._initialization_error is None

    def is_degraded(self) -> bool:
        """Check if the executor is running in degraded mode"""
        return self._degraded_mode

    def get_initialization_error(self) -> str:
        """Get the initialization error message if any"""
        return self._initialization_error

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        if not self.is_initialized():
            error_msg = f"Agent not available: {self._initialization_error}"
            print(f"Execution blocked for '{self.role_name}': {self._initialization_error}")
            
            # Create proper error event using your existing A2A types
            from a2a.types import Message, TextPart, TaskStatusUpdateEvent, TaskStatus, TaskState, Role
            import uuid
            
            error_event = TaskStatusUpdateEvent(
                contextId=context.context_id,
                state=TaskState.failed,
                status=TaskStatus(
                    state=TaskState.failed,
                    message=Message(
                        messageId=str(uuid.uuid4()),
                        role=Role.agent,
                        parts=[TextPart(text=error_msg)]
                    )
                ),
                taskId=context.task_id,
                final=True,
            )
            await event_queue.enqueue_event(error_event)
            return
            
        task = A2ATask(self, context, event_queue)
        await task.run()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        cancel_event = create_cancellation_event(context)
        await event_queue.enqueue_event(cancel_event)
        print(f"Executor '{self.role_name}' graceful recovery: Cancellation event published")

    def _ensure_initialized(self):
        """Ensure agent is initialized or raise error."""
        if not self.is_initialized():
            raise RuntimeError(f"Agent not initialized: {self._initialization_error}")

    async def run_agent(self, user_text: str):
        self._ensure_initialized()
        return await self.agent.ainvoke(user_text)
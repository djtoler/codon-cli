# a2a_utils.py

import uuid
import yaml
import os 
from pydantic import ValidationError

from a2a.server.agent_execution.context import RequestContext
from a2a.types import (
    Message,
    TextPart,
    TaskStatusUpdateEvent,
    TaskStatus,
    TaskState,
    Role, 
    AgentCard
)


def create_cancellation_event(context: RequestContext) -> TaskStatusUpdateEvent:
    return TaskStatusUpdateEvent(
        contextId=context.task_id,
        state=TaskState.failed,
        status=TaskStatus(
            state=TaskState.failed,
            message=Message(
                messageId=str(uuid.uuid4()),
                role=Role.agent,
                parts=[TextPart(text="Task was cancelled.")]
            )
        ),
        taskId=context.task_id,
        final=True,
    )

def create_agent_card_from_yaml_file(file_name: str) -> AgentCard:
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(current_dir, file_name)
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
            print("\n✅ Agent Card loaded successfully from YAML:")
        return AgentCard(**data)
    except FileNotFoundError:
        print(f"❌ Error: The file '{file_name}' was not found.")
        raise
    except ValidationError as e:
        print(f"❌ Pydantic validation failed for AgentCard: {e}")
        raise
    except yaml.YAMLError as e:
        print(f"❌ YAML parsing failed: {e}")
        raise
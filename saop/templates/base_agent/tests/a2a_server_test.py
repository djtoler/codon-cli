import pytest
from starlette.testclient import TestClient
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Correct imports
from a2a.server.apps.jsonrpc import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (AgentCard, AgentSkill, AgentCapabilities, Message,
    TextPart,
    TaskStatusUpdateEvent,
    TaskStatus,
    TaskState,
    Role,
    Part,
    JSONRPCSuccessResponse)

@pytest.fixture
def client():
    mock_request_handler = MagicMock(spec=DefaultRequestHandler)
    
    # We'll make the mock's on_message_send method return a valid Message object
    # that your test can then assert on.
    mock_message_response = Message(
        message_id="mock-response-id",
        role=Role.agent,
        parts=[
            Part(root=TextPart(text="Hello, world!", kind='text'))
        ]
    )

    # Configure the mock to return this message when on_message_send is called
    mock_request_handler.on_message_send = AsyncMock(return_value=mock_message_response)

    # Instantiate the application with the mocked handler
    starlette_app = A2AStarletteApplication(
        agent_card=AgentCard(
            id="test-agent",
            name="test-agent",
            version="1.0.0",
            url="http://localhost:9999",
            description="A test agent for the SAOP platform.",
            skills=[
                AgentSkill(
                    id="echo",
                    name="echo",
                    description="Echoes a message.",
                    tags=["test", "echo-function"]
                )
            ],
            capabilities=AgentCapabilities(
                tools=["echo"],
                protocols=["a2a:json-rpc"]
            ),
            default_input_modes=['text'],
            default_output_modes=['text']
        ),
        http_handler=mock_request_handler
    )
    
    with TestClient(starlette_app.build()) as client:
        yield client

def test_message_send_returns_echo_text(client):
    """
    Test that the / endpoint returns the sent message via JSON-RPC.
    """
    request_payload = {
      "jsonrpc": "2.0",
      "id": "12345",
      "method": "message/send",
      "params": {
        "message": {
          "messageId": "msg-001",
          "role": "user",
          "parts": [
            {
              "text": "Hello, world!"
            }
          ]
        }
      }
    }
    
    response = client.post("/", json=request_payload)
    
    assert response.status_code == 200
    response_data = response.json()
    
    assert "result" in response_data
    # ⚠️ CORRECTED: Access the text via the nested keys
    assert response_data["result"]["parts"][0]["text"] == "Hello, world!"
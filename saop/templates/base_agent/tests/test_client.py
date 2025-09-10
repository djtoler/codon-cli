#!/usr/bin/env python3
"""
A2A Test Client - Test your agent like a real client would.
Handles authentication and A2A protocol communication.
"""
import requests
import json
import sys
from typing import Optional, Dict, Any

class A2ATestClient:
    """Test client for A2A agent communication"""
    
    def __init__(self, base_url: str = "http://localhost:9999"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.auth_token = None
        self.api_key = None
        
    def authenticate_with_password(self, username: str, password: str) -> bool:
        """Authenticate using OAuth2 password flow"""
        try:
            response = self.session.post(f"{self.base_url}/auth/token", data={
                "username": username,
                "password": password
            })
            
            if response.status_code == 200:
                self.auth_token = response.json()["access_token"]
                self.session.headers.update({
                    "Authorization": f"Bearer {self.auth_token}"
                })
                print(f"Authenticated as {username}")
                return True
            else:
                print(f"Authentication failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"Authentication error: {e}")
            return False
    
    def authenticate_with_api_key(self, api_key: str) -> bool:
        """Authenticate using API key"""
        self.api_key = api_key
        self.session.headers.update({
            "X-API-Key": api_key
        })
        
        # Test the API key works
        try:
            response = self.session.get(f"{self.base_url}/auth/users/me")
            if response.status_code == 200:
                user_info = response.json()
                print(f"Authenticated with API key as {user_info['username']}")
                return True
            else:
                print(f"API key authentication failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"API key error: {e}")
            return False
    
    def send_message(self, text: str, message_id: Optional[str] = None) -> Optional[Dict[Any, Any]]:
        """Send a message to the A2A agent"""
        import uuid
        
        if not message_id:
            message_id = str(uuid.uuid4())
        
        request_payload = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": {
                    "messageId": message_id,
                    "role": "user",
                    "parts": [{"text": text}]
                }
            },
            "id": 1
        }
        
        try:
            print(f"Sending: {text}")
            response = self.session.post(
                f"{self.base_url}/",
                json=request_payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"Full response: {json.dumps(result, indent=2)}")
                
                if "result" in result:
                    # Try to extract agent response - handle different possible structures
                    try:
                        if "response" in result["result"]:
                            agent_response = result["result"]["response"]["parts"][0]["text"]
                        elif "message" in result["result"]:
                            agent_response = result["result"]["message"]["parts"][0]["text"]
                        elif "content" in result["result"]:
                            agent_response = result["result"]["content"]
                        else:
                            agent_response = str(result["result"])
                        
                        print(f"Agent: {agent_response}")
                    except (KeyError, IndexError) as e:
                        print(f"Could not parse agent response: {e}")
                        print(f"Raw result: {result['result']}")
                    
                    return result
                elif "error" in result:
                    print(f"Agent error: {result['error']}")
                    return result
            else:
                print(f"HTTP error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Request error: {e}")
            return None
    
    def test_single_prompt(self, prompt: str):
        """Test a single prompt"""
        print("\nTesting A2A Communication:")
        print("=" * 50)
        result = self.send_message(prompt)
        return result
    
    def interactive_session(self):
        """Start an interactive chat session"""
        print("\nInteractive A2A Session")
        print("Type 'quit' to exit")
        print("=" * 50)
        
        while True:
            try:
                user_input = input("\nYou: ").strip()
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    print("Goodbye!")
                    break
                
                if user_input:
                    self.send_message(user_input)
                    
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break

def main():
    
    TEST_PROMPT = "What is 1928 + 2938?"
    
    print("A2A Test Client")
    print("=" * 30)
    
    client = A2ATestClient()
    
    print("Authenticating with dev user...")
    if not client.authenticate_with_password("dev", "secret"):
        print("Failed to authenticate. Check your server is running.")
        return
    
    client.test_single_prompt(TEST_PROMPT)

if __name__ == "__main__":
    main()
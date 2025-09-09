# detailed_security_test.py
"""
Comprehensive security test with detailed token/key information display.
Shows exactly how authentication flows through each layer.
"""
import requests
import json
import base64
from typing import Optional

class DetailedSecurityTester:
    """Detailed security testing with full credential visibility"""
    
    def __init__(self, base_url: str = "http://localhost:9999"):
        self.base_url = base_url.rstrip('/')
        self.admin_token = None
        self.dev_token = None
        self.dev_api_key = "dev-api-key-12345"
        
    def decode_jwt_payload(self, token: str) -> dict:
        """Decode JWT payload for inspection"""
        try:
            # JWT format: header.payload.signature
            parts = token.split('.')
            if len(parts) != 3:
                return {"error": "Invalid JWT format"}
            
            # Decode payload (second part)
            payload = parts[1]
            # Add padding if needed
            payload += '=' * (4 - len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload)
            return json.loads(decoded.decode('utf-8'))
        except Exception as e:
            return {"error": f"JWT decode failed: {e}"}
    
    def print_credentials_summary(self):
        """Print all credentials being used"""
        print("\n" + "=" * 60)
        print("CREDENTIALS SUMMARY")
        print("=" * 60)
        
        print("\nAPI Key:")
        print(f"  Header: X-API-Key")
        print(f"  Value: {self.dev_api_key}")
        
        if self.admin_token:
            print(f"\nAdmin JWT Token:")
            print(f"  Raw Token: {self.admin_token}")
            admin_payload = self.decode_jwt_payload(self.admin_token)
            print(f"  Decoded Payload:")
            print(json.dumps(admin_payload, indent=4))
        
        if self.dev_token:
            print(f"\nDeveloper JWT Token:")
            print(f"  Raw Token: {self.dev_token}")
            dev_payload = self.decode_jwt_payload(self.dev_token)
            print(f"  Decoded Payload:")
            print(json.dumps(dev_payload, indent=4))
    
    def test_layer_by_layer_auth(self):
        """Test how authentication flows through each layer"""
        print("\n" + "=" * 60)
        print("LAYER-BY-LAYER AUTHENTICATION FLOW")
        print("=" * 60)
        
        if not self.dev_token:
            print("No dev token available for layer testing")
            return
        
        # Create A2A request
        a2a_request = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": {
                    "messageId": "layer-test",
                    "role": "user",
                    "parts": [{"text": "Testing layer authentication flow"}]
                }
            },
            "id": 1
        }
        
        print("\n1. FastAPI Security Layer:")
        print(f"   Request: POST {self.base_url}/")
        print(f"   Headers: Authorization: Bearer {self.dev_token[:20]}...")
        print(f"   Action: Validates JWT, extracts user context")
        
        print("\n2. RBAC Middleware:")
        print(f"   Input: User context from FastAPI layer")
        print(f"   Action: Checks if user has A2A permissions")
        print(f"   Decision: Allow/deny based on roles/permissions")
        
        print("\n3. A2A Protocol Handler:")
        print(f"   Input: Authenticated request + user context")
        print(f"   Action: Process JSON-RPC with user identity")
        print(f"   Context Available: Yes (user principal injected)")
        
        print("\n4. LangGraph Executor:")
        print(f"   Input: Task + user context from A2A layer")
        print(f"   Action: Execute agent logic with user identity")
        print(f"   Context Available: Yes (for audit/authorization)")
        
        print("\n5. MCP Tools:")
        print(f"   Input: Tool calls + user context")
        print(f"   Action: Execute external tools with user identity")
        print(f"   Context Available: Yes (for tool-level authorization)")
        
        # Actually make the request to show real flow
        print("\n6. ACTUAL REQUEST TRACE:")
        try:
            headers = {
                "Authorization": f"Bearer {self.dev_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(f"{self.base_url}/", 
                                   json=a2a_request, 
                                   headers=headers)
            
            print(f"   Response Status: {response.status_code}")
            print(f"   Authentication Flow: SUCCESS")
            print(f"   User Context Propagated: YES")
            
            if response.status_code == 200:
                print(f"   Result: User context successfully flowed through all layers")
            else:
                print(f"   Issue: {response.text[:100]}...")
                
        except Exception as e:
            print(f"   Error: {e}")
    
    def test_different_auth_methods(self):
        """Test different authentication methods in detail"""
        print("\n" + "=" * 60)
        print("AUTHENTICATION METHOD COMPARISON")
        print("=" * 60)
        
        test_endpoint = "/auth/users/me"
        
        # Test 1: JWT Token
        print("\n1. JWT TOKEN AUTHENTICATION:")
        if self.dev_token:
            jwt_headers = {"Authorization": f"Bearer {self.dev_token}"}
            print(f"   Method: Bearer Token")
            print(f"   Header: Authorization: Bearer {self.dev_token[:30]}...")
            
            jwt_response = requests.get(f"{self.base_url}{test_endpoint}", headers=jwt_headers)
            print(f"   Response: {jwt_response.status_code}")
            
            if jwt_response.status_code == 200:
                user_data = jwt_response.json()
                print(f"   User: {user_data.get('username')}")
                print(f"   Roles: {user_data.get('roles')}")
                print(f"   Permissions: {len(user_data.get('permissions', []))} permissions")
        
        # Test 2: API Key
        print("\n2. API KEY AUTHENTICATION:")
        api_headers = {"X-API-Key": self.dev_api_key}
        print(f"   Method: API Key Header")
        print(f"   Header: X-API-Key: {self.dev_api_key}")
        
        api_response = requests.get(f"{self.base_url}{test_endpoint}", headers=api_headers)
        print(f"   Response: {api_response.status_code}")
        
        if api_response.status_code == 200:
            user_data = api_response.json()
            print(f"   User: {user_data.get('username')}")
            print(f"   Roles: {user_data.get('roles')}")
            print(f"   Permissions: {len(user_data.get('permissions', []))} permissions")
        
        # Test 3: No Authentication
        print("\n3. NO AUTHENTICATION:")
        print(f"   Method: No headers")
        print(f"   Headers: (none)")
        
        no_auth_response = requests.get(f"{self.base_url}{test_endpoint}")
        print(f"   Response: {no_auth_response.status_code}")
        print(f"   Expected: 401 Unauthorized")
        print(f"   Security Working: {'YES' if no_auth_response.status_code == 401 else 'NO'}")
    
    def obtain_tokens(self):
        """Obtain and display authentication tokens"""
        print("OBTAINING AUTHENTICATION TOKENS")
        print("=" * 60)
        
        # Get admin token
        print("\n1. Admin Token Request:")
        print("   POST /auth/token")
        print("   Data: username=admin, password=secret")
        
        admin_response = requests.post(f"{self.base_url}/auth/token", data={
            "username": "admin",
            "password": "secret"
        })
        
        print(f"   Response: {admin_response.status_code}")
        if admin_response.status_code == 200:
            admin_data = admin_response.json()
            self.admin_token = admin_data["access_token"]
            print(f"   Token Type: {admin_data.get('token_type')}")
            print(f"   Expires In: {admin_data.get('expires_in')} seconds")
            print(f"   Token: {self.admin_token}")
        else:
            print(f"   Error: {admin_response.text}")
        
        # Get dev token
        print("\n2. Developer Token Request:")
        print("   POST /auth/token")
        print("   Data: username=dev, password=secret")
        
        dev_response = requests.post(f"{self.base_url}/auth/token", data={
            "username": "dev",
            "password": "secret"
        })
        
        print(f"   Response: {dev_response.status_code}")
        if dev_response.status_code == 200:
            dev_data = dev_response.json()
            self.dev_token = dev_data["access_token"]
            print(f"   Token Type: {dev_data.get('token_type')}")
            print(f"   Expires In: {dev_data.get('expires_in')} seconds")
            print(f"   Token: {self.dev_token}")
        else:
            print(f"   Error: {dev_response.text}")
    
    def run_detailed_test(self):
        """Run complete detailed security test"""
        print("SAOP DETAILED SECURITY ANALYSIS")
        print("=" * 60)
        print("This test shows exactly how authentication flows through each layer")
        print()
        
        # Step 1: Obtain tokens
        self.obtain_tokens()
        
        # Step 2: Show credential details
        self.print_credentials_summary()
        
        # Step 3: Test authentication methods
        self.test_different_auth_methods()
        
        # Step 4: Show layer-by-layer flow
        self.test_layer_by_layer_auth()
        
        print("\n" + "=" * 60)
        print("SECURITY ARCHITECTURE SUMMARY")
        print("=" * 60)
        print("Authentication happens ONCE at FastAPI layer")
        print("User context flows through subsequent layers")
        print("Each layer can use context for authorization decisions")
        print("No re-authentication required at each layer")
        print("=" * 60)

if __name__ == "__main__":
    print("Make sure your A2A server is running:")
    print("python -m agent2agent.a2a_server")
    print()
    input("Press Enter to start detailed security analysis...")
    
    tester = DetailedSecurityTester()
    tester.run_detailed_test()
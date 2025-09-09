# # find_a2a_endpoints.py
# """
# Discover actual A2A endpoints from your running server.
# """
# import requests
# import json

# def find_a2a_endpoints():
#     """Find real A2A endpoints"""
#     base_url = "http://localhost:9999"
    
#     print("Discovering A2A endpoints...")
    
#     # Get agent card to see what's available
#     card_response = requests.get(f"{base_url}/.well-known/agent-card.json")
#     if card_response.status_code == 200:
#         card = card_response.json()
#         print("Agent Card:")
#         print(json.dumps(card, indent=2))
        
#         # Look for endpoint hints
#         if "endpoints" in card:
#             print("\nEndpoints from agent card:")
#             for key, value in card["endpoints"].items():
#                 print(f"  {key}: {value}")
    
#     # Check OpenAPI spec for available endpoints
#     openapi_response = requests.get(f"{base_url}/openapi.json")
#     if openapi_response.status_code == 200:
#         openapi = openapi_response.json()
#         print("\nAvailable paths from OpenAPI:")
#         for path, methods in openapi.get("paths", {}).items():
#             method_list = list(methods.keys())
#             print(f"  {path} - {method_list}")
    
#     # Try some common A2A patterns
#     print("\nTesting common A2A patterns...")
    
#     # Get a dev token first
#     token_response = requests.post(f"{base_url}/auth/token", data={
#         "username": "dev",
#         "password": "secret"
#     })
    
#     if token_response.status_code == 200:
#         token = token_response.json()["access_token"]
#         headers = {"Authorization": f"Bearer {token}"}
        
#         # Test JSON-RPC with proper method
#         jsonrpc_methods = [
#             "agent.status",
#             "agent.capabilities", 
#             "task.create",
#             "task.status",
#             "message.send"
#         ]
        
#         for method in jsonrpc_methods:
#             payload = {
#                 "jsonrpc": "2.0",
#                 "method": method,
#                 "params": {},
#                 "id": 1
#             }
            
#             response = requests.post(
#                 f"{base_url}/jsonrpc",
#                 json=payload,
#                 headers={**headers, "Content-Type": "application/json"}
#             )
            
#             print(f"JSON-RPC {method}: {response.status_code}")
#             if response.status_code == 200:
#                 data = response.json()
#                 print(f"  Response: {json.dumps(data, indent=2)}")

# if __name__ == "__main__":
#     find_a2a_endpoints()






# check_a2a_endpoints.py
"""
Check what endpoints and capabilities the A2A library actually provides.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def inspect_a2a_application():
    """Inspect the A2A application to see what it actually provides"""
    
    try:
        from a2a.server.apps.jsonrpc import A2AStarletteApplication
        from a2a.server.request_handlers import DefaultRequestHandler
        from a2a.server.tasks import InMemoryTaskStore
        from agent2agent.a2a_utils import create_agent_card_from_yaml_file
        from langgraph.langgraph_executor import LangGraphA2AExecutor
        
        print("A2A Library Inspection")
        print("=" * 40)
        
        # Create the same setup as your server
        executor = LangGraphA2AExecutor()
        
        agent_card = create_agent_card_from_yaml_file('a2a_agent_card.yaml')
        
        request_handler = DefaultRequestHandler(
            agent_executor=executor,
            task_store=InMemoryTaskStore()
        )
        
        starlette_app = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler
        )
        
        # Build the ASGI app
        asgi_app = starlette_app.build()
        
        print("A2AStarletteApplication built successfully")
        
        # Check routes
        print("\nInspecting A2A routes...")
        if hasattr(asgi_app, 'routes'):
            for route in asgi_app.routes:
                print(f"Route: {route}")
                if hasattr(route, 'path'):
                    print(f"  Path: {route.path}")
                if hasattr(route, 'methods'):
                    print(f"  Methods: {route.methods}")
        
        # Check if A2AStarletteApplication has specific JSON-RPC endpoints
        print("\nChecking A2AStarletteApplication attributes:")
        for attr in dir(starlette_app):
            if 'jsonrpc' in attr.lower() or 'rpc' in attr.lower():
                print(f"  Found: {attr}")
        
        print("\nChecking DefaultRequestHandler capabilities:")
        for attr in dir(request_handler):
            if not attr.startswith('_'):
                print(f"  Method: {attr}")
        
        return True
        
    except Exception as e:
        print(f"Error inspecting A2A: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_a2a_server_routes():
    """Test what routes your actual running server has"""
    import requests
    
    print("\nTesting actual server routes...")
    base_url = "http://localhost:9999"
    
    # Test different potential JSON-RPC endpoints
    endpoints_to_test = [
        "/jsonrpc",
        "/rpc", 
        "/json-rpc",
        "/api/jsonrpc",
        "/v1/jsonrpc",
        "/"  # Root endpoint
    ]
    
    for endpoint in endpoints_to_test:
        try:
            # Test with a simple JSON-RPC call
            payload = {
                "jsonrpc": "2.0",
                "method": "ping",
                "params": {},
                "id": 1
            }
            
            response = requests.post(f"{base_url}{endpoint}", 
                                   json=payload, 
                                   timeout=2)
            
            print(f"{endpoint}: {response.status_code}")
            if response.status_code not in [404, 405]:
                print(f"  Response: {response.text[:100]}...")
                
        except requests.exceptions.RequestException as e:
            print(f"{endpoint}: Connection error - {e}")

if __name__ == "__main__":
    print("Make sure your A2A server is NOT running for the first test")
    print("Then start it for the second test")
    print()
    
    # First inspect the A2A library capabilities
    if inspect_a2a_application():
        print("\n" + "=" * 40)
        input("Now start your A2A server and press Enter...")
        test_a2a_server_routes()
    else:
        print("Failed to inspect A2A library")
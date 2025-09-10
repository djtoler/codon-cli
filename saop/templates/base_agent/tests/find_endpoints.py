#!/usr/bin/env python3
"""
Debug script to discover what endpoints your A2A server actually has.
"""
import requests
import json

def test_endpoint(url, method="GET", data=None, headers=None):
    """Test an endpoint and return status code and response info"""
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=5)
        elif method == "POST":
            response = requests.post(url, data=data, json=data if isinstance(data, dict) else None, headers=headers, timeout=5)
        
        return {
            "url": url,
            "status": response.status_code,
            "headers": dict(response.headers),
            "text": response.text[:200] + "..." if len(response.text) > 200 else response.text
        }
    except requests.exceptions.RequestException as e:
        return {
            "url": url,
            "status": "ERROR",
            "error": str(e)
        }

def main():
    base_url = "http://localhost:9999"
    
    print("🔍 DEBUGGING A2A SERVER ENDPOINTS")
    print(f"Testing server at: {base_url}")
    print("=" * 60)
    
    # Test basic connectivity
    print("\n📡 BASIC CONNECTIVITY")
    endpoints_to_test = [
        (f"{base_url}/", "GET"),
        (f"{base_url}/docs", "GET"),
        (f"{base_url}/openapi.json", "GET"),
        (f"{base_url}/health", "GET"),
    ]
    
    for url, method in endpoints_to_test:
        result = test_endpoint(url, method)
        status_emoji = "✅" if isinstance(result["status"], int) and result["status"] < 400 else "❌"
        print(f"{status_emoji} {method} {url} -> {result['status']}")
        if result["status"] == 200:
            print(f"   Response: {result['text'][:100]}...")
    
    # Test auth endpoints (original paths)
    print("\n🔐 AUTH ENDPOINTS (Original Paths)")
    auth_endpoints = [
        (f"{base_url}/auth/token", "POST"),
        (f"{base_url}/auth/users/me", "GET"),
        (f"{base_url}/auth/admin/users", "GET"),
        (f"{base_url}/auth/health", "GET"),
    ]
    
    for url, method in auth_endpoints:
        result = test_endpoint(url, method)
        status_emoji = "✅" if isinstance(result["status"], int) and result["status"] < 500 else "❌"
        print(f"{status_emoji} {method} {url} -> {result['status']}")
    
    # Test auth endpoints (updated paths)
    print("\n🔐 AUTH ENDPOINTS (Root Level Paths)")
    root_auth_endpoints = [
        (f"{base_url}/token", "POST"),
        (f"{base_url}/users/me", "GET"),
        (f"{base_url}/admin/users", "GET"),
        (f"{base_url}/developer/permissions", "GET"),
    ]
    
    for url, method in root_auth_endpoints:
        result = test_endpoint(url, method)
        status_emoji = "✅" if isinstance(result["status"], int) and result["status"] < 500 else "❌"
        print(f"{status_emoji} {method} {url} -> {result['status']}")
    
    # Test A2A endpoints
    print("\n🤖 A2A ENDPOINTS")
    a2a_data = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {"message": {"messageId": "test", "role": "user", "parts": [{"text": "hello"}]}},
        "id": 1
    }
    
    a2a_result = test_endpoint(f"{base_url}/", "POST", a2a_data, {"Content-Type": "application/json"})
    status_emoji = "✅" if isinstance(a2a_result["status"], int) else "❌"
    print(f"{status_emoji} POST {base_url}/ (A2A) -> {a2a_result['status']}")
    if a2a_result["status"] != "ERROR":
        print(f"   Response: {a2a_result['text'][:150]}...")
    
    # Try to get OpenAPI schema to see all endpoints
    print("\n📋 DISCOVERING ALL ENDPOINTS")
    try:
        openapi_response = requests.get(f"{base_url}/openapi.json", timeout=5)
        if openapi_response.status_code == 200:
            openapi_data = openapi_response.json()
            paths = openapi_data.get("paths", {})
            print(f"Found {len(paths)} endpoint paths:")
            for path in sorted(paths.keys()):
                methods = list(paths[path].keys())
                print(f"  {path} -> {', '.join(methods).upper()}")
        else:
            print(f"❌ Could not get OpenAPI schema: {openapi_response.status_code}")
    except Exception as e:
        print(f"❌ Error getting OpenAPI schema: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 DIAGNOSIS:")
    print("1. If you see 404s for all auth endpoints -> Routes not mounted")
    print("2. If you see different status codes -> Routes exist but might need different paths")
    print("3. If A2A endpoint works -> Server is running, just missing auth routes")
    print("4. Check the 'DISCOVERING ALL ENDPOINTS' section to see what's actually available")

if __name__ == "__main__":
    main()
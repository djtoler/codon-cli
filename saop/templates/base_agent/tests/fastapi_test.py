#!/usr/bin/env python3
"""
Test script for FastAPI OAuth2 + API Key authentication.
Run this after starting your server with: python app.py
"""

import requests
import json
import sys
from typing import Optional

BASE_URL = "http://localhost:9999"

class AuthTester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.jwt_token: Optional[str] = None
    
    def test_server_health(self) -> bool:
        """Test if server is running"""
        try:
            response = self.session.get(f"{self.base_url}/.well-known/agent.json")
            if response.status_code == 200:
                print("✅ Server is running and A2A endpoints accessible")
                return True
            else:
                print(f"❌ Server responded with status {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            print("❌ Cannot connect to server. Is it running on port 9999?")
            return False
    
    def test_oauth2_token_endpoint(self) -> bool:
        """Test OAuth2 password flow"""
        print("\n🔐 Testing OAuth2 password flow...")
        
        # Test with correct credentials
        data = {
            "username": "admin",
            "password": "secret"
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/auth/token",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.jwt_token = token_data.get("access_token")
                print(f"✅ OAuth2 token received: {self.jwt_token[:20]}...")
                print(f"   Token type: {token_data.get('token_type')}")
                return True
            else:
                print(f"❌ OAuth2 failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ OAuth2 error: {e}")
            return False
    
    def test_oauth2_wrong_credentials(self) -> bool:
        """Test OAuth2 with wrong credentials"""
        print("\n🔒 Testing OAuth2 with wrong credentials...")
        
        data = {
            "username": "admin", 
            "password": "wrong"
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/auth/token",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 401:
                print("✅ Correctly rejected wrong credentials")
                return True
            else:
                print(f"❌ Should have rejected wrong credentials, got: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error testing wrong credentials: {e}")
            return False
    
    def test_jwt_protected_endpoint(self) -> bool:
        """Test protected endpoint with JWT token"""
        if not self.jwt_token:
            print("❌ No JWT token available for testing")
            return False
        
        print("\n🎫 Testing JWT token authentication...")
        
        try:
            headers = {"Authorization": f"Bearer {self.jwt_token}"}
            response = self.session.get(f"{self.base_url}/auth/users/me", headers=headers)
            
            if response.status_code == 200:
                user_data = response.json()
                print(f"✅ JWT auth successful. User: {user_data.get('username')}")
                print(f"   Email: {user_data.get('email')}")
                print(f"   Roles: {user_data.get('roles')}")
                return True
            else:
                print(f"❌ JWT auth failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ JWT auth error: {e}")
            return False
    
    def test_api_key_authentication(self) -> bool:
        """Test API key authentication"""
        print("\n🔑 Testing API key authentication...")
        
        try:
            headers = {"X-API-Key": "dev-api-key-12345"}
            response = self.session.get(f"{self.base_url}/auth/users/me", headers=headers)
            
            if response.status_code == 200:
                user_data = response.json()
                print(f"✅ API key auth successful. User: {user_data.get('username')}")
                print(f"   Email: {user_data.get('email')}")
                print(f"   Roles: {user_data.get('roles')}")
                return True
            else:
                print(f"❌ API key auth failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ API key auth error: {e}")
            return False
    
    def test_invalid_api_key(self) -> bool:
        """Test with invalid API key"""
        print("\n🚫 Testing invalid API key...")
        
        try:
            headers = {"X-API-Key": "invalid-key"}
            response = self.session.get(f"{self.base_url}/auth/users/me", headers=headers)
            
            if response.status_code == 401:
                print("✅ Correctly rejected invalid API key")
                return True
            else:
                print(f"❌ Should have rejected invalid API key, got: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error testing invalid API key: {e}")
            return False
    
    def test_protected_route(self) -> bool:
        """Test the protected demo route"""
        print("\n🛡️ Testing protected route...")
        
        try:
            headers = {"X-API-Key": "dev-api-key-12345"}
            response = self.session.get(f"{self.base_url}/auth/protected", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Protected route accessible. Message: {data.get('message')}")
                return True
            else:
                print(f"❌ Protected route failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Protected route error: {e}")
            return False
    
    def test_unauthenticated_access(self) -> bool:
        """Test accessing protected endpoint without authentication"""
        print("\n🚪 Testing unauthenticated access to protected endpoint...")
        
        try:
            response = self.session.get(f"{self.base_url}/auth/users/me")
            
            if response.status_code == 401:
                print("✅ Correctly blocked unauthenticated access")
                return True
            else:
                print(f"❌ Should have blocked unauthenticated access, got: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error testing unauthenticated access: {e}")
            return False
    
    def test_fastapi_docs(self) -> bool:
        """Test if FastAPI docs are available"""
        print("\n📚 Testing FastAPI documentation...")
        
        try:
            response = self.session.get(f"{self.base_url}/docs")
            
            if response.status_code == 200:
                print("✅ FastAPI docs available at http://localhost:9999/docs")
                return True
            else:
                print(f"❌ FastAPI docs not available: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error accessing FastAPI docs: {e}")
            return False
    
    def run_all_tests(self) -> bool:
        """Run all authentication tests"""
        print("🧪 Starting FastAPI Authentication Tests")
        print("=" * 50)
        
        tests = [
            ("Server Health", self.test_server_health),
            ("OAuth2 Token", self.test_oauth2_token_endpoint),
            ("OAuth2 Wrong Credentials", self.test_oauth2_wrong_credentials),
            ("JWT Protected Endpoint", self.test_jwt_protected_endpoint),
            ("API Key Auth", self.test_api_key_authentication),
            ("Invalid API Key", self.test_invalid_api_key),
            ("Protected Route", self.test_protected_route),
            ("Unauthenticated Access", self.test_unauthenticated_access),
            ("FastAPI Docs", self.test_fastapi_docs),
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            try:
                if test_func():
                    passed += 1
            except Exception as e:
                print(f"❌ {test_name} crashed: {e}")
        
        print("\n" + "=" * 50)
        print(f"📊 Test Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! Your FastAPI authentication is working correctly.")
        else:
            print("⚠️ Some tests failed. Check the output above for details.")
        
        return passed == total

def test_fastapi():
    """Main test function"""
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = BASE_URL
    
    print(f"Testing FastAPI authentication at: {base_url}")
    
    tester = AuthTester(base_url)
    success = tester.run_all_tests()
    
    if not success:
        sys.exit(1)


test_fastapi()


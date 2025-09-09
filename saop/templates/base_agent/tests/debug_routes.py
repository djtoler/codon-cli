# debug_routes.py
"""
Debug script to check if all imports and routes are working correctly.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test all the imports individually"""
    print("Testing imports...")
    
    try:
        from config.agent_config import load_env_config
        print("✅ Config import works")
        config = load_env_config()
        print(f"✅ Config loaded: {config.get('AGENT_NAME')}")
    except Exception as e:
        print(f"❌ Config import failed: {e}")
        return False
    
    try:
        from api.auth import auth_provider, Role, Permission
        print("✅ Auth import works")
    except Exception as e:
        print(f"❌ Auth import failed: {e}")
        return False
    
    try:
        from api.routes import router as auth_router
        print("✅ Routes import works")
        print(f"Routes in router: {[route.path for route in auth_router.routes]}")
    except Exception as e:
        print(f"❌ Routes import failed: {e}")
        return False
    
    try:
        from api.middleware import A2AAuthContextMiddleware
        print("✅ Middleware import works")
    except Exception as e:
        print(f"❌ Middleware import failed: {e}")
        print("Creating minimal middleware...")
        create_minimal_middleware()
        return False
    
    try:
        from api.wrapper import wrap_a2a_with_security
        print("✅ Wrapper import works")
    except Exception as e:
        print(f"❌ Wrapper import failed: {e}")
        return False
    
    return True

def create_minimal_middleware():
    """Create a minimal middleware file if it doesn't exist"""
    middleware_content = '''# api/middleware.py
"""
Minimal A2A authentication context middleware.
"""
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class A2AAuthContextMiddleware(BaseHTTPMiddleware):
    """
    Minimal middleware for A2A authentication context injection.
    """
    
    async def dispatch(self, request: Request, call_next):
        # For now, just pass through - we'll enhance this later
        response = await call_next(request)
        return response
'''
    
    try:
        os.makedirs("api", exist_ok=True)
        with open("api/middleware.py", "w") as f:
            f.write(middleware_content)
        print("✅ Created minimal middleware file")
    except Exception as e:
        print(f"❌ Failed to create middleware: {e}")

def test_fastapi_app():
    """Test creating a minimal FastAPI app with auth routes"""
    print("\nTesting FastAPI app creation...")
    
    if not test_imports():
        return False
    
    try:
        from fastapi import FastAPI
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route
        from api.wrapper import wrap_a2a_with_security
        from config.agent_config import load_env_config
        
        # Create minimal test app
        async def hello(request):
            return JSONResponse({"message": "Hello from test A2A app!"})
        
        test_a2a_app = Starlette(routes=[
            Route("/test", hello),
        ])
        
        config = load_env_config()
        
        # Try wrapping with security
        secured_app = wrap_a2a_with_security(
            test_a2a_app,
            config=config,
            title="Debug Test Agent",
            version="1.0.0-debug"
        )
        
        print("✅ Secured app created successfully")
        
        # Check routes
        print("\nAvailable routes:")
        for route in secured_app.routes:
            if hasattr(route, 'path'):
                methods = getattr(route, 'methods', ['GET'])
                print(f"  {route.path} - {methods}")
        
        return True
        
    except Exception as e:
        print(f"❌ FastAPI app creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("SAOP Route Debugging")
    print("=" * 40)
    
    success = test_fastapi_app()
    
    if success:
        print("\n✅ All components working correctly")
        print("Try running the test again")
    else:
        print("\n❌ Issues found - fix them first")
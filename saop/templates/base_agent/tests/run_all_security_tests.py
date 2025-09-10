#!/usr/bin/env python3
"""
Master test runner for all security requirements validation.
Runs all 3 security tests in sequence and provides a comprehensive summary.
"""

import sys
from test_fastapi_security import FastAPISecurityValidator
from test_rbac_middleware import RBACMiddlewareValidator
from test_a2a_principal_injection import A2APrincipalInjectionValidator

def print_banner(title: str):
    """Print a formatted banner"""
    print("\n" + "=" * 80)
    print(f"{title:^80}")
    print("=" * 80)

def main():
    print_banner("SAOP SECURITY IMPLEMENTATION - COMPLETE VALIDATION")
    print("Testing against: http://localhost:9999")
    print("This validates all security requirements with detailed proof.")
    print()
    print("Prerequisites:")
    print("1. A2A server must be running: python -m agent2agent.a2a_server")
    print("2. Server must have the security implementation")
    print()
    
    # Wait for user confirmation
    try:
        input("Press Enter when your A2A server is ready (Ctrl+C to cancel)...")
    except KeyboardInterrupt:
        print("\nTest cancelled by user.")
        sys.exit(0)
    
    # Track overall results
    results = {}
    
    # Test 1: FastAPI Security
    print_banner("RUNNING: FastAPI Security Validation")
    try:
        fastapi_validator = FastAPISecurityValidator()
        tokens = fastapi_validator.run_validation()
        results['fastapi_security'] = True
        print("✅ FastAPI Security: PASSED")
    except Exception as e:
        print(f"❌ FastAPI Security: FAILED - {e}")
        results['fastapi_security'] = False
        tokens = {}
    
    # Test 2: RBAC Middleware
    print_banner("RUNNING: RBAC Middleware Validation")
    try:
        rbac_validator = RBACMiddlewareValidator()
        rbac_result = rbac_validator.run_validation(tokens)
        results['rbac_middleware'] = rbac_result
        print(f"{'✅' if rbac_result else '❌'} RBAC Middleware: {'PASSED' if rbac_result else 'FAILED'}")
    except Exception as e:
        print(f"❌ RBAC Middleware: FAILED - {e}")
        results['rbac_middleware'] = False
    
    # Test 3: A2A Principal Injection
    print_banner("RUNNING: A2A Principal Injection Validation")
    try:
        a2a_validator = A2APrincipalInjectionValidator()
        a2a_result = a2a_validator.run_validation(tokens)
        results['a2a_principal_injection'] = a2a_result
        print(f"{'✅' if a2a_result else '❌'} A2A Principal Injection: {'PASSED' if a2a_result else 'FAILED'}")
    except Exception as e:
        print(f"❌ A2A Principal Injection: FAILED - {e}")
        results['a2a_principal_injection'] = False
    
    # Final Summary
    print_banner("FINAL SECURITY VALIDATION SUMMARY")
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    
    print(f"Tests Run: {total_tests}")
    print(f"Tests Passed: {passed_tests}")
    print(f"Tests Failed: {total_tests - passed_tests}")
    print()
    
    # Detailed results
    test_names = {
        'fastapi_security': 'REQ-1: FastAPI Security (OAuth2 + API Key)',
        'rbac_middleware': 'REQ-2: RBAC Middleware (admin/dev/view roles)',
        'a2a_principal_injection': 'REQ-3: JWT Principal Injection into A2A RequestContext'
    }
    
    for test_key, test_name in test_names.items():
        status = "✅ PASSED" if results.get(test_key, False) else "❌ FAILED"
        print(f"{status} - {test_name}")
    
    print()
    
    if passed_tests == total_tests:
        print("🎉 ALL SECURITY REQUIREMENTS: SUCCESSFULLY IMPLEMENTED")
        print("Your security implementation meets all requirements with proof!")
        sys.exit(0)
    else:
        print("⚠️  SECURITY VALIDATION INCOMPLETE")
        print("Some security requirements are not properly implemented.")
        print("Please check the failed tests above for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
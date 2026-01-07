#!/usr/bin/env python3
"""
Test Keycloak Authentication Flow
Tests the complete authentication process for SparksBM
"""

import requests
import json
from urllib.parse import urlencode

# Configuration
KEYCLOAK_URL = "http://localhost:8080"
FRONTEND_URL = "http://localhost:3001"
BACKEND_URL = "http://localhost:8070"
REALM = "sparksbm"
CLIENT_ID = "sparksbm"
USERNAME = "admin@sparksbm.com"
PASSWORD = "admin123"

def test_keycloak_health():
    """Test if Keycloak is responding"""
    print("\n1. Testing Keycloak health...")
    try:
        response = requests.get(f"{KEYCLOAK_URL}/health")
        print(f"   ✓ Keycloak is up: {response.status_code}")
        return True
    except Exception as e:
        print(f"   ✗ Keycloak is down: {e}")
        return False

def test_realm_config():
    """Test if realm configuration is accessible"""
    print("\n2. Testing realm configuration...")
    try:
        response = requests.get(f"{KEYCLOAK_URL}/realms/{REALM}/.well-known/openid-configuration")
        if response.status_code == 200:
            config = response.json()
            print(f"   ✓ Realm config accessible")
            print(f"   - Authorization endpoint: {config['authorization_endpoint']}")
            print(f"   - Token endpoint: {config['token_endpoint']}")
            return True
        else:
            print(f"   ✗ Realm config failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

def test_password_grant():
    """Test password grant authentication"""
    print("\n3. Testing password grant authentication...")
    try:
        data = {
            "username": USERNAME,
            "password": PASSWORD,
            "grant_type": "password",
            "client_id": CLIENT_ID
        }
        response = requests.post(
            f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if response.status_code == 200:
            token_data = response.json()
            print(f"   ✓ Authentication successful")
            print(f"   - Access token obtained (length: {len(token_data['access_token'])})")
            print(f"   - Token type: {token_data.get('token_type')}")
            print(f"   - Expires in: {token_data.get('expires_in')} seconds")
            return token_data['access_token']
        else:
            print(f"   ✗ Authentication failed: {response.status_code}")
            print(f"   - Response: {response.text}")
            return None
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return None

def test_backend_with_token(token):
    """Test backend API with token"""
    print("\n4. Testing backend API with token...")
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Origin": FRONTEND_URL
        }
        response = requests.get(f"{BACKEND_URL}/domains", headers=headers)
        print(f"   - Response status: {response.status_code}")
        print(f"   - CORS headers:")
        for header, value in response.headers.items():
            if 'access-control' in header.lower():
                print(f"     {header}: {value}")
        
        if response.status_code == 200:
            print(f"   ✓ Backend API accessible with token")
            return True
        else:
            print(f"   ✗ Backend API failed: {response.text}")
            return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

def test_frontend():
    """Test if frontend is responding"""
    print("\n5. Testing frontend...")
    try:
        response = requests.get(FRONTEND_URL)
        if response.status_code == 200:
            print(f"   ✓ Frontend is accessible")
            return True
        else:
            print(f"   ✗ Frontend returned: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

def test_cors_preflight():
    """Test CORS preflight request"""
    print("\n6. Testing CORS preflight...")
    try:
        headers = {
            "Origin": FRONTEND_URL,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization"
        }
        response = requests.options(f"{BACKEND_URL}/domains", headers=headers)
        print(f"   - Response status: {response.status_code}")
        print(f"   - CORS headers:")
        for header, value in response.headers.items():
            if 'access-control' in header.lower():
                print(f"     {header}: {value}")
        
        if 'Access-Control-Allow-Origin' in response.headers:
            print(f"   ✓ Backend CORS configured")
            return True
        else:
            print(f"   ✗ Backend CORS not configured")
            return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

def main():
    print("=" * 60)
    print("SparksBM Authentication Flow Test")
    print("=" * 60)
    
    # Run all tests
    results = []
    results.append(("Keycloak Health", test_keycloak_health()))
    results.append(("Realm Config", test_realm_config()))
    
    token = test_password_grant()
    results.append(("Password Grant Auth", token is not None))
    
    if token:
        results.append(("Backend API with Token", test_backend_with_token(token)))
    
    results.append(("Frontend Accessible", test_frontend()))
    results.append(("CORS Preflight", test_cors_preflight()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:.<40} {status}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All authentication components working!")
    else:
        print("\n✗ Some components need attention")
    
    return passed == total

if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)

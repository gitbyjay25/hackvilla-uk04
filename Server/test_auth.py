"""
Test Google OAuth endpoints
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_google_oauth_status():
    """Test /auth/google/status endpoint"""
    print("\n=== Testing /auth/google/status ===")
    response = requests.get(f"{BASE_URL}/auth/google/status")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_google_auth_url():
    """Test /auth/google endpoint"""
    print("\n=== Testing /auth/google ===")
    response = requests.get(f"{BASE_URL}/auth/google")
    print(f"Status Code: {response.status_code}")
    result = response.json()
    print(f"Auth URL: {result.get('auth_url', 'N/A')[:100]}...")
    return response.status_code == 200

def test_health():
    """Test /api/v1/health endpoint"""
    print("\n=== Testing /api/v1/health ===")
    response = requests.get(f"{BASE_URL}/api/v1/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

if __name__ == "__main__":
    print("🧪 Testing Nexarch API Endpoints...")
    print(f"Base URL: {BASE_URL}")
    
    # Wait for server to be ready
    print("\nWaiting for server to start...")
    time.sleep(2)
    
    results = []
    
    try:
        results.append(("Health Check", test_health()))
        results.append(("Google OAuth Status", test_google_oauth_status()))
        results.append(("Google Auth URL", test_google_auth_url()))
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    # Summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status} - {name}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️  Some tests failed")

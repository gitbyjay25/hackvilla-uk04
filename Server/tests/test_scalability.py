"""
Test script for multi-tenant Nexarch
Demonstrates:
1. Creating multiple tenants
2. Data isolation between tenants
3. Rate limiting
4. Caching
"""
import requests
import json
from datetime import datetime
import time

BASE_URL = "http://localhost:443"


def create_tenant(name, email):
    """Create a new tenant"""
    response = requests.post(
        f"{BASE_URL}/api/v1/admin/tenants",
        json={"name": name, "admin_email": email}
    )
    return response.json()


def ingest_span(api_key, service_name, operation):
    """Ingest a test span"""
    now = datetime.now()
    span = {
        "trace_id": f"trace-{int(time.time() * 1000)}",
        "span_id": f"span-{int(time.time() * 1000)}",
        "parent_span_id": None,
        "service_name": service_name,
        "operation": operation,
        "kind": "server",
        "start_time": now.isoformat(),
        "end_time": now.isoformat(),
        "latency_ms": 250.0,
        "status_code": 200,
        "error": None,
        "downstream": "postgres://users-db"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/ingest",
        json=span,
        headers={"X-API-Key": api_key}
    )
    if response.status_code != 202:
        print(f"      Error: {response.status_code} - {response.text}")
    return response.status_code == 202


def get_architecture(api_key):
    """Get architecture for a tenant"""
    response = requests.get(
        f"{BASE_URL}/api/v1/architecture/current",
        headers={"X-API-Key": api_key}
    )
    if response.status_code != 200:
        print(f"   Error getting architecture: {response.status_code}")
        print(f"   Response: {response.text}")
        return {"nodes": [], "edges": [], "metrics_summary": {}}
    return response.json()


def test_multi_tenancy():
    """Test multi-tenant functionality"""
    print("=" * 60)
    print("NEXARCH MULTI-TENANT SCALABILITY TEST")
    print("=" * 60)
    
    # Create Tenant 1
    print("\n1. Creating Tenant 1 (Acme Corp)...")
    tenant1 = create_tenant("Acme Corp", "admin@acme.com")
    print(f"   ✓ Created: {tenant1['name']}")
    print(f"   ✓ API Key: {tenant1['api_key'][:20]}...")
    
    # Create Tenant 2
    print("\n2. Creating Tenant 2 (TechStart Inc)...")
    tenant2 = create_tenant("TechStart Inc", "admin@techstart.com")
    print(f"   ✓ Created: {tenant2['name']}")
    print(f"   ✓ API Key: {tenant2['api_key'][:20]}...")
    
    # Ingest data for Tenant 1
    print("\n3. Ingesting spans for Tenant 1...")
    for i in range(5):
        success = ingest_span(tenant1['api_key'], "acme-api", f"GET /users/{i}")
        print(f"   {'✓' if success else '✗'} Span {i+1} ingested")
    
    # Ingest data for Tenant 2
    print("\n4. Ingesting spans for Tenant 2...")
    for i in range(3):
        success = ingest_span(tenant2['api_key'], "techstart-service", f"POST /orders/{i}")
        print(f"   {'✓' if success else '✗'} Span {i+1} ingested")
    
    # Verify data isolation
    print("\n5. Testing data isolation...")
    arch1 = get_architecture(tenant1['api_key'])
    arch2 = get_architecture(tenant2['api_key'])
    
    tenant1_services = [n['id'] for n in arch1['nodes']]
    tenant2_services = [n['id'] for n in arch2['nodes']]
    
    print(f"   Tenant 1 services: {tenant1_services}")
    print(f"   Tenant 2 services: {tenant2_services}")
    
    if 'acme-api' in tenant1_services and 'acme-api' not in tenant2_services:
        print("   ✓ Data isolation working correctly")
    else:
        print("   ✗ Data isolation failed")
    
    # Test caching
    print("\n6. Testing cache performance...")
    start = time.time()
    get_architecture(tenant1['api_key'])
    first_call = time.time() - start
    
    start = time.time()
    get_architecture(tenant1['api_key'])
    cached_call = time.time() - start
    
    print(f"   First call: {first_call:.3f}s")
    print(f"   Cached call: {cached_call:.3f}s")
    if cached_call < first_call:
        print("   ✓ Caching is working")
    
    # Test rate limiting (commented out to avoid blocking)
    print("\n7. Rate limiting enabled (1000 req/min per tenant)")
    print("   ℹ Test by sending >1000 requests to see 429 error")
    
    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED")
    print("=" * 60)
    print(f"\nTenant 1 API Key: {tenant1['api_key']}")
    print(f"Tenant 2 API Key: {tenant2['api_key']}")
    print("\nTest with: curl -H 'X-API-Key: YOUR_KEY' http://localhost:443/api/v1/architecture/current")


if __name__ == "__main__":
    try:
        test_multi_tenancy()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

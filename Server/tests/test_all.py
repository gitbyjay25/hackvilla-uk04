"""
Nexarch Test Suite (ASCII-Safe)
Tests all server endpoints and bug fixes
"""
import requests
import time
import sys
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"


class NexarchTestSuite:
    """Test suite for Nexarch platform"""
    
    def __init__(self):
        self.session = requests.Session()
        self.tenant_id = None
        self.api_key = None
        self.passed = 0
        self.failed = 0
    
    def headers(self):
        return {"X-API-Key": self.api_key} if self.api_key else {}
    
    def log(self, name, passed, details=""):
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {name}")
        if details:
            print(f"       -> {details}")
        if passed:
            self.passed += 1
        else:
            self.failed += 1
    
    def run_test(self, name, test_func):
        try:
            result = test_func()
            self.log(name, True, result if isinstance(result, str) else "")
        except AssertionError as e:
            self.log(name, False, str(e))
        except Exception as e:
            self.log(name, False, f"Exception: {type(e).__name__}: {e}")
    
    # === TESTS ===
    
    def test_health(self):
        response = self.session.get(f"{BASE_URL}/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        return f"Status: {data['status']}"
    
    def test_create_tenant(self):
        response = self.session.post(f"{BASE_URL}/api/v1/admin/tenants", json={
            "name": f"Test Tenant {datetime.now().strftime('%H%M%S')}",
            "admin_email": "test@nexarch.dev"
        })
        assert response.status_code == 200
        data = response.json()
        self.tenant_id = data.get("tenant_id")
        self.api_key = data.get("api_key")
        assert self.tenant_id and self.api_key
        return f"Tenant: {self.tenant_id[:16]}..."
    
    def test_ingest_single(self):
        span = {
            "trace_id": f"trace-{int(time.time())}",
            "span_id": f"span-{int(time.time())}",
            "service_name": "test-service",
            "operation": "GET /api/test",
            "kind": "server",
            "start_time": datetime.utcnow().isoformat(),
            "end_time": (datetime.utcnow() + timedelta(milliseconds=50)).isoformat(),
            "latency_ms": 50.0,
            "status_code": 200,
            "downstream": "test-db"
        }
        response = self.session.post(
            f"{BASE_URL}/api/v1/ingest",
            headers=self.headers(),
            json=span
        )
        assert response.status_code == 202, f"Got {response.status_code}: {response.text}"
        return "Span ingested"
    
    def test_ingest_batch(self):
        """Test batch ingestion - FIXED BUG: correct path and format"""
        now = datetime.utcnow()
        spans = [
            {
                "trace_id": f"batch-{i}",
                "span_id": f"span-{i}",
                "service_name": "batch-svc",
                "operation": f"GET /batch/{i}",
                "kind": "server",
                "start_time": now.isoformat(),
                "end_time": (now + timedelta(milliseconds=100)).isoformat(),
                "latency_ms": 100.0,
                "status_code": 200
            }
            for i in range(5)
        ]
        response = self.session.post(
            f"{BASE_URL}/api/v1/ingest/batch",
            headers=self.headers(),
            json=spans
        )
        assert response.status_code == 202, f"Got {response.status_code}: {response.text}"
        data = response.json()
        return f"Batch: {data.get('count', 0)} spans"
    
    def test_architecture_discovery(self):
        """Test architecture discovery - FIXED BUG: model now has version/middleware fields"""
        discovery = {
            "service_name": "discovery-test",
            "service_type": "microservice",
            "version": "1.0.0",
            "endpoints": [{"path": "/api/users", "methods": ["GET"]}],
            "databases": [{"type": "postgres", "engine": "psycopg2"}],
            "external_services": ["https://api.example.com"],
            "middleware": ["CORS", "Auth"],
            "dependencies": {},
            "architecture_patterns": {"has_caching": True},
            "discovered_at": datetime.utcnow().isoformat()
        }
        response = self.session.post(
            f"{BASE_URL}/api/v1/ingest/architecture-discovery",
            headers=self.headers(),
            json=discovery
        )
        assert response.status_code == 202, f"Got {response.status_code}: {response.text}"
        data = response.json()
        return f"Service: {data.get('service', 'N/A')}"
    
    def test_sample_data(self):
        response = self.session.post(
            f"{BASE_URL}/demo/generate-sample-data?count=20",
            headers=self.headers()
        )
        assert response.status_code == 200
        data = response.json()
        return f"Generated: {data.get('count', 0)} spans"
    
    def test_dashboard(self):
        response = self.session.get(
            f"{BASE_URL}/api/v1/dashboard/overview",
            headers=self.headers()
        )
        assert response.status_code == 200
        data = response.json()
        return f"Services: {data.get('total_services', 0)}"
    
    def test_architecture_graph(self):
        response = self.session.get(
            f"{BASE_URL}/api/v1/architecture/graph",
            headers=self.headers()
        )
        assert response.status_code == 200
        data = response.json()
        return f"Nodes: {len(data.get('nodes', []))}"
    
    def test_issues(self):
        response = self.session.get(
            f"{BASE_URL}/api/v1/architecture/issues",
            headers=self.headers()
        )
        assert response.status_code == 200
        data = response.json()
        return f"Issues: {len(data.get('issues', []))}"
    
    def test_workflows(self):
        response = self.session.post(
            f"{BASE_URL}/api/v1/workflows/generate",
            headers=self.headers()
        )
        assert response.status_code == 200
        data = response.json()
        return f"Workflows: {len(data.get('workflows', []))}"
    
    def test_stats(self):
        response = self.session.get(
            f"{BASE_URL}/system/stats",
            headers=self.headers()
        )
        assert response.status_code == 200
        data = response.json()
        return f"Spans: {data.get('total_spans', 0)}"
    
    def test_cleanup(self):
        response = self.session.delete(
            f"{BASE_URL}/demo/clear-data",
            headers=self.headers()
        )
        assert response.status_code == 200
        return "Data cleared"
    
    def run_all(self):
        print("=" * 60)
        print("  NEXARCH TEST SUITE")
        print("=" * 60)
        
        tests = [
            ("Health Check", self.test_health),
            ("Create Tenant", self.test_create_tenant),
            ("Ingest Single Span", self.test_ingest_single),
            ("Ingest Batch (Bug Fix)", self.test_ingest_batch),
            ("Architecture Discovery (Bug Fix)", self.test_architecture_discovery),
            ("Generate Sample Data", self.test_sample_data),
            ("Dashboard Overview", self.test_dashboard),
            ("Architecture Graph", self.test_architecture_graph),
            ("Issue Detection", self.test_issues),
            ("Workflow Generation", self.test_workflows),
            ("System Stats", self.test_stats),
            ("Cleanup", self.test_cleanup),
        ]
        
        for name, func in tests:
            self.run_test(name, func)
        
        print("=" * 60)
        total = self.passed + self.failed
        if self.failed == 0:
            print(f"  ALL TESTS PASSED: {self.passed}/{total}")
        else:
            print(f"  RESULTS: {self.passed} passed, {self.failed} failed")
        print("=" * 60)
        
        return self.failed == 0


def main():
    print("\nChecking server status...")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
        if response.status_code == 200:
            print("Server is running\n")
        else:
            print(f"Server returned {response.status_code}")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"Cannot connect to {BASE_URL}")
        print("Start server: cd Server && python -m uvicorn main:app --port 8000")
        sys.exit(1)
    
    suite = NexarchTestSuite()
    success = suite.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

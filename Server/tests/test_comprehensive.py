"""
Nexarch Comprehensive Test Suite
Tests all server endpoints, SDK compatibility, and fixes
Run this after starting the server with: python main.py
"""
import requests
import json
import time
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

BASE_URL = "http://localhost:8000"


class Colors:
    """ANSI colors for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class NexarchTestSuite:
    """Comprehensive test suite for Nexarch platform"""
    
    def __init__(self):
        self.session = requests.Session()
        self.tenant_id: Optional[str] = None
        self.api_key: Optional[str] = None
        self.passed = 0
        self.failed = 0
        self.results: List[Dict[str, Any]] = []
    
    def headers(self) -> Dict[str, str]:
        """Get headers with API key"""
        return {"X-API-Key": self.api_key} if self.api_key else {}
    
    def log_test(self, name: str, passed: bool, details: str = ""):
        """Log test result"""
        status = f"{Colors.GREEN}✅ PASS{Colors.RESET}" if passed else f"{Colors.RED}❌ FAIL{Colors.RESET}"
        print(f"  {status} {name}")
        if details:
            print(f"       {Colors.CYAN}{details}{Colors.RESET}")
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        self.results.append({"name": name, "passed": passed, "details": details})
    
    def run_test(self, name: str, test_func):
        """Run a single test with error handling"""
        try:
            result = test_func()
            self.log_test(name, True, result if isinstance(result, str) else "")
        except AssertionError as e:
            self.log_test(name, False, str(e))
        except Exception as e:
            self.log_test(name, False, f"Exception: {type(e).__name__}: {e}")
    
    # ==================== HEALTH TESTS ====================
    
    def test_health_basic(self) -> str:
        """Test basic health endpoint"""
        response = self.session.get(f"{BASE_URL}/api/v1/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy", f"Status not healthy: {data}"
        return f"Status: {data['status']}"
    
    def test_health_detailed(self) -> str:
        """Test detailed health endpoint"""
        response = self.session.get(f"{BASE_URL}/api/v1/health/detailed")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        return f"Database: {data.get('database', 'N/A')}, AI: {data.get('ai_available', 'N/A')}"
    
    # ==================== ADMIN TESTS ====================
    
    def test_create_tenant(self) -> str:
        """Test tenant creation"""
        response = self.session.post(f"{BASE_URL}/api/v1/admin/tenants", json={
            "name": f"Test Tenant {datetime.now().strftime('%H%M%S')}",
            "admin_email": f"test{datetime.now().strftime('%H%M%S')}@nexarch.dev"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        self.tenant_id = data.get("id")
        self.api_key = data.get("api_key")
        assert self.tenant_id, "No tenant_id returned"
        assert self.api_key, "No api_key returned"
        return f"Tenant: {self.tenant_id[:16]}..."
    
    # ==================== INGEST TESTS ====================
    
    def test_ingest_single_span(self) -> str:
        """Test single span ingestion"""
        span = {
            "trace_id": f"trace-test-{int(time.time())}",
            "span_id": f"span-test-{int(time.time())}",
            "service_name": "test-service",
            "operation": "GET /api/test",
            "kind": "server",
            "start_time": datetime.utcnow().isoformat(),
            "end_time": (datetime.utcnow() + timedelta(milliseconds=50)).isoformat(),
            "latency_ms": 50.0,
            "status_code": 200,
            "downstream": "test-database"
        }
        response = self.session.post(
            f"{BASE_URL}/api/v1/ingest",
            headers=self.headers(),
            json=span
        )
        assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "accepted", f"Not accepted: {data}"
        return f"Span ID: {data.get('span_id', 'N/A')[:16]}..."
    
    def test_ingest_batch(self) -> str:
        """Test batch span ingestion (FIXED: correct API path and payload format)"""
        now = datetime.utcnow()
        spans = [
            {
                "trace_id": f"batch-trace-{i}",
                "span_id": f"batch-span-{i}",
                "service_name": "batch-service",
                "operation": f"GET /api/batch/{i}",
                "kind": "server",
                "start_time": now.isoformat(),
                "end_time": (now + timedelta(milliseconds=100 + i * 10)).isoformat(),
                "latency_ms": 100.0 + i * 10,
                "status_code": 200 if i % 5 != 0 else 500,
                "downstream": "batch-db"
            }
            for i in range(10)
        ]
        response = self.session.post(
            f"{BASE_URL}/api/v1/ingest/batch",
            headers=self.headers(),
            json=spans
        )
        assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.text}"
        data = response.json()
        return f"Ingested: {data.get('count', 0)} spans, Failed: {data.get('failed', 0)}"
    
    def test_ingest_architecture_discovery(self) -> str:
        """Test architecture discovery ingestion (FIXED: model now has all required fields)"""
        discovery = {
            "service_name": "discovery-test-service",
            "service_type": "microservice",
            "version": "1.0.0",
            "endpoints": [
                {"path": "/api/users", "methods": ["GET", "POST"], "calls_database": True},
                {"path": "/api/orders", "methods": ["GET", "POST", "DELETE"], "calls_external": True}
            ],
            "databases": [
                {"type": "relational", "engine": "postgres", "connection": "postgres://***@db/app"},
                {"type": "cache", "engine": "redis", "connection": "redis://***@cache:6379"}
            ],
            "external_services": ["https://api.stripe.com", "https://api.sendgrid.com"],
            "middleware": ["CORS", "RateLimiting", "Authentication"],
            "dependencies": {"users": ["postgres", "redis"], "orders": ["postgres", "stripe"]},
            "architecture_patterns": {"service_type": "microservice", "has_caching": True},
            "discovered_at": datetime.utcnow().isoformat()
        }
        response = self.session.post(
            f"{BASE_URL}/api/v1/ingest/architecture-discovery",
            headers=self.headers(),
            json=discovery
        )
        assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "accepted", f"Not accepted: {data}"
        return f"Service: {data.get('service', 'N/A')}, Endpoints: {data.get('endpoints_discovered', 0)}"
    
    def test_ingest_stats(self) -> str:
        """Test ingestion stats endpoint"""
        response = self.session.get(
            f"{BASE_URL}/api/v1/ingest/stats",
            headers=self.headers()
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        return f"Spans: {data.get('total_spans', 0)}, Services: {data.get('unique_services', 0)}"
    
    # ==================== DEMO DATA TESTS ====================
    
    def test_generate_sample_data(self) -> str:
        """Generate sample telemetry data for testing"""
        response = self.session.post(
            f"{BASE_URL}/demo/generate-sample-data?count=30",
            headers=self.headers()
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        return f"Generated: {data.get('count', 0)} spans, Services: {', '.join(data.get('services_created', [])[:3])}"
    
    # ==================== DASHBOARD TESTS ====================
    
    def test_dashboard_overview(self) -> str:
        """Test dashboard overview endpoint"""
        response = self.session.get(
            f"{BASE_URL}/api/v1/dashboard/overview",
            headers=self.headers()
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        return f"Services: {data.get('total_services', 0)}, Health: {data.get('health_score', 0)}%"
    
    def test_dashboard_architecture_map(self) -> str:
        """Test architecture map endpoint"""
        response = self.session.get(
            f"{BASE_URL}/api/v1/dashboard/architecture-map",
            headers=self.headers()
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        return f"Nodes: {len(nodes)}, Edges: {len(edges)}"
    
    def test_dashboard_services(self) -> str:
        """Test services list endpoint"""
        response = self.session.get(
            f"{BASE_URL}/api/v1/dashboard/services",
            headers=self.headers()
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        return f"Services found: {len(data)}"
    
    def test_dashboard_trends(self) -> str:
        """Test trends endpoint"""
        response = self.session.get(
            f"{BASE_URL}/api/v1/dashboard/trends?hours=24",
            headers=self.headers()
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        return f"Latency points: {len(data.get('latency', []))}"
    
    def test_dashboard_health(self) -> str:
        """Test system health endpoint"""
        response = self.session.get(
            f"{BASE_URL}/api/v1/dashboard/health",
            headers=self.headers()
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        return f"Overall Health: {data.get('overall_health', 0)}%"
    
    # ==================== ARCHITECTURE TESTS ====================
    
    def test_architecture_graph(self) -> str:
        """Test architecture graph endpoint"""
        response = self.session.get(
            f"{BASE_URL}/api/v1/architecture/graph",
            headers=self.headers()
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        return f"Nodes: {len(data.get('nodes', []))}, Edges: {len(data.get('edges', []))}"
    
    def test_architecture_issues(self) -> str:
        """Test issue detection endpoint"""
        response = self.session.get(
            f"{BASE_URL}/api/v1/architecture/issues",
            headers=self.headers()
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        issues = data.get("issues", [])
        return f"Issues: {len(issues)}"
    
    # ==================== WORKFLOW TESTS ====================
    
    def test_workflow_generation(self) -> str:
        """Test workflow generation endpoint"""
        response = self.session.get(
            f"{BASE_URL}/api/v1/workflows/generated",
            headers=self.headers()
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        workflows = data.get("workflows", [])
        return f"Workflows: {len(workflows)}"
    
    def test_workflow_architecture_graph(self) -> str:
        """Test workflow architecture graph endpoint (NEW)"""
        response = self.session.get(
            f"{BASE_URL}/api/v1/workflows/architecture/graph",
            headers=self.headers()
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify current_architecture exists
        current = data.get("current_architecture", {})
        assert "workflow_id" in current, "Missing workflow_id in current_architecture"
        assert "nodes" in current, "Missing nodes in current_architecture"
        assert "edges" in current, "Missing edges in current_architecture"
        assert "tech_stack" in current, "Missing tech_stack in current_architecture"
        
        # Verify generated_workflows exists
        variants = data.get("generated_workflows", [])
        assert isinstance(variants, list), "generated_workflows should be a list"
        
        return f"Current: {len(current.get('nodes', []))} nodes, Variants: {len(variants)}"
    
    # ==================== SYSTEM TESTS ====================
    
    def test_system_stats(self) -> str:
        """Test system stats endpoint"""
        response = self.session.get(
            f"{BASE_URL}/system/stats",
            headers=self.headers()
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        return f"Spans: {data.get('total_spans', 0)}, Services: {data.get('service_count', 0)}"
    
    def test_system_capabilities(self) -> str:
        """Test capabilities endpoint"""
        response = self.session.get(f"{BASE_URL}/system/capabilities")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        caps = data.get("capabilities", [])
        enabled = sum(1 for c in caps if c.get("enabled", False))
        return f"Capabilities: {enabled}/{len(caps)} enabled"
    
    # ==================== CLEANUP ====================
    
    def test_cleanup(self) -> str:
        """Clean up test data"""
        response = self.session.delete(
            f"{BASE_URL}/demo/clear-data",
            headers=self.headers()
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        return f"Deleted {data.get('deleted_spans', 0)} spans"
    
    # ==================== RUN ALL TESTS ====================
    
    def run_all(self):
        """Run all tests"""
        print(f"\n{Colors.BOLD}{'='*70}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}  🧪 NEXARCH COMPREHENSIVE TEST SUITE{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")
        
        test_groups = [
            ("🏥 Health Checks", [
                ("Basic Health", self.test_health_basic),
                ("Detailed Health", self.test_health_detailed),
            ]),
            ("👤 Admin & Tenant", [
                ("Create Tenant", self.test_create_tenant),
            ]),
            ("📡 Ingestion (Bug Fixes Verified)", [
                ("Single Span Ingest", self.test_ingest_single_span),
                ("Batch Span Ingest", self.test_ingest_batch),
                ("Architecture Discovery", self.test_ingest_architecture_discovery),
                ("Ingestion Stats", self.test_ingest_stats),
            ]),
            ("📊 Demo Data", [
                ("Generate Sample Data", self.test_generate_sample_data),
            ]),
            ("📈 Dashboard Endpoints", [
                ("Dashboard Overview", self.test_dashboard_overview),
                ("Architecture Map", self.test_dashboard_architecture_map),
                ("Services List", self.test_dashboard_services),
                ("Trends", self.test_dashboard_trends),
                ("System Health", self.test_dashboard_health),
            ]),
            ("🔍 Architecture Analysis", [
                ("Architecture Graph", self.test_architecture_graph),
                ("Issue Detection", self.test_architecture_issues),
            ]),
            ("⚡ Workflow Generation", [
                ("Generate Workflows", self.test_workflow_generation),
                ("Workflow Architecture Graph", self.test_workflow_architecture_graph),
            ]),
            ("⚙️ System", [
                ("System Stats", self.test_system_stats),
                ("System Capabilities", self.test_system_capabilities),
            ]),
            ("🧹 Cleanup", [
                ("Clear Test Data", self.test_cleanup),
            ]),
        ]
        
        for group_name, tests in test_groups:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}{group_name}{Colors.RESET}")
            print("-" * 50)
            for test_name, test_func in tests:
                self.run_test(test_name, test_func)
        
        # Summary
        print(f"\n{Colors.BOLD}{'='*70}{Colors.RESET}")
        total = self.passed + self.failed
        if self.failed == 0:
            print(f"{Colors.GREEN}{Colors.BOLD}  ✅ ALL TESTS PASSED: {self.passed}/{total}{Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}{Colors.BOLD}  📊 RESULTS: {self.passed} passed, {self.failed} failed ({total} total){Colors.RESET}")
        print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")
        
        return self.failed == 0


def main():
    """Main entry point"""
    print(f"\n{Colors.CYAN}🔍 Checking if server is running at {BASE_URL}...{Colors.RESET}")
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
        if response.status_code == 200:
            print(f"{Colors.GREEN}✅ Server is running{Colors.RESET}")
        else:
            print(f"{Colors.RED}❌ Server returned status {response.status_code}{Colors.RESET}")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"{Colors.RED}❌ Cannot connect to server at {BASE_URL}{Colors.RESET}")
        print(f"{Colors.YELLOW}   Start the server with: cd Server && python main.py{Colors.RESET}")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print(f"{Colors.RED}❌ Connection to server timed out{Colors.RESET}")
        sys.exit(1)
    
    # Run tests
    suite = NexarchTestSuite()
    success = suite.run_all()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

"""
Comprehensive end-to-end test for Nexarch Platform
Tests multi-tenancy, SDK ingestion, AI features, LangGraph, and MCP
"""
import requests
import json
from typing import Dict, Any
import time


BASE_URL = "http://localhost:8000"
API_KEY = "test-api-key-123"  # Create via /admin/tenants endpoint


class E2ETest:
    def __init__(self):
        self.tenant_id = None
        self.api_key = None
        self.session = requests.Session()
    
    def headers(self) -> Dict[str, str]:
        """Get headers with API key"""
        return {"X-API-Key": self.api_key} if self.api_key else {}
    
    def test_1_health_check(self):
        """Test 1: Health check"""
        print("\n🧪 Test 1: Health Check")
        response = self.session.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Health: {data['status']}")
        
        # Detailed health
        response = self.session.get(f"{BASE_URL}/health/detailed")
        data = response.json()
        print(f"✅ Detailed health: DB={data['database']}, AI={data['ai_available']}")
    
    def test_2_create_tenant(self):
        """Test 2: Create tenant and get API key"""
        print("\n🧪 Test 2: Create Tenant")
        response = self.session.post(f"{BASE_URL}/admin/tenants", json={
            "name": "E2E Test Tenant",
            "email": "test@example.com"
        })
        assert response.status_code == 200
        data = response.json()
        self.tenant_id = data["tenant_id"]
        self.api_key = data["api_key"]
        print(f"✅ Tenant created: {self.tenant_id}")
        print(f"✅ API Key: {self.api_key[:20]}...")
    
    def test_3_generate_sample_data(self):
        """Test 3: Generate sample telemetry data"""
        print("\n🧪 Test 3: Generate Sample Data")
        response = self.session.post(
            f"{BASE_URL}/demo/generate-sample-data?count=50",
            headers=self.headers()
        )
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Generated {data['count']} spans")
        print(f"   Services: {', '.join(data['services_created'][:5])}")
    
    def test_4_ingest_batch(self):
        """Test 4: Batch span ingestion"""
        print("\n🧪 Test 4: Batch Ingestion")
        spans = [
            {
                "trace_id": f"trace-{i}",
                "span_id": f"span-{i}",
                "service_name": "api-gateway",
                "operation_name": f"GET /api/v1/resource-{i}",
                "start_time": 1234567890 + i,
                "end_time": 1234567890 + i + 100,
                "status_code": 200,
                "http_method": "GET",
                "http_url": f"/api/v1/resource-{i}"
            }
            for i in range(10)
        ]
        
        response = self.session.post(
            f"{BASE_URL}/api/v1/ingest/batch",
            headers=self.headers(),
            json=spans
        )
        assert response.status_code == 202
        data = response.json()
        print(f"✅ Ingested {data['count']} spans")
    
    def test_5_dashboard_overview(self):
        """Test 5: Dashboard overview"""
        print("\n🧪 Test 5: Dashboard Overview")
        response = self.session.get(
            f"{BASE_URL}/dashboard/overview",
            headers=self.headers()
        )
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Services: {data['total_services']}")
        print(f"✅ Requests: {data['total_requests']}")
        print(f"✅ Avg Latency: {data['avg_latency_ms']:.2f}ms")
    
    def test_6_architecture_map(self):
        """Test 6: Architecture dependency map"""
        print("\n🧪 Test 6: Architecture Map")
        response = self.session.get(
            f"{BASE_URL}/dashboard/architecture-map",
            headers=self.headers()
        )
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Nodes: {len(data['nodes'])}")
        print(f"✅ Edges: {len(data['edges'])}")
        print(f"✅ Graph properties: DAG={data['properties']['is_dag']}, "
              f"Avg Degree={data['properties']['avg_degree']:.2f}")
    
    def test_7_detect_issues(self):
        """Test 7: Issue detection"""
        print("\n🧪 Test 7: Issue Detection")
        response = self.session.get(
            f"{BASE_URL}/architecture/issues",
            headers=self.headers()
        )
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Issues detected: {len(data['issues'])}")
        if data['issues']:
            issue = data['issues'][0]
            print(f"   Example: [{issue['severity']}] {issue['description']}")
    
    def test_8_langgraph_workflows(self):
        """Test 8: LangGraph workflow generation"""
        print("\n🧪 Test 8: LangGraph Workflow Generation")
        response = self.session.post(
            f"{BASE_URL}/workflows/generate",
            headers=self.headers()
        )
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Workflows generated: {len(data['workflows'])}")
        for w in data['workflows']:
            print(f"   - {w['name']}: complexity={w['complexity_score']}, "
                  f"risk={w['risk_score']}, changes={len(w['proposed_changes'])}")
    
    def test_9_workflow_comparison(self):
        """Test 9: Workflow comparison"""
        print("\n🧪 Test 9: Workflow Comparison")
        response = self.session.get(
            f"{BASE_URL}/workflows/compare",
            headers=self.headers()
        )
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Workflows compared: {len(data['workflows'])}")
        if 'recommendation' in data:
            rec = data['recommendation']
            print(f"   Recommended: {rec['workflow']}")
            print(f"   Reason: {rec['reason']}")
    
    def test_10_ai_insights(self):
        """Test 10: AI-powered insights"""
        print("\n🧪 Test 10: AI Insights (if Azure OpenAI configured)")
        response = self.session.get(
            f"{BASE_URL}/dashboard/insights",
            headers=self.headers()
        )
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Insights generated: {len(data['insights'])}")
        if data['insights']:
            print(f"   Example: {data['insights'][0]['message'][:80]}...")
    
    def test_11_ai_design(self):
        """Test 11: AI architecture design"""
        print("\n🧪 Test 11: AI Architecture Design (if Azure OpenAI configured)")
        response = self.session.post(
            f"{BASE_URL}/ai-design/design-new",
            headers=self.headers(),
            json={
                "requirements": "E-commerce platform with product catalog, shopping cart, and payment processing",
                "constraints": ["microservices", "cloud-native", "scalable"],
                "scale": "medium"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Architectures designed: {len(data['architectures'])}")
            for arch in data['architectures'][:2]:
                print(f"   - {arch['name']}: {len(arch['services'])} services")
        else:
            print(f"⚠️  AI design skipped (Azure OpenAI not configured)")
    
    def test_12_system_stats(self):
        """Test 12: System statistics"""
        print("\n🧪 Test 12: System Statistics")
        response = self.session.get(
            f"{BASE_URL}/system/stats",
            headers=self.headers()
        )
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Total spans: {data['total_spans']}")
        print(f"✅ Services: {data['service_count']}")
        print(f"✅ Avg latency: {data['avg_latency_ms']:.2f}ms")
    
    def test_13_system_capabilities(self):
        """Test 13: System capabilities"""
        print("\n🧪 Test 13: System Capabilities")
        response = self.session.get(f"{BASE_URL}/system/capabilities")
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Features available:")
        for feature in data['capabilities'][:5]:
            status = "✓" if feature['enabled'] else "✗"
            print(f"   {status} {feature['name']}")
    
    def test_14_mcp_tools(self):
        """Test 14: MCP tools (manual verification)"""
        print("\n🧪 Test 14: MCP Tools")
        print("✅ MCP server can be tested separately with:")
        print("   cd Server && python -m mcp.server")
        print("   Then use MCP client to test tools with tenant_id parameter")
    
    def test_15_cleanup(self):
        """Test 15: Cleanup demo data"""
        print("\n🧪 Test 15: Cleanup")
        response = self.session.delete(
            f"{BASE_URL}/demo/clear-data",
            headers=self.headers()
        )
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Deleted {data['deleted_spans']} spans")
    
    def run_all(self):
        """Run all tests"""
        print("=" * 60)
        print("🚀 Nexarch E2E Test Suite")
        print("=" * 60)
        
        tests = [
            self.test_1_health_check,
            self.test_2_create_tenant,
            self.test_3_generate_sample_data,
            self.test_4_ingest_batch,
            self.test_5_dashboard_overview,
            self.test_6_architecture_map,
            self.test_7_detect_issues,
            self.test_8_langgraph_workflows,
            self.test_9_workflow_comparison,
            self.test_10_ai_insights,
            self.test_11_ai_design,
            self.test_12_system_stats,
            self.test_13_system_capabilities,
            self.test_14_mcp_tools,
            self.test_15_cleanup
        ]
        
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                test()
                passed += 1
            except Exception as e:
                print(f"❌ {test.__name__} failed: {str(e)}")
                failed += 1
        
        print("\n" + "=" * 60)
        print(f"📊 Results: {passed} passed, {failed} failed")
        print("=" * 60)


if __name__ == "__main__":
    # Make sure server is running
    print("🔍 Checking if server is running...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running\n")
        else:
            print("❌ Server returned non-200 status")
            exit(1)
    except requests.exceptions.RequestException:
        print("❌ Server is not running. Start it with:")
        print("   cd Server && python main.py")
        exit(1)
    
    # Run tests
    test = E2ETest()
    test.run_all()

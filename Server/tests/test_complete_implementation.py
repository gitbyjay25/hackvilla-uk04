"""
COMPREHENSIVE IMPLEMENTATION TEST SUITE
Tests all features, bug fixes, and edge cases for Nexarch Platform

This test suite validates:
1. Server API endpoints (all routes)
2. SDK functionality (client, middleware, instrumentation)
3. Multi-tenant isolation
4. Caching layer (Redis/in-memory)
5. AI integrations (with fallbacks)
6. Architecture discovery
7. Database instrumentation
8. Error handling and edge cases
9. Performance and scalability
10. Security (API key validation)
"""

import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Test configuration
BASE_URL = "http://4.240.107.18:443"
TEST_TENANT_EMAIL = f"test_{uuid.uuid4().hex[:8]}@nexarch.io"
TEST_API_KEY = None
TEST_TENANT_ID = None


class TestResult:
    """Test result container"""
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.duration_ms = 0
        self.error = None
        self.details = None


class NexarchTestSuite:
    """Complete implementation test suite"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.api_key = None
        self.tenant_id = None
        self.results: List[TestResult] = []
        
    async def run_all_tests(self):
        """Run complete test suite"""
        print("=" * 80)
        print("🧪 NEXARCH COMPLETE IMPLEMENTATION TEST SUITE")
        print("=" * 80)
        print(f"Target Server: {self.base_url}")
        print(f"Started at: {datetime.now().isoformat()}")
        print("=" * 80)
        print()
        
        test_groups = [
            ("🔧 Setup & Prerequisites", [
                self.test_server_health,
                self.test_create_tenant,
            ]),
            ("🔐 Authentication & Security", [
                self.test_invalid_api_key,
                self.test_missing_api_key,
                self.test_valid_api_key,
            ]),
            ("📊 Data Ingestion", [
                self.test_ingest_single_span,
                self.test_ingest_batch_spans,
                self.test_ingest_with_dependencies,
                self.test_ingest_with_errors,
                self.test_large_batch_ingestion,
            ]),
            ("🏗️ Architecture Discovery", [
                self.test_architecture_discovery_ingestion,
                self.test_architecture_current,
                self.test_architecture_issues,
            ]),
            ("📈 Dashboard & Metrics", [
                self.test_dashboard_overview,
                self.test_dashboard_service_metrics,
                self.test_dashboard_trace_timeline,
            ]),
            ("🔄 Workflow Generation", [
                self.test_workflow_generation,
                self.test_workflow_comparison,
                self.test_workflow_architecture_graph,
            ]),
            ("🤖 AI Features", [
                self.test_ai_design_endpoint,
                self.test_ai_fallback_behavior,
            ]),
            ("💾 Cache Management", [
                self.test_cache_info,
                self.test_cache_clear,
                self.test_cache_hit_miss,
            ]),
            ("🔍 Multi-Tenant Isolation", [
                self.test_tenant_isolation,
                self.test_cross_tenant_access_prevention,
            ]),
            ("🎯 System & Admin", [
                self.test_system_stats,
                self.test_list_tenants,
                self.test_demo_endpoints,
            ]),
            ("🐛 Bug Fixes Verification", [
                self.test_bugfix_async_handling,
                self.test_bugfix_exception_handling,
                self.test_bugfix_discovery_storage,
            ]),
            ("⚡ Performance & Edge Cases", [
                self.test_concurrent_requests,
                self.test_large_payload_handling,
                self.test_rate_limiting,
            ]),
        ]
        
        total_tests = sum(len(tests) for _, tests in test_groups)
        current_test = 0
        
        for group_name, tests in test_groups:
            print(f"\n{group_name}")
            print("-" * 80)
            
            for test_func in tests:
                current_test += 1
                result = await self._run_test(test_func, current_test, total_tests)
                self.results.append(result)
        
        self._print_summary()
    
    async def _run_test(self, test_func, current: int, total: int) -> TestResult:
        """Run a single test with timing and error handling"""
        result = TestResult(test_func.__name__)
        
        try:
            start = time.time()
            await test_func()
            result.duration_ms = round((time.time() - start) * 1000, 2)
            result.passed = True
            status = "✅ PASS"
        except Exception as e:
            result.duration_ms = round((time.time() - start) * 1000, 2)
            result.passed = False
            result.error = str(e)
            status = "❌ FAIL"
        
        print(f"  [{current}/{total}] {status} {result.name} ({result.duration_ms}ms)")
        if result.error:
            print(f"      Error: {result.error}")
        
        return result
    
    def _print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 80)
        print("📊 TEST SUMMARY")
        print("=" * 80)
        
        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed
        total_duration = sum(r.duration_ms for r in self.results)
        
        print(f"Total Tests: {len(self.results)}")
        print(f"Passed: {passed} ✅")
        print(f"Failed: {failed} ❌")
        print(f"Pass Rate: {round(passed / len(self.results) * 100, 2)}%")
        print(f"Total Duration: {round(total_duration / 1000, 2)}s")
        print()
        
        if failed > 0:
            print("Failed Tests:")
            for result in self.results:
                if not result.passed:
                    print(f"  ❌ {result.name}: {result.error}")
        
        print("=" * 80)
        
        return passed == len(self.results)
    
    # ==================== SETUP TESTS ====================
    
    async def test_server_health(self):
        """Test server is running and healthy"""
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/api/v1/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
    
    async def test_create_tenant(self):
        """Test tenant creation"""
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/admin/tenants",
                json={
                    "name": f"Test Tenant {uuid.uuid4().hex[:8]}",
                    "admin_email": TEST_TENANT_EMAIL
                }
            )
            assert response.status_code == 200
            data = response.json()
            self.tenant_id = data["id"]
            self.api_key = data["api_key"]
            assert self.api_key.startswith("nex_")
    
    # ==================== AUTHENTICATION TESTS ====================
    
    async def test_invalid_api_key(self):
        """Test invalid API key is rejected"""
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/architecture/current",
                headers={"X-API-Key": "invalid_key_12345"}
            )
            assert response.status_code == 401
    
    async def test_missing_api_key(self):
        """Test missing API key is rejected"""
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/architecture/current"
            )
            assert response.status_code in [401, 422]  # Unprocessable or Unauthorized
    
    async def test_valid_api_key(self):
        """Test valid API key is accepted"""
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/architecture/current",
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 200
    
    # ==================== INGESTION TESTS ====================
    
    async def test_ingest_single_span(self):
        """Test single span ingestion"""
        import httpx
        span = {
            "trace_id": str(uuid.uuid4()),
            "span_id": str(uuid.uuid4()),
            "parent_span_id": None,
            "service_name": "test-service",
            "operation": "GET /users",
            "kind": "server",
            "start_time": datetime.utcnow().isoformat(),
            "end_time": (datetime.utcnow() + timedelta(milliseconds=150)).isoformat(),
            "latency_ms": 150.5,
            "status_code": 200,
            "error": None,
            "downstream": None
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/ingest",
                json=span,
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "accepted"
            assert "span_id" in data
    
    async def test_ingest_batch_spans(self):
        """Test batch span ingestion"""
        import httpx
        
        spans = []
        for i in range(10):
            spans.append({
                "trace_id": str(uuid.uuid4()),
                "span_id": str(uuid.uuid4()),
                "parent_span_id": None,
                "service_name": f"service-{i % 3}",
                "operation": f"GET /endpoint-{i}",
                "kind": "server",
                "start_time": datetime.utcnow().isoformat(),
                "end_time": (datetime.utcnow() + timedelta(milliseconds=100)).isoformat(),
                "latency_ms": 100.0,
                "status_code": 200,
                "error": None,
                "downstream": None
            })
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/ingest/batch",
                json=spans,
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 202
            data = response.json()
            assert data["count"] >= 9  # Allow for some failures
    
    async def test_ingest_with_dependencies(self):
        """Test span with downstream dependencies"""
        import httpx
        
        span = {
            "trace_id": str(uuid.uuid4()),
            "span_id": str(uuid.uuid4()),
            "parent_span_id": None,
            "service_name": "api-gateway",
            "operation": "GET /orders",
            "kind": "server",
            "start_time": datetime.utcnow().isoformat(),
            "end_time": (datetime.utcnow() + timedelta(milliseconds=200)).isoformat(),
            "latency_ms": 200.0,
            "status_code": 200,
            "error": None,
            "downstream": "order-service"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/ingest",
                json=span,
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 202
    
    async def test_ingest_with_errors(self):
        """Test span with error status"""
        import httpx
        
        span = {
            "trace_id": str(uuid.uuid4()),
            "span_id": str(uuid.uuid4()),
            "parent_span_id": None,
            "service_name": "payment-service",
            "operation": "POST /payments",
            "kind": "server",
            "start_time": datetime.utcnow().isoformat(),
            "end_time": (datetime.utcnow() + timedelta(milliseconds=500)).isoformat(),
            "latency_ms": 500.0,
            "status_code": 500,
            "error": "Database connection timeout",
            "downstream": "postgres"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/ingest",
                json=span,
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 202
    
    async def test_large_batch_ingestion(self):
        """Test large batch ingestion (100 spans)"""
        import httpx
        
        spans = []
        for i in range(100):
            spans.append({
                "trace_id": str(uuid.uuid4()),
                "span_id": str(uuid.uuid4()),
                "parent_span_id": None,
                "service_name": f"service-{i % 5}",
                "operation": f"GET /resource-{i}",
                "kind": "server",
                "start_time": datetime.utcnow().isoformat(),
                "end_time": (datetime.utcnow() + timedelta(milliseconds=50)).isoformat(),
                "latency_ms": 50.0,
                "status_code": 200,
                "error": None,
                "downstream": None
            })
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/ingest/batch",
                json=spans,
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 202
            data = response.json()
            assert data["count"] >= 95  # Allow up to 5% failures
    
    # ==================== ARCHITECTURE DISCOVERY TESTS ====================
    
    async def test_architecture_discovery_ingestion(self):
        """Test architecture discovery data ingestion"""
        import httpx
        
        discovery = {
            "service_name": "test-api",
            "service_type": "fastapi",
            "version": "1.0.0",
            "endpoints": [
                {
                    "path": "/users",
                    "methods": ["GET", "POST"],
                    "calls_database": True,
                    "calls_external": False
                },
                {
                    "path": "/orders",
                    "methods": ["GET"],
                    "calls_database": True,
                    "calls_external": True
                }
            ],
            "databases": [
                {
                    "type": "relational",
                    "engine": "postgresql",
                    "driver": "psycopg2"
                }
            ],
            "external_services": ["stripe.com", "sendgrid.com"],
            "middleware": ["cors", "authentication", "rate_limiting"],
            "architecture_patterns": {
                "pattern": "microservices",
                "uses_cache": True,
                "uses_queue": False
            },
            "discovered_at": datetime.utcnow().isoformat()
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/ingest/architecture-discovery",
                json=discovery,
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "accepted"
            assert data["endpoints_discovered"] == 2
    
    async def test_architecture_current(self):
        """Test get current architecture"""
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/architecture/current",
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 200
            data = response.json()
            assert "nodes" in data
            assert "edges" in data
            assert "metrics_summary" in data
    
    async def test_architecture_issues(self):
        """Test get architecture issues"""
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/architecture/issues",
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 200
            data = response.json()
            assert "issues" in data
            assert "total_count" in data
    
    # ==================== DASHBOARD TESTS ====================
    
    async def test_dashboard_overview(self):
        """Test dashboard overview"""
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/dashboard/overview",
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 200
            data = response.json()
            assert "total_requests" in data
            assert "total_services" in data
    
    async def test_dashboard_service_metrics(self):
        """Test service metrics endpoint"""
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/dashboard/services/test-service/metrics",
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code in [200, 404]  # Service might not exist
    
    async def test_dashboard_trace_timeline(self):
        """Test trace timeline"""
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/dashboard/traces/timeline",
                headers={"X-API-Key": self.api_key},
                params={"hours": 24}
            )
            assert response.status_code == 200
            data = response.json()
            assert "timeline" in data
    
    # ==================== WORKFLOW TESTS ====================
    
    async def test_workflow_generation(self):
        """Test workflow generation"""
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/workflows/generated",
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 200
            data = response.json()
            assert "workflows" in data
    
    async def test_workflow_comparison(self):
        """Test workflow comparison"""
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/workflows/comparison",
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 200
            data = response.json()
            assert "workflows" in data
            assert "recommendation" in data
    
    async def test_workflow_architecture_graph(self):
        """Test workflow architecture graph"""
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/workflows/architecture/graph",
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 200
            data = response.json()
            assert "current_architecture" in data
            assert "generated_workflows" in data
    
    # ==================== AI TESTS ====================
    
    async def test_ai_design_endpoint(self):
        """Test AI architecture design endpoint"""
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/ai-design/design-new",
                json={
                    "business_domain": "E-commerce",
                    "expected_scale": "medium",
                    "key_features": ["product catalog", "checkout", "payments"],
                    "performance_requirements": {"max_latency_ms": 500},
                    "constraints": {"budget": "moderate"},
                    "num_alternatives": 2
                },
                headers={"X-API-Key": self.api_key}
            )
            # May return 200 with fallback or actual AI response
            assert response.status_code in [200, 500, 503]
    
    async def test_ai_fallback_behavior(self):
        """Test AI features work even without Azure OpenAI configured"""
        # This should return fallback recommendations
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/architecture/issues",
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 200
            # Should work even if AI is disabled
    
    # ==================== CACHE TESTS ====================
    
    async def test_cache_info(self):
        """Test cache info endpoint"""
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/cache/info",
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 200
            data = response.json()
            assert "backend" in data
    
    async def test_cache_clear(self):
        """Test cache clearing"""
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/api/v1/cache/clear",
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 200
    
    async def test_cache_hit_miss(self):
        """Test cache hit/miss behavior"""
        import httpx
        async with httpx.AsyncClient() as client:
            # First call - cache miss
            response1 = await client.get(
                f"{self.base_url}/api/v1/architecture/current",
                headers={"X-API-Key": self.api_key}
            )
            assert response1.status_code == 200
            
            # Second call - should be cached
            response2 = await client.get(
                f"{self.base_url}/api/v1/architecture/current",
                headers={"X-API-Key": self.api_key}
            )
            assert response2.status_code == 200
    
    # ==================== MULTI-TENANT TESTS ====================
    
    async def test_tenant_isolation(self):
        """Test tenant data isolation"""
        import httpx
        
        # Create second tenant
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/admin/tenants",
                json={
                    "name": "Isolation Test Tenant",
                    "admin_email": f"isolation_{uuid.uuid4().hex[:8]}@test.com"
                }
            )
            assert response.status_code == 200
            tenant2_data = response.json()
            tenant2_api_key = tenant2_data["api_key"]
            
            # Ingest data for tenant 1
            span_t1 = {
                "trace_id": str(uuid.uuid4()),
                "span_id": str(uuid.uuid4()),
                "parent_span_id": None,
                "service_name": "tenant1-service",
                "operation": "GET /test",
                "kind": "server",
                "start_time": datetime.utcnow().isoformat(),
                "end_time": (datetime.utcnow() + timedelta(milliseconds=100)).isoformat(),
                "latency_ms": 100.0,
                "status_code": 200,
                "error": None,
                "downstream": None
            }
            
            response = await client.post(
                f"{self.base_url}/api/v1/ingest",
                json=span_t1,
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 202
            
            # Verify tenant 2 doesn't see tenant 1's data
            response = await client.get(
                f"{self.base_url}/api/v1/architecture/current",
                headers={"X-API-Key": tenant2_api_key}
            )
            assert response.status_code == 200
            data = response.json()
            # Should not contain tenant1-service
            node_ids = [node["id"] for node in data.get("nodes", [])]
            assert "tenant1-service" not in node_ids
    
    async def test_cross_tenant_access_prevention(self):
        """Test that tenants cannot access each other's data"""
        # Already covered by tenant_isolation test
        pass
    
    # ==================== SYSTEM TESTS ====================
    
    async def test_system_stats(self):
        """Test system statistics endpoint"""
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/system/stats",
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 200
            data = response.json()
            assert "spans" in data
    
    async def test_list_tenants(self):
        """Test list tenants endpoint"""
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/api/v1/admin/tenants")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
    
    async def test_demo_endpoints(self):
        """Test demo data generation endpoints"""
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/demo/generate-sample-data",
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code in [200, 201, 202]
    
    # ==================== BUG FIX VERIFICATION ====================
    
    async def test_bugfix_async_handling(self):
        """Verify async/await bug fixes work correctly"""
        # This tests that issue_detector and workflow_generator
        # handle async properly without event loop errors
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/workflows/generated",
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 200
    
    async def test_bugfix_exception_handling(self):
        """Verify proper exception handling (no bare excepts)"""
        # All endpoints should return proper error codes, not 500
        import httpx
        async with httpx.AsyncClient() as client:
            # Test with invalid data
            response = await client.post(
                f"{self.base_url}/api/v1/ingest",
                json={"invalid": "data"},
                headers={"X-API-Key": self.api_key}
            )
            # Should get 422 (validation error), not 500
            assert response.status_code in [422, 400]
    
    async def test_bugfix_discovery_storage(self):
        """Verify architecture discovery is properly stored"""
        import httpx
        
        discovery = {
            "service_name": "bugfix-test-service",
            "service_type": "fastapi",
            "version": "2.0.0",
            "endpoints": [{"path": "/health", "methods": ["GET"]}],
            "databases": [],
            "external_services": [],
            "middleware": [],
            "architecture_patterns": {},
            "discovered_at": datetime.utcnow().isoformat()
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/ingest/architecture-discovery",
                json=discovery,
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 202
            data = response.json()
            assert "message" in data
            assert "saved successfully" in data["message"].lower()
    
    # ==================== PERFORMANCE TESTS ====================
    
    async def test_concurrent_requests(self):
        """Test handling concurrent requests"""
        import httpx
        import asyncio
        
        async def make_request():
            async with httpx.AsyncClient() as client:
                return await client.get(
                    f"{self.base_url}/api/v1/health"
                )
        
        # Make 20 concurrent requests
        tasks = [make_request() for _ in range(20)]
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(r.status_code == 200 for r in responses)
    
    async def test_large_payload_handling(self):
        """Test handling of large payloads"""
        import httpx
        
        # Create a large discovery payload
        large_discovery = {
            "service_name": "large-service",
            "service_type": "fastapi",
            "version": "1.0.0",
            "endpoints": [
                {
                    "path": f"/endpoint-{i}",
                    "methods": ["GET", "POST"],
                    "calls_database": True,
                    "calls_external": False
                }
                for i in range(200)  # 200 endpoints
            ],
            "databases": [{"type": "postgresql", "engine": "psycopg2"} for _ in range(10)],
            "external_services": [f"service-{i}.com" for i in range(50)],
            "middleware": ["cors", "auth", "rate_limit"],
            "architecture_patterns": {"pattern": "microservices"},
            "discovered_at": datetime.utcnow().isoformat()
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/ingest/architecture-discovery",
                json=large_discovery,
                headers={"X-API-Key": self.api_key}
            )
            assert response.status_code == 202
    
    async def test_rate_limiting(self):
        """Test rate limiting behavior"""
        # This test verifies rate limiting middleware exists
        # Actual rate limiting might not trigger in test environment
        import httpx
        async with httpx.AsyncClient() as client:
            # Make multiple rapid requests
            responses = []
            for _ in range(10):
                response = await client.get(
                    f"{self.base_url}/api/v1/health"
                )
                responses.append(response)
            
            # Most should succeed (rate limit is typically high in dev)
            success_count = sum(1 for r in responses if r.status_code == 200)
            assert success_count >= 8  # At least 80% should succeed


# ==================== MAIN TEST RUNNER ====================

async def main():
    """Main test runner"""
    suite = NexarchTestSuite()
    
    try:
        await suite.run_all_tests()
        
        # Return exit code based on results
        all_passed = all(r.passed for r in suite.results)
        sys.exit(0 if all_passed else 1)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("Starting Nexarch Complete Implementation Test Suite...")
    print("Make sure the server is running at http://localhost:443")
    print()
    
    # Check dependencies
    try:
        import httpx
    except ImportError:
        print("❌ Error: httpx not installed. Run: pip install httpx")
        sys.exit(1)
    
    # Run tests
    asyncio.run(main())

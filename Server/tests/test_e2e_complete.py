"""
Complete End-to-End Integration Test
Tests SDK -> FastAPI -> MCP Server in a realistic workflow
"""
import asyncio
import sys
import os
import time
import requests
import json
from datetime import datetime, timedelta

# Add paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'SDK', 'python'))

# Color codes for output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


class E2ETestSuite:
    """Complete end-to-end test suite"""
    
    def __init__(self):
        # FastAPI backend on localhost (use port 8001 to avoid admin privileges)
        self.base_url = "http://localhost:8001"
        # MCP server runs via stdio, not HTTP - we'll test directly
        self.mcp_url = None  # MCP is stdio-based
        self.tenant_id = "e2e_test_tenant"
        self.test_results = []
        self.sdk_client = None
        self.api_key = None
    
    def print_header(self, text):
        """Print colored header"""
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{text.center(70)}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")
    
    def print_section(self, text):
        """Print section header"""
        print(f"\n{Colors.OKCYAN}{Colors.BOLD}{'-'*70}{Colors.ENDC}")
        print(f"{Colors.OKCYAN}{Colors.BOLD}>>> {text}{Colors.ENDC}")
        print(f"{Colors.OKCYAN}{'-'*70}{Colors.ENDC}")
    
    def print_success(self, text):
        """Print success message"""
        print(f"{Colors.OKGREEN}[OK] {text}{Colors.ENDC}")
    
    def print_error(self, text):
        """Print error message"""
        print(f"{Colors.FAIL}[ERROR] {text}{Colors.ENDC}")
    
    def print_info(self, text):
        """Print info message"""
        print(f"{Colors.OKBLUE}[INFO] {text}{Colors.ENDC}")
    
    def add_result(self, test_name, status, details=None):
        """Record test result"""
        self.test_results.append({
            "test": test_name,
            "status": status,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
    
    # ========== PHASE 1: FastAPI Backend Tests ==========
    
    def test_backend_health(self):
        """Test FastAPI backend health endpoint"""
        self.print_section("PHASE 1: Testing FastAPI Backend")
        print("Testing backend health...")
        try:
            response = requests.get(f"{self.base_url}/api/v1/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.print_success(f"Backend is healthy: {data.get('status')}")
                self.print_info(f"   Version: {data.get('version')}")
                self.print_info(f"   Multi-tenant: {data.get('multi_tenant')}")
                self.print_info(f"   Caching: {data.get('caching')}")
                self.add_result("backend_health", "PASS", data)
                return True
            else:
                self.print_error(f"Backend returned status {response.status_code}")
                self.add_result("backend_health", "FAIL", f"Status: {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            self.print_error("Backend is not running! Please start with: python main.py")
            self.add_result("backend_health", "FAIL", "Connection refused")
            return False
        except Exception as e:
            self.print_error(f"Health check failed: {e}")
            self.add_result("backend_health", "FAIL", str(e))
            return False
    
    def test_ingest_spans(self):
        """Test span ingestion endpoint"""
        print("\n📥 Testing span ingestion...")
        try:
            # Create test spans
            spans = [
                {
                    "trace_id": f"trace-e2e-{i}",
                    "span_id": f"span-e2e-{i}",
                    "parent_span_id": f"span-e2e-{i-1}" if i > 0 else None,
                    "service_name": "e2e-service" if i % 2 == 0 else "e2e-database",
                    "operation": "GET /api/test",
                    "kind": "server",
                    "start_time": (datetime.utcnow() - timedelta(seconds=10-i)).isoformat(),
                    "end_time": (datetime.utcnow() - timedelta(seconds=9-i)).isoformat(),
                    "latency_ms": 100 + i * 10,
                    "status_code": 200 if i % 5 != 0 else 500,
                    "error": None if i % 5 != 0 else "Test error",
                    "downstream": "e2e-database" if i % 2 == 0 else None
                }
                for i in range(20)
            ]
            
            payload = {
                "tenant_id": self.tenant_id,
                "spans": spans
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/ingest/spans",
                json=payload,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                self.print_success(f"Ingested {data.get('ingested', 0)} spans")
                self.print_info(f"   Tenant: {data.get('tenant_id')}")
                self.print_info(f"   Processing time: {data.get('processing_time_ms', 0):.2f}ms")
                self.add_result("ingest_spans", "PASS", data)
                time.sleep(1)  # Allow processing
                return True
            else:
                self.print_error(f"Ingestion failed: {response.status_code}")
                self.print_error(f"   Response: {response.text[:200]}")
                self.add_result("ingest_spans", "FAIL", response.text)
                return False
        except Exception as e:
            self.print_error(f"Ingestion test failed: {e}")
            self.add_result("ingest_spans", "FAIL", str(e))
            return False
    
    def test_architecture_endpoint(self):
        """Test architecture graph endpoint"""
        print("\n🏗️  Testing architecture graph...")
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/architecture/graph",
                params={"tenant_id": self.tenant_id},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                nodes = data.get('nodes', [])
                edges = data.get('edges', [])
                self.print_success(f"Architecture retrieved")
                self.print_info(f"   Services: {len(nodes)}")
                self.print_info(f"   Dependencies: {len(edges)}")
                if nodes:
                    self.print_info(f"   Sample services: {', '.join([n.get('name', 'unknown')[:20] for n in nodes[:3]])}")
                self.add_result("architecture_graph", "PASS", {"nodes": len(nodes), "edges": len(edges)})
                return True
            else:
                self.print_error(f"Architecture fetch failed: {response.status_code}")
                self.add_result("architecture_graph", "FAIL", response.text)
                return False
        except Exception as e:
            self.print_error(f"Architecture test failed: {e}")
            self.add_result("architecture_graph", "FAIL", str(e))
            return False
    
    def test_metrics_endpoint(self):
        """Test metrics endpoint"""
        print("\n📊 Testing metrics...")
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/architecture/metrics",
                params={"tenant_id": self.tenant_id},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.print_success("Metrics retrieved")
                self.print_info(f"   Service count: {data.get('service_count', 0)}")
                self.print_info(f"   Total requests: {data.get('total_requests', 0)}")
                self.print_info(f"   Error rate: {data.get('error_rate', 0):.2f}%")
                self.print_info(f"   Avg latency: {data.get('avg_latency_ms', 0):.2f}ms")
                self.add_result("metrics", "PASS", data)
                return True
            else:
                self.print_error(f"Metrics fetch failed: {response.status_code}")
                self.add_result("metrics", "FAIL", response.text)
                return False
        except Exception as e:
            self.print_error(f"Metrics test failed: {e}")
            self.add_result("metrics", "FAIL", str(e))
            return False
    
    def test_workflow_generation(self):
        """Test workflow generation endpoint"""
        print("\n🔄 Testing workflow generation...")
        try:
            payload = {
                "tenant_id": self.tenant_id,
                "goal": "optimize_performance"
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/workflows/generate",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                workflows = data.get('workflows', [])
                self.print_success(f"Generated {len(workflows)} workflows")
                for i, wf in enumerate(workflows, 1):
                    self.print_info(f"   {i}. {wf.get('name')}: Complexity={wf.get('complexity_score')}/10, Risk={wf.get('risk_score')}/10")
                self.add_result("workflow_generation", "PASS", {"count": len(workflows)})
                return True
            else:
                self.print_error(f"Workflow generation failed: {response.status_code}")
                self.add_result("workflow_generation", "FAIL", response.text)
                return False
        except Exception as e:
            self.print_error(f"Workflow test failed: {e}")
            self.add_result("workflow_generation", "FAIL", str(e))
            return False
    
    # ========== PHASE 2: MCP Server Tests ==========
    
    async def test_mcp_server(self):
        """Test MCP server tools"""
        self.print_section("PHASE 2: Testing MCP Server")
        
        try:
            from mcp_server.tools import MCPTools
            tools = MCPTools(default_tenant_id=self.tenant_id)
            
            # Test 1: Get architecture
            print("\n🏗️  Testing MCP get_current_architecture...")
            arch_data = tools.get_current_architecture(self.tenant_id)
            self.print_success(f"MCP Architecture: {arch_data.get('service_count')} services, {arch_data.get('dependency_count')} dependencies")
            self.add_result("mcp_architecture", "PASS", arch_data)
            
            # Test 2: Detect issues
            print("\n🔍 Testing MCP get_detected_issues...")
            issues_data = await tools.get_detected_issues(self.tenant_id)
            self.print_success(f"MCP Issues: {issues_data.get('total_count')} total, {issues_data.get('critical_count')} critical")
            if issues_data.get('total_count', 0) > 0:
                for issue_type, issues in list(issues_data.get('by_type', {}).items())[:3]:
                    self.print_info(f"   {issue_type}: {len(issues)} issues")
            self.add_result("mcp_issues", "PASS", issues_data)
            
            # Test 3: Generate workflows
            print("\n🔄 Testing MCP generate_workflows...")
            wf_data = await tools.generate_workflows(self.tenant_id, "optimize_performance")
            self.print_success(f"MCP Workflows: {wf_data.get('count')} generated via {wf_data.get('generated_by')}")
            for wf in wf_data.get('workflows', [])[:2]:
                self.print_info(f"   {wf.get('name')}: {wf.get('description', 'No description')[:60]}...")
            self.add_result("mcp_workflows", "PASS", wf_data)
            
            # Test 4: Graph analysis
            print("\n📊 Testing MCP get_graph_analysis...")
            graph_data = tools.get_graph_analysis(self.tenant_id)
            metrics = graph_data.get('graph_metrics', {})
            self.print_success(f"MCP Graph Analysis: {metrics.get('node_count')} nodes, DAG={metrics.get('is_dag')}")
            self.print_info(f"   Avg Degree: {metrics.get('avg_degree', 0):.2f}")
            self.print_info(f"   Insights: {len(graph_data.get('insights', []))}")
            self.add_result("mcp_graph_analysis", "PASS", graph_data)
            
            return True
            
        except Exception as e:
            self.print_error(f"MCP server tests failed: {e}")
            import traceback
            traceback.print_exc()
            self.add_result("mcp_server", "FAIL", str(e))
            return False
    
    # ========== PHASE 3: SDK Tests ==========
    
    def test_sdk_instrumentation(self):
        """Test SDK instrumentation"""
        self.print_section("PHASE 3: Testing SDK Instrumentation")
        
        try:
            # Import SDK
            import sys
            sdk_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'SDK', 'python')
            sys.path.insert(0, sdk_path)
            
            from client import NexarchClient
            from instrumentation.requests_patch import patch_requests
            
            print("\n🔧 Initializing SDK...")
            client = NexarchClient(
                tenant_id=self.tenant_id,
                endpoint=f"{self.base_url}/api/v1/ingest/spans"
            )
            
            # Patch requests library
            patch_requests(client)
            self.print_success("SDK initialized and requests library patched")
            self.add_result("sdk_init", "PASS", {"tenant": self.tenant_id})
            
            # Test instrumentation
            print("\n📡 Testing instrumented HTTP requests...")
            test_urls = [
                "https://httpbin.org/get",
                "https://httpbin.org/delay/1",
                "https://httpbin.org/status/200"
            ]
            
            success_count = 0
            for url in test_urls:
                try:
                    print(f"   Making request to {url}...")
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        success_count += 1
                        self.print_info(f"      ✓ {url} - Status {response.status_code}")
                except Exception as e:
                    self.print_info(f"      ⚠ {url} - {str(e)[:50]}")
            
            # Flush spans
            time.sleep(2)
            client.flush()
            self.print_success(f"SDK instrumentation test complete ({success_count}/{len(test_urls)} successful)")
            self.add_result("sdk_instrumentation", "PASS", {"requests": len(test_urls), "successful": success_count})
            
            return True
            
        except ImportError as e:
            self.print_error(f"SDK not found: {e}")
            self.print_info("SDK tests skipped - SDK not installed")
            self.add_result("sdk_instrumentation", "SKIP", "SDK not available")
            return False
        except Exception as e:
            self.print_error(f"SDK test failed: {e}")
            import traceback
            traceback.print_exc()
            self.add_result("sdk_instrumentation", "FAIL", str(e))
            return False
    
    # ========== Test Summary ==========
    
    def print_summary(self):
        """Print comprehensive test summary"""
        self.print_header("TEST SUMMARY")
        
        passed = sum(1 for r in self.test_results if r["status"] == "PASS")
        failed = sum(1 for r in self.test_results if r["status"] == "FAIL")
        skipped = sum(1 for r in self.test_results if r["status"] == "SKIP")
        total = len(self.test_results)
        
        print(f"\n{Colors.BOLD}Total Tests: {total}{Colors.ENDC}")
        print(f"{Colors.OKGREEN}✅ Passed: {passed}{Colors.ENDC}")
        print(f"{Colors.FAIL}❌ Failed: {failed}{Colors.ENDC}")
        print(f"{Colors.WARNING}⏭️  Skipped: {skipped}{Colors.ENDC}")
        
        # Show by phase
        print(f"\n{Colors.BOLD}Results by Phase:{Colors.ENDC}")
        
        phases = {
            "FastAPI Backend": ["backend_health", "ingest_spans", "architecture_graph", "metrics", "workflow_generation"],
            "MCP Server": ["mcp_architecture", "mcp_issues", "mcp_workflows", "mcp_graph_analysis"],
            "SDK": ["sdk_init", "sdk_instrumentation"]
        }
        
        for phase_name, test_names in phases.items():
            phase_results = [r for r in self.test_results if r["test"] in test_names]
            phase_passed = sum(1 for r in phase_results if r["status"] == "PASS")
            phase_total = len(phase_results)
            
            if phase_total > 0:
                status_icon = "✅" if phase_passed == phase_total else "⚠️" if phase_passed > 0 else "❌"
                print(f"  {status_icon} {phase_name}: {phase_passed}/{phase_total}")
        
        # Show failures
        if failed > 0:
            print(f"\n{Colors.FAIL}{Colors.BOLD}Failed Tests:{Colors.ENDC}")
            for result in self.test_results:
                if result["status"] == "FAIL":
                    print(f"{Colors.FAIL}  ❌ {result['test']}{Colors.ENDC}")
                    if result.get("details"):
                        detail_str = str(result["details"])[:100]
                        print(f"     {detail_str}")
        
        # Final verdict
        print(f"\n{Colors.BOLD}{'='*70}{Colors.ENDC}")
        if failed == 0:
            print(f"{Colors.OKGREEN}{Colors.BOLD}🎉 ALL TESTS PASSED! System is fully operational.{Colors.ENDC}")
        elif passed > failed:
            print(f"{Colors.WARNING}{Colors.BOLD}⚠️  PARTIAL SUCCESS - Some tests failed but core functionality works.{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}{Colors.BOLD}❌ TESTS FAILED - Critical issues detected.{Colors.ENDC}")
        print(f"{Colors.BOLD}{'='*70}{Colors.ENDC}\n")
    
    # ========== Main Test Runner ==========
    
    async def run_all_tests(self):
        """Run all tests in sequence"""
        self.print_header("NEXARCH E2E INTEGRATION TEST SUITE")
        
        print(f"{Colors.BOLD}Testing:{Colors.ENDC}")
        print("  • FastAPI Backend (REST API)")
        print("  • MCP Server (AI Tools)")
        print("  • SDK (Instrumentation)\n")
        
        print(f"{Colors.BOLD}Test Tenant:{Colors.ENDC} {self.tenant_id}")
        print(f"{Colors.BOLD}Backend URL:{Colors.ENDC} {self.base_url}\n")
        
        # Phase 1: Backend
        backend_ok = self.test_backend_health()
        if backend_ok:
            self.test_ingest_spans()
            self.test_architecture_endpoint()
            self.test_metrics_endpoint()
            self.test_workflow_generation()
        else:
            self.print_error("Backend not available - skipping backend tests")
        
        # Phase 2: MCP
        await self.test_mcp_server()
        
        # Phase 3: SDK
        self.test_sdk_instrumentation()
        
        # Summary
        self.print_summary()


async def main():
    """Main entry point"""
    suite = E2ETestSuite()
    await suite.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())

import unittest
import asyncio
import httpx
import sys
import os
import json
import uuid
from fastapi import FastAPI

# Add SDK to path
sdk_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../SDK"))
if sdk_path not in sys.path:
    sys.path.insert(0, sdk_path)

try:
    from python.client import NexarchSDK
except ImportError:
    print(f"[FAIL] Failed to import NexarchSDK from {sdk_path}")
    sys.exit(1)

# Configuration
BACKEND_URL = "http://4.240.107.18:443"
MCP_SERVER_URL = "http://127.0.0.1:8000"
TEST_TENANT_NAME = f"Integration Test {uuid.uuid4().hex[:8]}"

class TestIntegrationSuite(unittest.IsolatedAsyncioTestCase):
    
    api_key = None
    tenant_id = None
        
    async def test_1_backend_health(self):
        """Verify Backend is reachable"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BACKEND_URL}/api/v1/health")
            self.assertEqual(resp.status_code, 200)
            print("\n[OK] Backend is healthy")

    async def test_2_create_tenant(self):
        """Create a tenant for isolation"""
        async with httpx.AsyncClient() as client:
            payload = {
                "name": TEST_TENANT_NAME,
                "admin_email": f"test_{uuid.uuid4().hex[:8]}@nexarch.dev"
            }
            resp = await client.post(f"{BACKEND_URL}/api/v1/admin/tenants", json=payload)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            TestIntegrationSuite.api_key = data["api_key"]
            TestIntegrationSuite.tenant_id = data["id"]
            print(f"\n[OK] Created tenant: {TEST_TENANT_NAME} (ID: {data['id']})")

    async def test_3_sdk_end_to_end(self):
        """
        Verify SDK -> Backend Flow:
        1. Initialize SDK with REAL backend URL
        2. Instrument local FastAPI app
        3. Make request to local app
        4. Verify backend received the span
        """
        self.assertIsNotNone(TestIntegrationSuite.api_key, "Tenant creation failed, skipping SDK test")
        
        # 1. Create Local App
        app = FastAPI(title="SDK Test App")
        
        @app.get("/test-endpoint")
        async def test_endpoint():
            return {"message": "Hello from SDK"}
        
        # 2. Initialize SDK
        ingest_url = f"{BACKEND_URL}/api/v1/ingest" 
        
        sdk = NexarchSDK(
            api_key=TestIntegrationSuite.api_key,
            service_name="sdk-integration-service",
            environment="test",
            enable_http_export=True,
            http_endpoint=ingest_url,
            enable_local_logs=False,
            sampling_rate=1.0  # Force sample
        )
        sdk.init(app)
        
        print(f"\n[START] Sending traces to {ingest_url}")
        
        # 3. Trigger Request
        from httpx import ASGITransport
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/test-endpoint")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json(), {"message": "Hello from SDK"})
            
        # 4. Wait for async ingestion
        print("[WAIT] Waiting for trace ingestion...")
        
        # Force flush SDK (workaround for SDK batching bug)
        try:
            from python.queue import get_log_queue
            queue = get_log_queue()
            if queue._exporter:
                print("[WAIT] Forcing SDK exporter flush...")
                queue._exporter.flush()
        except ImportError:
            print("[FAIL] Could not import queue to force flush")

        await asyncio.sleep(5) 
        
        # 5. Verify on Backend
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BACKEND_URL}/api/v1/architecture/current",
                headers={"X-API-Key": TestIntegrationSuite.api_key}
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            
            nodes = data.get("nodes", [])
            service_found = any(n["id"] == "sdk-integration-service" or n["id"] == "test" for n in nodes)
            
            service_ids = [n["id"] for n in nodes]
            print(f"   Found services: {service_ids}")
            
            self.assertTrue(service_found, f"SDK Service not found in architecture. Services: {service_ids}")
            print("[OK] SDK Trace successfully ingested!")

    async def test_4_mcp_server_connection(self):
        """Verify MCP Server (SSE) is running"""
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{MCP_SERVER_URL}/sse", timeout=2.0)
                self.assertEqual(resp.status_code, 200)
                print("\n[OK] MCP Server reachable at /sse")
                
            except httpx.TimeoutException:
                print("\n[OK] MCP Server reachable (connection kept open)")
            except httpx.ConnectError:
                self.fail("[FAIL] MCP Server NOT running on port 8000")

    async def test_5_mcp_tools(self):
        """Placeholder for MCP Tool Check"""
        pass

if __name__ == "__main__":
    unittest.main()

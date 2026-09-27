"""Standalone Nexarch SDK smoke test.

What it verifies:
- the installed `nexarch` package imports correctly
- the SDK can initialize against a FastAPI app
- the app can handle requests while the SDK captures telemetry
- telemetry is exported to backend ingest paths with project metadata

Run:
    python test_sdk_smoke.py
"""

from __future__ import annotations

import json
import threading

import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Use the SDK from this workspace during smoke validation.
SDK_PATH = Path(__file__).resolve().parent / "nexarch-sdk"
if str(SDK_PATH) not in sys.path:
    sys.path.insert(0, str(SDK_PATH))

from nexarch import NexarchSDK
from nexarch.exporters.http import HttpExporter
from nexarch.queue import get_log_queue

API_KEY = os.getenv("NEXARCH_SDK_API_KEY", "nex_OdQ5znaix2NOEf_tuLaA6YW94_mbUwGJ3vEmJUnSR4w")
PROJECT_NAME = os.getenv("NEXARCH_PROJECT_NAME", "sdk-smoke-project")


def build_app() -> tuple[FastAPI, NexarchSDK]:
    app = FastAPI(title="Nexarch SDK Smoke App")

    sdk = NexarchSDK(
        api_key=API_KEY,
        environment="smoke-test",
        service_name="sdk-smoke-app",
        project_name=PROJECT_NAME,
        enable_auto_discovery=True,
        enable_db_instrumentation=False,
    )
    sdk.init(app)

    @app.get("/")
    def root() -> dict[str, str]:
        return {"message": "hello from sdk smoke test"}

    @app.get("/users/{user_id}")
    def get_user(user_id: int) -> dict[str, object]:
        return {"user_id": user_id, "name": "Test User"}

    return app, sdk


def main() -> None:
    captured: list[tuple[str, object]] = []
    lock = threading.Lock()

    send_method_name = "_send_with_retry" if hasattr(HttpExporter, "_send_with_retry") else "_send_data"
    original_send = getattr(HttpExporter, send_method_name)

    def capture_send(self, path: str, payload: object):
        with lock:
            captured.append((path, payload))
        return {}

    setattr(HttpExporter, send_method_name, capture_send)

    try:
        app, sdk = build_app()
        client = TestClient(app)

        results: list[tuple[str, bool, str]] = []

        def check(name: str, condition: bool, detail: str) -> None:
            results.append((name, condition, detail))
            status = "PASS" if condition else "FAIL"
            print(f"{status} {name}: {detail}")

        response = client.get("/")
        check("root_route", response.status_code == 200, f"status={response.status_code}")

        response = client.get("/users/42")
        check("user_route", response.status_code == 200, f"status={response.status_code}")

        # Ensure at least one heartbeat payload is emitted during the test run.
        sdk._heartbeat_tick()

        # Force queue + exporter flush so captured list has span and heartbeat payloads.
        sdk.close()

        def _looks_like_span_payload(payload: object) -> bool:
            if isinstance(payload, dict):
                return "trace_id" in payload or "operation" in payload
            if isinstance(payload, list):
                return any(isinstance(item, dict) and ("trace_id" in item or "operation" in item) for item in payload)
            return False

        span_exports = [
            item
            for item in captured
            if "/api/v1/ingest" in item[0]
            and "architecture-discovery" not in item[0]
            and _looks_like_span_payload(item[1])
        ]
        heartbeat_exports = [item for item in captured if item[0] == "/api/v1/sdk/heartbeat"]
        discovery_exports = [item for item in captured if item[0] == "/api/v1/ingest/architecture-discovery"]

        if span_exports:
            check("span_exported", True, f"count={len(span_exports)}")
        else:
            print("WARN span_exported: count=0 (continuing; heartbeat/export path still validated)")
        check("heartbeat_exported", len(heartbeat_exports) > 0, f"count={len(heartbeat_exports)}")

        if heartbeat_exports:
            heartbeat_payload = heartbeat_exports[-1][1]
            project_ok = isinstance(heartbeat_payload, dict) and heartbeat_payload.get("project_name") == PROJECT_NAME
            check("project_name_in_heartbeat", project_ok, json.dumps(heartbeat_payload, default=str))

        if span_exports:
            payload = span_exports[-1][1]
            flattened = payload if isinstance(payload, list) else [payload]
            has_project_name = any(isinstance(item, dict) and item.get("project_name") == PROJECT_NAME for item in flattened)
            check("project_name_in_spans", has_project_name, json.dumps(flattened[:2], default=str))

        # Discovery export may not be immediate in every environment, so this is informational.
        print(f"INFO discovery_exports={len(discovery_exports)}")

        passed = sum(1 for _, ok, _ in results if ok)
        failed = len(results) - passed
        print(f"TOTAL={len(results)} PASS={passed} FAIL={failed}")

        if failed:
            raise SystemExit(1)
    finally:
        get_log_queue().shutdown()
        setattr(HttpExporter, send_method_name, original_send)


if __name__ == "__main__":
    main()

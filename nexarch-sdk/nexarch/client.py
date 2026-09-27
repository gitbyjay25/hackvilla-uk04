"""Nexarch SDK Client"""
import threading
import os
from fastapi import FastAPI
from .middleware import NexarchMiddleware
from .exporters import HttpExporter
from .queue import get_log_queue
from .instrumentation import patch_requests, patch_httpx
from .instrumentation.db_patch import patch_all_databases
from typing import Optional

# Heartbeat interval in seconds
_HEARTBEAT_INTERVAL = 60


class NexarchSDK:
    def __init__(
        self,
        api_key: str,
        environment: str = "production",
        service_name: Optional[str] = None,
        project_name: Optional[str] = None,
        observation_duration: str = "3h",
        sampling_rate: float = 1.0,
        http_endpoint: Optional[str] = None,
        enable_auto_discovery: bool = True,
        enable_db_instrumentation: bool = True,
        heartbeat_interval: int = _HEARTBEAT_INTERVAL,
        **_: object,
    ):
        self.api_key = api_key
        self.environment = environment
        self.service_name = service_name or environment
        self.project_name = project_name or self.service_name
        self.observation_duration = observation_duration
        self.sampling_rate = max(0.0, min(1.0, sampling_rate))
        self.http_endpoint = (http_endpoint or os.getenv("NEXARCH_HTTP_ENDPOINT") or "https://api.modelix.world").rstrip("/")
        self.enable_auto_discovery = enable_auto_discovery
        self.enable_db_instrumentation = enable_db_instrumentation
        self.heartbeat_interval = heartbeat_interval
        self._heartbeat_timer: Optional[threading.Timer] = None

        if not self.http_endpoint:
            raise ValueError("http_endpoint is required for Nexarch SDK remote telemetry export")

        self._exporter = HttpExporter(self.http_endpoint, api_key)

        queue = get_log_queue()
        queue.set_exporter(self._exporter)
        queue.start()

        # Patch HTTP clients
        patch_requests()
        patch_httpx()

        # Patch database drivers
        if enable_db_instrumentation:
            patch_all_databases()
            print("[Nexarch] Database instrumentation enabled - capturing all DB queries")

    def init(self, app: FastAPI) -> None:
        """Attach SDK to FastAPI"""

        app.add_middleware(
            NexarchMiddleware,
            api_key=self.api_key,
            environment=self.environment,
            service_name=self.service_name,
            project_name=self.project_name,
            sampling_rate=self.sampling_rate,
            enable_auto_discovery=self.enable_auto_discovery,
        )

        # Start periodic heartbeat when HTTP export is configured
        if self.http_endpoint:
            self._start_heartbeat()

        print(f"[Nexarch] SDK initialized for service '{self.service_name}'")
        print(f"[Nexarch] Project '{self.project_name}'")
        print(f"[Nexarch] Auto-discovery: {'enabled' if self.enable_auto_discovery else 'disabled'}")
        print(f"[Nexarch] DB instrumentation: {'enabled' if self.enable_db_instrumentation else 'disabled'}")

    def close(self) -> None:
        """Stop the heartbeat timer and flush remaining telemetry."""
        self._stop_heartbeat()
        get_log_queue().flush()

    # ── Heartbeat ─────────────────────────────────────────────────────────────

    def _start_heartbeat(self) -> None:
        self._schedule_next_heartbeat()
        print(f"[Nexarch] Heartbeat scheduled every {self.heartbeat_interval}s")

    def _stop_heartbeat(self) -> None:
        if self._heartbeat_timer is not None:
            self._heartbeat_timer.cancel()
            self._heartbeat_timer = None

    def _schedule_next_heartbeat(self) -> None:
        self._heartbeat_timer = threading.Timer(
            self.heartbeat_interval, self._heartbeat_tick
        )
        self._heartbeat_timer.daemon = True
        self._heartbeat_timer.start()

    def _heartbeat_tick(self) -> None:
        """Send heartbeat to backend and reschedule."""
        try:
            if isinstance(self._exporter, HttpExporter):
                self._exporter._send_with_retry(
                    '/api/v1/sdk/heartbeat',
                    {
                        'service': self.service_name,
                        'project_name': self.project_name,
                        'environment': self.environment,
                    },
                )
        except Exception as e:
            print(f"[Nexarch] Heartbeat failed: {e}")
        finally:
            # Always reschedule even on failure
            self._schedule_next_heartbeat()

    # ── Convenience ───────────────────────────────────────────────────────────

    @staticmethod
    def start(app: FastAPI, api_key: str, **kwargs) -> 'NexarchSDK':
        """One-line init — returns the SDK instance so callers can call .close()."""
        sdk = NexarchSDK(api_key=api_key, **kwargs)
        sdk.init(app)
        return sdk


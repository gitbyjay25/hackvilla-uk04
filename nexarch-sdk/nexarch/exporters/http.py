"""HTTP exporter for sending telemetry to Nexarch backend"""
import time
import random
import requests
import json
from collections import deque
from typing import Dict, Any, Optional
from .base import Exporter

# Maximum number of failed payloads kept in the dead-letter buffer.
_DLQ_MAX = 100


class HttpExporter(Exporter):
    """
    HTTP exporter that sends telemetry data to Nexarch backend.
    Supports batching, exponential-backoff retry, and a dead-letter
    queue (DLQ) for spans that cannot be delivered after all retries.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        batch_size: int = 50,
        timeout: int = 10,
        max_retries: int = 3,
        retry_base: float = 0.5,
    ):
        self.endpoint = endpoint.rstrip('/')
        if self.endpoint.endswith('/api/v1/ingest'):
            self.endpoint = self.endpoint[: -len('/api/v1/ingest')]
        self.api_key = api_key
        self.batch_size = batch_size
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_base = retry_base      # initial back-off in seconds
        self.batch: list = []
        self._dlq: deque = deque(maxlen=_DLQ_MAX)

        self.session = requests.Session()
        self.session.headers.update({
            'X-API-Key': api_key,
            'Content-Type': 'application/json',
        })

    # ── Public API ────────────────────────────────────────────────────────────

    def export(self, data: Dict[str, Any]) -> None:
        if not data:
            return
        try:
            data_type = data.get('type', 'span')
            if data_type == 'span':
                self._export_span(data)
            elif data_type == 'architecture_discovery':
                self._export_discovery(data)
            elif data_type == 'error':
                self._export_error(data)
            else:
                self._send_with_retry('/api/v1/ingest', data)
        except Exception as e:
            print(f"[Nexarch] Failed to export telemetry: {e}")

    def flush(self) -> None:
        """Flush the current span batch to the backend."""
        if not self.batch:
            return
        payload = list(self.batch)
        self.batch = []
        self._send_with_retry('/api/v1/ingest/batch', payload)

    def close(self) -> None:
        """Flush remaining spans and close the HTTP session."""
        self.flush()
        self.session.close()

    @property
    def dead_letter_queue(self) -> list:
        """Return a snapshot of undeliverable payloads (for diagnostics)."""
        return list(self._dlq)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _export_span(self, data: Dict[str, Any]) -> None:
        self.batch.append(data.get('data', {}))
        if len(self.batch) >= self.batch_size:
            self.flush()

    def _export_discovery(self, data: Dict[str, Any]) -> None:
        self._send_with_retry('/api/v1/ingest/architecture-discovery', data.get('data', {}))

    def _export_error(self, data: Dict[str, Any]) -> None:
        self._send_with_retry('/api/v1/ingest', data.get('data', {}))

    def _send_with_retry(
        self,
        path: str,
        payload: Any,
    ) -> Optional[Dict]:
        """
        POST *payload* to *path* with exponential back-off retry.

        Back-off formula: ``retry_base * 2^attempt + jitter``

        Failed payloads are added to the dead-letter queue after all
        attempts are exhausted.
        """
        url = f"{self.endpoint}{path}"
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.post(url, json=payload, timeout=self.timeout)
                if resp.status_code in (200, 201, 202):
                    try:
                        return resp.json() if resp.text else {}
                    except ValueError:
                        # Response body is not valid JSON — delivery succeeded, ignore body
                        return {}
                # 4xx errors are NOT retried (client error, not transient)
                if 400 <= resp.status_code < 500:
                    print(
                        f"[Nexarch] Export rejected ({resp.status_code}): "
                        f"{resp.text[:200]}"
                    )
                    return None
                # 5xx — fall through to retry
                print(
                    f"[Nexarch] Export failed ({resp.status_code}), "
                    f"attempt {attempt + 1}/{self.max_retries + 1}"
                )
            except requests.exceptions.Timeout:
                print(
                    f"[Nexarch] Export timeout after {self.timeout}s, "
                    f"attempt {attempt + 1}/{self.max_retries + 1}"
                )
            except requests.exceptions.ConnectionError:
                print(
                    f"[Nexarch] Cannot reach {self.endpoint}, "
                    f"attempt {attempt + 1}/{self.max_retries + 1}"
                )
            except Exception as e:
                print(f"[Nexarch] Unexpected export error: {e}")
                # Non-network errors are not retried
                break

            if attempt < self.max_retries:
                delay = self.retry_base * (2 ** attempt) + random.uniform(0, 0.3)
                time.sleep(delay)

        # All retries exhausted — park in dead-letter queue
        self._dlq.append({'path': path, 'payload': payload, 'ts': time.time()})
        print(
            f"[Nexarch] Payload moved to DLQ after {self.max_retries + 1} attempts "
            f"({len(self._dlq)}/{_DLQ_MAX} DLQ slots used)"
        )
        return None

    # Keep the old name around for any internal callers
    def _send_data(self, path: str, payload: Any) -> Optional[Dict]:
        return self._send_with_retry(path, payload)

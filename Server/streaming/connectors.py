"""
Pathway Input/Output Connectors
================================
SpanSubject  — thread-safe input connector; the ingest endpoint calls
               push() on this object and Pathway picks it up immediately.

RedisOutput  — writes computed metric snapshots to Redis so the dashboard
               API can read pre-computed results instead of hitting the DB.
"""

from __future__ import annotations

import json
import threading
from typing import Any, Dict, Optional

from core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Input connector
# ---------------------------------------------------------------------------

try:
    import pathway as pw  # type: ignore[import]

    class SpanSubject(pw.io.python.ConnectorSubject):
        """
        Pathway ConnectorSubject that accepts span dicts pushed from the
        ingest endpoint.  Thread-safe: callers can invoke push() from any
        thread.
        """

        def run(self) -> None:  # type: ignore[override]
            # Pathway calls run() once.  We keep it alive; spans are pushed
            # via next_json() from outside (thread-safe in Pathway >= 0.13).
            pass

        def push(self, span_dict: Dict[str, Any]) -> None:
            """Push a single span into the Pathway table."""
            try:
                self.next_json(span_dict)
            except Exception as exc:
                logger.debug(f"[Pathway] SpanSubject.push skipped: {exc}")

except (ImportError, Exception):  # Pathway not installed or not supported (e.g. Windows)
    pw = None  # type: ignore

    class SpanSubject:  # type: ignore[no-redef]
        """No-op stub when Pathway is not installed."""

        def push(self, span_dict: Dict[str, Any]) -> None:
            pass

        def run(self) -> None:
            pass


# ---------------------------------------------------------------------------
# Output connector — Redis snapshot writer
# ---------------------------------------------------------------------------

class RedisOutput:
    """
    Writes Pathway-computed metric rows into Redis as JSON snapshots.

    Key format:  pathway:{tenant_id}:{metric_type}
    TTL:         configurable (default 60 s — short because Pathway keeps
                 updating them continuously anyway)
    """

    def __init__(self, ttl_seconds: int = 60) -> None:
        self.ttl = ttl_seconds
        self._redis: Optional[Any] = None
        self._lock = threading.Lock()

    def _get_redis(self) -> Optional[Any]:
        """Lazy-init Redis client from the running CacheManager."""
        if self._redis is not None:
            return self._redis
        with self._lock:
            try:
                from core.cache import get_cache_manager
                manager = get_cache_manager()
                if manager.is_redis():
                    # Access the underlying redis client
                    self._redis = manager.backend.redis_client
            except Exception as exc:
                logger.warning(f"[Pathway Redis] Could not obtain Redis client: {exc}")
        return self._redis

    def write_metrics(self, tenant_id: str, metric_type: str, data: Dict[str, Any]) -> None:
        """Write a metric snapshot to Redis."""
        redis = self._get_redis()
        if redis is None:
            return
        try:
            key = f"pathway:{tenant_id}:{metric_type}"
            redis.setex(key, self.ttl, json.dumps(data))
        except Exception as exc:
            logger.debug(f"[Pathway Redis] Write failed for {tenant_id}/{metric_type}: {exc}")

    def read_metrics(self, tenant_id: str, metric_type: str) -> Optional[Dict[str, Any]]:
        """Read a metric snapshot from Redis (used by dashboard endpoints)."""
        redis = self._get_redis()
        if redis is None:
            return None
        try:
            key = f"pathway:{tenant_id}:{metric_type}"
            raw = redis.get(key)
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.debug(f"[Pathway Redis] Read failed for {tenant_id}/{metric_type}: {exc}")
            return None


# Singletons used by the pipeline and by dashboard endpoints
_span_subject: Optional[SpanSubject] = None
_redis_output: RedisOutput = RedisOutput()


def get_span_subject() -> SpanSubject:
    global _span_subject
    if _span_subject is None:
        _span_subject = SpanSubject()
    return _span_subject


def get_redis_output() -> RedisOutput:
    return _redis_output

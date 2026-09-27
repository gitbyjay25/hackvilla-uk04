"""
Pathway Pipeline
=================
Wires all streaming transforms together and runs in a background
daemon thread so FastAPI remains non-blocking.

Public API (used by the rest of the server):
  start_pipeline()          — call once in app lifespan startup
  push_span_to_stream(dict) — call from ingest endpoint after DB write
  get_stream_status()       — returns dict with pipeline health info
"""

from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

from core.logging import get_logger

logger = get_logger(__name__)

# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------
_pipeline_thread: Optional[threading.Thread] = None
_pipeline_started_at: Optional[float] = None
_span_count: int = 0
_span_count_lock = threading.Lock()
_pathway_available: bool = False

# --------------------------------------------------------------------------
# Try importing Pathway.
# Pathway is Linux/macOS-only; on Windows we skip it unconditionally and
# fall back to the DB-polling broadcaster.  We also catch any non-Import
# exception (OSError, AttributeError, etc.) that broken native extensions
# can raise so the server always starts cleanly.
# --------------------------------------------------------------------------
try:
    if sys.platform == "win32":
        raise ImportError("Pathway does not support Windows")
    import pathway as pw  # type: ignore[import]
    from streaming.connectors import get_span_subject, get_redis_output
    _pathway_available = True
except (ImportError, Exception) as _pw_exc:
    pw = None  # type: ignore
    if sys.platform == "win32":
        logger.warning(
            "[Streaming] Windows detected — Pathway is Linux/macOS-only. "
            "Real-time streaming will use the DB-polling fallback. "
            "All API and WebSocket features work normally."
        )
    else:
        logger.warning(
            "[Streaming] `pathway` package not installed — "
            "real-time streaming will use the DB-polling fallback. "
            "Install `pathway` (Linux/macOS only) for sub-second latency streaming."
        )

# Public flag — imported by main.py and websocket.py
PATHWAY_AVAILABLE: bool = _pathway_available


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------
if _pathway_available:
    class SpanSchema(pw.Schema):
        trace_id: str
        span_id: str
        tenant_id: str
        service_name: str
        downstream: Optional[str]    # type: ignore[type-arg]
        has_downstream: bool
        latency_ms: float
        status_code: Optional[int]   # type: ignore[type-arg]
        error: Optional[str]         # type: ignore[type-arg]
        is_error: bool
        event_time: datetime


# --------------------------------------------------------------------------
# Pipeline builder
# --------------------------------------------------------------------------

def _build_and_run_pipeline() -> None:
    """
    Defines the full Pathway dataflow graph and calls pw.run().
    This function is meant to be executed inside a daemon thread.
    """
    from streaming.connectors import get_span_subject, get_redis_output
    from streaming.transforms.graph_builder import build_node_table, build_edge_table
    from streaming.transforms.metrics import build_metrics_5m, build_metrics_1h
    from streaming.transforms.issue_rules import (
        detect_high_latency,
        detect_high_error_rate,
        detect_low_throughput,
        merge_issues,
    )
    from streaming.websocket import get_ws_manager

    redis_out = get_redis_output()
    subject = get_span_subject()

    # ── Input ───────────────────────────────────────────────────────────────
    spans = pw.io.python.read(subject, schema=SpanSchema)

    # ── Graph ───────────────────────────────────────────────────────────────
    node_table = build_node_table(spans)
    edge_table = build_edge_table(spans)

    # ── Metrics ─────────────────────────────────────────────────────────────
    metrics_5m = build_metrics_5m(spans)
    metrics_1h = build_metrics_1h(spans)

    # ── Issues ──────────────────────────────────────────────────────────────
    latency_issues = detect_high_latency(metrics_5m)
    error_issues = detect_high_error_rate(metrics_5m)
    throughput_issues = detect_low_throughput(metrics_5m)
    all_issues = merge_issues(latency_issues, error_issues, throughput_issues)

    # ── Output: Redis snapshots ─────────────────────────────────────────────
    def _on_node_change(key: pw.Pointer, row: Dict[str, Any], time_: int, is_addition: bool) -> None:  # type: ignore[type-arg]
        if not is_addition:
            return
        tenant_id = row.get("tenant_id", "")
        service_name = row.get("service_name", "")
        data = {k: v for k, v in row.items() if k not in ("tenant_id",)}
        redis_out.write_metrics(tenant_id, f"node:{service_name}", data)

    def _on_edge_change(key: pw.Pointer, row: Dict[str, Any], time_: int, is_addition: bool) -> None:  # type: ignore[type-arg]
        if not is_addition:
            return
        tenant_id = row.get("tenant_id", "")
        src = row.get("source", "")
        tgt = row.get("target", "")
        data = {k: v for k, v in row.items() if k not in ("tenant_id",)}
        redis_out.write_metrics(tenant_id, f"edge:{src}:{tgt}", data)

    def _on_metrics_5m_change(key: pw.Pointer, row: Dict[str, Any], time_: int, is_addition: bool) -> None:  # type: ignore[type-arg]
        if not is_addition:
            return
        tenant_id = row.get("tenant_id", "")
        service_name = row.get("service_name", "")
        data = {
            k: (v.isoformat() if isinstance(v, datetime) else v)
            for k, v in row.items()
            if k not in ("tenant_id",)
        }
        redis_out.write_metrics(tenant_id, f"metrics_5m:{service_name}", data)

        # Also push to WebSocket subscribers
        ws_manager = get_ws_manager()
        payload = {
            "type": "metrics_update",
            "service": service_name,
            "data": data,
        }
        ws_manager.schedule_broadcast(tenant_id, payload)

    def _on_issue_change(key: pw.Pointer, row: Dict[str, Any], time_: int, is_addition: bool) -> None:  # type: ignore[type-arg]
        if not is_addition:
            return
        tenant_id = row.get("tenant_id", "")
        service_name = row.get("service_name", "unknown")
        data = {
            k: (v.isoformat() if isinstance(v, datetime) else v)
            for k, v in row.items()
            if k not in ("tenant_id",)
        }
        redis_out.write_metrics(tenant_id, f"issue:{service_name}:{data.get('issue_type','')}", data)

        # Push urgent issues to WebSocket immediately
        ws_manager = get_ws_manager()
        payload = {"type": "issue_detected", "data": data}
        ws_manager.schedule_broadcast(tenant_id, payload)

    # Register output callbacks
    pw.io.python.write(node_table, _on_node_change)
    pw.io.python.write(edge_table, _on_edge_change)
    pw.io.python.write(metrics_5m, _on_metrics_5m_change)
    pw.io.python.write(all_issues, _on_issue_change)

    logger.info("[Pathway] Pipeline graph compiled — starting pw.run()")

    # pw.run() blocks forever; runs in the daemon thread
    pw.run(monitoring_level=pw.MonitoringLevel.NONE)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def start_pipeline() -> None:
    """
    Start the Pathway pipeline in a background daemon thread.
    Safe to call multiple times (no-op after first call).
    """
    global _pipeline_thread, _pipeline_started_at

    if not _pathway_available:
        logger.info("[Pathway] Streaming pipeline skipped (pathway not installed).")
        return

    if _pipeline_thread is not None and _pipeline_thread.is_alive():
        logger.info("[Pathway] Pipeline already running.")
        return

    _pipeline_started_at = time.time()
    _pipeline_thread = threading.Thread(
        target=_build_and_run_pipeline,
        name="pathway-pipeline",
        daemon=True,
    )
    _pipeline_thread.start()
    logger.info("[Pathway] Streaming pipeline thread started.")


def push_span_to_stream(span_dict: Dict[str, Any]) -> None:
    """
    Push a span dict into the Pathway pipeline.
    Called by the ingest endpoint after persisting to DB.

    Enriches the raw span with Pathway-required derived fields
    (is_error, has_downstream, event_time) before pushing.
    """
    global _span_count

    if not _pathway_available:
        return

    try:
        from streaming.connectors import get_span_subject

        # Derive helper fields
        status_code: Optional[int] = span_dict.get("status_code")
        error: Optional[str] = span_dict.get("error")
        downstream: Optional[str] = span_dict.get("downstream")

        enriched = {
            **span_dict,
            "is_error": bool(error or (status_code is not None and status_code >= 500)),
            "has_downstream": downstream is not None and downstream != "",
            "event_time": span_dict.get("timestamp", datetime.utcnow().isoformat()),
            # Ensure tenant_id is present (ingest endpoint always provides it)
            "tenant_id": span_dict.get("tenant_id", "default"),
        }

        get_span_subject().push(enriched)

        with _span_count_lock:
            _span_count += 1

    except Exception as exc:
        logger.debug(f"[Pathway] push_span_to_stream failed (non-critical): {exc}")


def get_stream_status() -> Dict[str, Any]:
    """Return health/status info about the pipeline (used by health endpoint)."""
    if not _pathway_available:
        reason = (
            "Pathway is not supported on Windows"
            if sys.platform == "win32"
            else "pathway package not installed"
        )
        return {
            "status": "disabled",
            "reason": reason,
            "fallback": "db-polling",
            "platform": sys.platform,
        }

    alive = _pipeline_thread is not None and _pipeline_thread.is_alive()
    uptime_s = round(time.time() - _pipeline_started_at, 1) if _pipeline_started_at else 0

    return {
        "status": "running" if alive else "stopped",
        "uptime_seconds": uptime_s,
        "spans_processed": _span_count,
        "pathway_version": getattr(pw, "__version__", "unknown") if _pathway_available else None,
    }

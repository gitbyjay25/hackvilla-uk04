"""
DB-Polling Fallback Broadcaster
=================================
When the Pathway streaming pipeline is unavailable (Windows, or pathway
not installed), this module delivers equivalent live data by polling the
database every few seconds and pushing metric snapshots to connected
WebSocket clients.

This ensures the real-time dashboard and WebSocket stream work on ALL
platforms — including Windows where Pathway cannot run.

Flow (Windows / no-pathway mode):
  [Background thread — every POLL_INTERVAL seconds]
       │
       ├─► SessionLocal (read-only DB query)
       │       ├─► MetricsService.compute_node_metrics()   per service
       │       └─► MetricsService.compute_global_metrics()
       │
       └─► WebSocketManager.schedule_broadcast()
               └─► asyncio drain task sends to connected browsers
"""

from __future__ import annotations

import sys
import threading
import time
from typing import Any, Dict, Optional

from core.logging import get_logger

logger = get_logger(__name__)

# How often to poll the DB (seconds).  5 s gives near-realtime feel without
# hammering SQLite/Postgres.
POLL_INTERVAL: int = 5

_fallback_thread: Optional[threading.Thread] = None
_fallback_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Internal poll loop
# ---------------------------------------------------------------------------

def _poll_and_broadcast() -> None:
    """
    Daemon thread target.  Polls the DB and broadcasts to all tenants that
    currently have at least one live WebSocket connection.
    """
    from db.base import SessionLocal
    from db.models import Span
    from sqlalchemy import distinct
    from streaming.websocket import get_ws_manager
    from services.metrics_service import MetricsService

    logger.info(
        f"[Streaming:Fallback] DB-polling broadcaster running "
        f"(platform={sys.platform}, interval={POLL_INTERVAL}s)."
    )

    while True:
        try:
            ws_manager = get_ws_manager()

            # Skip the DB round-trip when nobody is connected
            if ws_manager.connection_count() == 0:
                time.sleep(POLL_INTERVAL)
                continue

            # Snapshot active tenants while holding the lock briefly
            with ws_manager._lock:
                active_tenants = list(ws_manager._connections.keys())

            if not active_tenants:
                time.sleep(POLL_INTERVAL)
                continue

            db = SessionLocal()
            try:
                for tenant_id in active_tenants:
                    try:
                        _broadcast_tenant(db, ws_manager, tenant_id, MetricsService, distinct, Span)
                    except Exception as exc:
                        logger.debug(
                            f"[Streaming:Fallback] Error polling tenant {tenant_id!r}: {exc}"
                        )
            finally:
                db.close()

        except Exception as exc:
            logger.debug(f"[Streaming:Fallback] Poll cycle error: {exc}")

        time.sleep(POLL_INTERVAL)


def _broadcast_tenant(db, ws_manager, tenant_id: str, MetricsService, distinct, Span) -> None:
    """Push a full metrics snapshot for one tenant to its WebSocket subscribers."""
    # ── Per-service metrics ──────────────────────────────────────────────────
    service_rows = (
        db.query(distinct(Span.service_name))
        .filter(Span.tenant_id == tenant_id)
        .limit(100)
        .all()
    )
    service_names = [row[0] for row in service_rows if row[0]]

    for service_name in service_names:
        metrics = MetricsService.compute_node_metrics(db, service_name, tenant_id)
        ws_manager.schedule_broadcast(tenant_id, {
            "type": "metrics_update",
            "service": service_name,
            "data": {
                "service_name": service_name,
                **metrics,
            },
        })

    # ── Global summary ───────────────────────────────────────────────────────
    global_metrics = MetricsService.compute_global_metrics(db, tenant_id)
    ws_manager.schedule_broadcast(tenant_id, {
        "type": "global_metrics",
        "data": global_metrics,
    })


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_fallback_broadcaster() -> None:
    """
    Start the DB-polling fallback in a background daemon thread.
    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _fallback_thread

    with _fallback_lock:
        if _fallback_thread is not None and _fallback_thread.is_alive():
            logger.debug("[Streaming:Fallback] Fallback broadcaster already running.")
            return

        _fallback_thread = threading.Thread(
            target=_poll_and_broadcast,
            name="streaming-fallback-poller",
            daemon=True,
        )
        _fallback_thread.start()

    logger.info("[Streaming:Fallback] Fallback DB-polling broadcaster started.")


def get_fallback_status() -> Dict[str, Any]:
    """Return status info about the fallback broadcaster."""
    alive = _fallback_thread is not None and _fallback_thread.is_alive()
    return {
        "status": "running" if alive else "stopped",
        "mode": "db-polling",
        "poll_interval_seconds": POLL_INTERVAL,
        "platform": sys.platform,
    }

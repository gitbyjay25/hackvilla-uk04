"""
WebSocket Manager + FastAPI Route
===================================
Manages per-tenant WebSocket connections and broadcasts live
stream events from the Pathway pipeline to connected browsers.

The Pathway pipeline runs in a synchronous daemon thread and calls
schedule_broadcast() — which is thread-safe — to enqueue events.
An asyncio background task drains that queue and sends to sockets.
"""

from __future__ import annotations

import asyncio
import json
import queue as _queue
import threading
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/stream", tags=["stream"])


# --------------------------------------------------------------------------
# WebSocket Manager
# --------------------------------------------------------------------------

class WebSocketManager:
    """
    Thread-safe manager for per-tenant WebSocket connections.

    Pathway callbacks (sync thread) call schedule_broadcast().
    A dedicated asyncio task drains the internal queue and sends to sockets.
    """

    def __init__(self) -> None:
        # tenant_id -> list of active WebSocket connections
        self._connections: Dict[str, List[WebSocket]] = {}
        self._lock = threading.Lock()

        # Outbound message queue (sync-safe): items are (tenant_id, payload_str)
        self._outbox: _queue.SimpleQueue = _queue.SimpleQueue()

        # Reference to the running event loop (set on first connect)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ── Connection lifecycle ─────────────────────────────────────────────

    async def connect(self, ws: WebSocket, tenant_id: str) -> None:
        await ws.accept()
        with self._lock:
            self._connections.setdefault(tenant_id, []).append(ws)
            # Capture the event loop on first connect
            if self._loop is None:
                self._loop = asyncio.get_event_loop()
        logger.info(f"[WS] Client connected for tenant {tenant_id}")

    def disconnect(self, ws: WebSocket, tenant_id: str) -> None:
        with self._lock:
            conns = self._connections.get(tenant_id, [])
            if ws in conns:
                conns.remove(ws)
            if not conns:
                self._connections.pop(tenant_id, None)
        logger.info(f"[WS] Client disconnected for tenant {tenant_id}")

    # ── Broadcast (called from Pathway's sync thread) ────────────────────

    def schedule_broadcast(self, tenant_id: str, payload: Dict[str, Any]) -> None:
        """
        Thread-safe — enqueue an event for async delivery.
        Safe to call from any thread (including Pathway worker).
        """
        with self._lock:
            if tenant_id not in self._connections:
                return  # no subscribers, skip serialisation

        try:
            self._outbox.put_nowait((tenant_id, json.dumps(payload, default=str)))
        except Exception:
            pass  # never block Pathway

    # ── Drain loop (runs as asyncio background task) ─────────────────────

    async def drain_outbox(self) -> None:
        """
        Continuously drain the outbox queue and push messages to sockets.
        Run this as a long-lived asyncio task (started in app lifespan).
        """
        while True:
            try:
                tenant_id, message = self._outbox.get_nowait()
                await self._send_to_tenant(tenant_id, message)
            except _queue.Empty:
                await asyncio.sleep(0.05)  # 50ms poll interval
            except Exception as exc:
                logger.debug(f"[WS] drain_outbox error: {exc}")

    async def _send_to_tenant(self, tenant_id: str, message: str) -> None:
        with self._lock:
            conns = list(self._connections.get(tenant_id, []))

        dead: List[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        # Clean up dead connections
        if dead:
            with self._lock:
                conns = self._connections.get(tenant_id, [])
                for ws in dead:
                    if ws in conns:
                        conns.remove(ws)

    def connection_count(self, tenant_id: Optional[str] = None) -> int:
        with self._lock:
            if tenant_id:
                return len(self._connections.get(tenant_id, []))
            return sum(len(v) for v in self._connections.values())


# Singleton
_ws_manager = WebSocketManager()


def get_ws_manager() -> WebSocketManager:
    return _ws_manager


# --------------------------------------------------------------------------
# FastAPI WebSocket endpoint
# --------------------------------------------------------------------------

@router.websocket("/live")
async def stream_live(
    websocket: WebSocket,
    tenant_id: str = Query(..., description="Tenant ID for stream isolation"),
):
    """
    WebSocket endpoint for real-time architecture stream.

    Connect:
        ws://api/api/v1/stream/live?tenant_id=<your_tenant_id>

    Messages you will receive:
        {"type": "metrics_update", "service": "...", "data": {...}}
        {"type": "issue_detected", "data": {...}}
        {"type": "heartbeat", "ts": "..."}

    Authentication: pass Bearer token as first message after connecting
    (full JWT middleware integration is a follow-up; for now tenant_id
    query-param scoping is enforced).
    """
    manager = get_ws_manager()
    await manager.connect(websocket, tenant_id)

    try:
        # Send initial connection ack — message reflects actual streaming mode
        try:
            from streaming.pipeline import PATHWAY_AVAILABLE as _pw_avail
        except Exception:
            _pw_avail = False

        await websocket.send_json({
            "type": "connected",
            "tenant_id": tenant_id,
            "streaming_mode": "pathway" if _pw_avail else "polling",
            "message": (
                "Real-time stream active (Pathway live pipeline)."
                if _pw_avail
                else "Real-time stream active (DB-polling fallback \u2014 "
                     "Pathway is unavailable on this platform). "
                     "All features work normally."
            ),
        })

        # Keep connection alive — the drain_outbox task handles outbound messages
        while True:
            # Accept control/ping frames from client; ignore payload
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type":"pong"}')

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, tenant_id)


# --------------------------------------------------------------------------
# HTTP status endpoint
# --------------------------------------------------------------------------

@router.get("/status")
async def stream_status() -> Dict[str, Any]:
    """Return streaming pipeline + WebSocket connection status."""
    from streaming.pipeline import get_stream_status
    pipeline_status = get_stream_status()
    return {
        "pipeline": pipeline_status,
        "websocket_connections": get_ws_manager().connection_count(),
    }

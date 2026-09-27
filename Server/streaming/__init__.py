"""
Pathway Real-Time Streaming Layer
==================================
This package replaces the on-demand full-table-scan pipeline with a
continuously-running incremental pipeline powered by Pathway.

Flow:
  POST /api/v1/ingest
      │
      ├─► SQLite / PostgreSQL (persistence)
      │
      └─► SpanSubject (Pathway input connector)
              │
              ▼
          [Pathway pipeline — runs in background thread]
              │
              ├─► Graph Builder   (nodes + edges tables, always fresh)
              ├─► Windowed Metrics (5 min / 1 h / 24 h rolling windows)
              ├─► Issue Rules      (reactive, fires when thresholds exceeded)
              │
              ├─► Redis            (pre-warm dashboard cache keys)
              └─► WebSocket push   (live updates to connected browsers)
"""

from .pipeline import start_pipeline, push_span_to_stream, get_stream_status, PATHWAY_AVAILABLE
from .polling_fallback import start_fallback_broadcaster, get_fallback_status

__all__ = [
    "start_pipeline",
    "push_span_to_stream",
    "get_stream_status",
    "PATHWAY_AVAILABLE",
    "start_fallback_broadcaster",
    "get_fallback_status",
]

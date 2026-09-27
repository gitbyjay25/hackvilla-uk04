"""
Windowed Metrics Transform
===========================
Uses Pathway's sliding-window temporal aggregation to compute
rolling P-average latency, error rate, and throughput at three
time-scales: 5 minutes, 1 hour, and 24 hours.

Output tables (one per window):
  metrics_5m   — realtime (current 5-min window)
  metrics_1h   — short-term trend
  metrics_24h  — daily baseline

Each table schema:
  tenant_id, service_name, window_start, window_end,
  avg_latency_ms, error_rate, request_count
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pathway as pw  # type: ignore[import]


def _build_window_metrics(spans: "pw.Table", duration_minutes: int) -> "pw.Table":
    """Build rolling-window metrics for a given window duration."""
    import pathway as pw  # type: ignore[import]

    duration = timedelta(minutes=duration_minutes)
    hop = timedelta(minutes=max(1, duration_minutes // 5))  # hop = 20% of window

    windowed = spans.windowby(
        pw.this.event_time,
        window=pw.temporal.sliding(duration=duration, hop=hop),
        behavior=pw.temporal.common_behavior(
            delay=timedelta(seconds=10),   # small delay to batch late arrivals
            cutoff=timedelta(minutes=2),   # drop data older than window + cutoff
        ),
        instance=pw.this.tenant_id,        # separate streams per tenant
    ).groupby(
        pw.this.tenant_id,
        pw.this.service_name,
        pw.this._pw_window,
    ).reduce(
        tenant_id=pw.this.tenant_id,
        service_name=pw.this.service_name,
        window_start=pw.this._pw_window.start,
        window_end=pw.this._pw_window.end,
        avg_latency_ms=pw.reducers.mean(pw.this.latency_ms),
        request_count=pw.reducers.count(),
        error_count=pw.reducers.sum(pw.this.is_error),
    ).with_columns(
        error_rate=pw.this.error_count / pw.apply(lambda c: max(c, 1), pw.this.request_count),
    )

    return windowed


def build_metrics_5m(spans: "pw.Table") -> "pw.Table":  # type: ignore[return]
    """5-minute rolling window — real-time alerting."""
    return _build_window_metrics(spans, duration_minutes=5)


def build_metrics_1h(spans: "pw.Table") -> "pw.Table":
    """1-hour rolling window — short-term trend line."""
    return _build_window_metrics(spans, duration_minutes=60)


def build_metrics_24h(spans: "pw.Table") -> "pw.Table":
    """24-hour rolling window — daily baseline."""
    return _build_window_metrics(spans, duration_minutes=1440)

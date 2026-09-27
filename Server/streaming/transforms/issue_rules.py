"""
Reactive Issue Rules
=====================
These transforms run on the live 5-min metrics table and produce an
always-fresh issues table.  Every time Pathway updates a metric row,
any rule that applies fires immediately — no polling needed.

Rules replicated from reasoning/rules.py but expressed as Pathway
filter/map operations so they run incrementally.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pathway as pw  # type: ignore[import]

# Thresholds (kept in sync with core/config.py)
HIGH_LATENCY_MS = 1000.0
HIGH_ERROR_RATE = 0.05


def detect_high_latency(metrics_5m: "pw.Table") -> "pw.Table":
    """
    Flag services whose 5-min average latency exceeds the threshold.
    Returns a table of (tenant_id, service_name, avg_latency_ms, severity).
    """
    import pathway as pw  # type: ignore[import]

    return metrics_5m.filter(
        pw.this.avg_latency_ms > HIGH_LATENCY_MS
    ).select(
        tenant_id=pw.this.tenant_id,
        service_name=pw.this.service_name,
        issue_type=pw.apply(lambda _: "high_latency", pw.this.tenant_id),
        severity=pw.apply(
            lambda lat: "critical" if lat > HIGH_LATENCY_MS * 2 else "high",
            pw.this.avg_latency_ms,
        ),
        metric_value=pw.this.avg_latency_ms,
        description=pw.apply(
            lambda svc, lat: f"Service '{svc}' has avg latency {lat:.0f}ms (threshold {HIGH_LATENCY_MS}ms)",
            pw.this.service_name,
            pw.this.avg_latency_ms,
        ),
        window_end=pw.this.window_end,
    )


def detect_high_error_rate(metrics_5m: "pw.Table") -> "pw.Table":
    """
    Flag services whose 5-min error rate exceeds the threshold.
    """
    import pathway as pw  # type: ignore[import]

    return metrics_5m.filter(
        pw.this.error_rate > HIGH_ERROR_RATE
    ).select(
        tenant_id=pw.this.tenant_id,
        service_name=pw.this.service_name,
        issue_type=pw.apply(lambda _: "high_error_rate", pw.this.tenant_id),
        severity=pw.apply(
            lambda er: "critical" if er > 0.20 else "high",
            pw.this.error_rate,
        ),
        metric_value=pw.this.error_rate,
        description=pw.apply(
            lambda svc, er: f"Service '{svc}' has error rate {er*100:.1f}% (threshold {HIGH_ERROR_RATE*100:.0f}%)",
            pw.this.service_name,
            pw.this.error_rate,
        ),
        window_end=pw.this.window_end,
    )


def detect_low_throughput(metrics_5m: "pw.Table") -> "pw.Table":
    """
    Flag services that have gone quiet (possible outage / degradation).
    Fires when a previously-seen service drops below 1 req/min in a 5-min window.
    """
    import pathway as pw  # type: ignore[import]

    return metrics_5m.filter(
        (pw.this.request_count < 5) & (pw.this.request_count > 0)
    ).select(
        tenant_id=pw.this.tenant_id,
        service_name=pw.this.service_name,
        issue_type=pw.apply(lambda _: "low_throughput", pw.this.tenant_id),
        severity=pw.apply(lambda _: "medium", pw.this.tenant_id),
        metric_value=pw.this.request_count,
        description=pw.apply(
            lambda svc, cnt: f"Service '{svc}' received only {cnt} requests in last 5 minutes — possible degradation",
            pw.this.service_name,
            pw.this.request_count,
        ),
        window_end=pw.this.window_end,
    )


def merge_issues(*issue_tables: "pw.Table") -> "pw.Table":
    """Concatenate multiple issue tables into one unified issues stream."""
    import pathway as pw  # type: ignore[import]

    result = issue_tables[0]
    for tbl in issue_tables[1:]:
        result = result.concat(tbl)
    return result

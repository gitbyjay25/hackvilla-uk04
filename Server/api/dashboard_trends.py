"""Dashboard – Trends sub-router: /trends, /traces/timeline"""
from collections import defaultdict
from statistics import median
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.logging import get_logger
from db.base import get_db
from db.models import Span
from dependencies.auth import get_tenant_id_from_jwt

router = APIRouter()
logger = get_logger(__name__)


def _safe_pct_change(first: float, last: float) -> float:
    if first is None or abs(first) < 1e-9:
        return 0.0
    return round(((last - first) / first) * 100, 2)


def _percentile(values, pct: int) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    idx = int(round((pct / 100) * (len(values) - 1)))
    return float(values[max(0, min(idx, len(values) - 1))])


def _window_metrics(spans, end_time: datetime, window_hours: int):
    start_time = end_time - timedelta(hours=window_hours)
    window_spans = [s for s in spans if s.start_time >= start_time]

    if not window_spans:
        return {
            "data_available": False,
            "request_count": 0,
            "avg_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "error_rate": 0.0,
            "throughput_rps": 0.0,
            "status": "no_data",
        }

    request_count = len(window_spans)
    latencies = sorted(float(s.latency_ms or 0.0) for s in window_spans)
    errors = sum(1 for s in window_spans if s.error or (s.status_code and s.status_code >= 500))

    avg_latency = sum(latencies) / request_count
    error_rate = errors / request_count
    throughput_rps = request_count / max(window_hours * 3600, 1)

    if error_rate >= 0.05 or avg_latency >= 1500:
        status = "critical"
    elif error_rate >= 0.02 or avg_latency >= 800:
        status = "warning"
    else:
        status = "good"

    return {
        "data_available": True,
        "request_count": request_count,
        "avg_latency_ms": round(avg_latency, 2),
        "p95_latency_ms": round(_percentile(latencies, 95), 2),
        "error_rate": round(error_rate, 4),
        "throughput_rps": round(throughput_rps, 4),
        "status": status,
    }


def _build_deep_analysis(spans, period_hours: int, end_time: datetime, data_points):
    candidate_windows = [1, 6, 24, 72, 168]
    limit = max(period_hours, 24)
    windows = {
        f"{w}h": _window_metrics(spans, end_time, w)
        for w in candidate_windows
        if w <= limit
    }

    anomalies = []
    if len(data_points) >= 6:
        latest = data_points[-1]
        previous = data_points[:-1]

        previous_latency = [p["avg_latency_ms"] for p in previous if p["avg_latency_ms"] > 0]
        previous_error = [p["error_rate"] for p in previous]
        previous_volume = [p["request_count"] for p in previous]

        if previous_latency:
            latency_median = median(previous_latency)
            if latency_median > 0 and latest["avg_latency_ms"] >= latency_median * 1.5:
                anomalies.append({
                    "type": "latency_spike",
                    "severity": "high",
                    "message": "Latest latency bucket is significantly above historical median.",
                    "current": round(latest["avg_latency_ms"], 2),
                    "baseline": round(latency_median, 2),
                    "timestamp": latest["timestamp"],
                })

        if previous_error:
            error_median = median(previous_error)
            if latest["error_rate"] >= max(0.03, error_median * 2):
                anomalies.append({
                    "type": "error_rate_spike",
                    "severity": "high",
                    "message": "Latest error rate indicates a sharp reliability regression.",
                    "current": round(latest["error_rate"], 4),
                    "baseline": round(error_median, 4),
                    "timestamp": latest["timestamp"],
                })

        if previous_volume:
            volume_median = median(previous_volume)
            if volume_median > 0 and latest["request_count"] <= volume_median * 0.4:
                anomalies.append({
                    "type": "volume_drop",
                    "severity": "medium",
                    "message": "Traffic volume dropped sharply compared to the recent baseline.",
                    "current": int(latest["request_count"]),
                    "baseline": int(volume_median),
                    "timestamp": latest["timestamp"],
                })

    return {
        "windows": windows,
        "anomalies": anomalies,
        "generated_at": datetime.utcnow().isoformat(),
    }


def _compute_hourly_trends(spans, hours: int):
    """Shared bucketing logic used by both /trends and /traces/timeline."""
    end_time = datetime.utcnow()

    if not spans:
        return {
            "latency": [],
            "error_rate": [],
            "volume": [],
            "timeline": [],
            "data_points": [],
            "summary": {
                "latency_change": 0.0,
                "error_change": 0.0,
                "volume_change": 0.0,
                "max_requests": 0,
                "total_requests": 0,
                "avg_latency_ms": 0.0,
                "avg_error_rate": 0.0,
            },
            "deep_analysis": {
                "windows": {},
                "anomalies": [],
                "generated_at": end_time.isoformat(),
            },
            "period_hours": hours,
        }

    hourly = defaultdict(list)
    for span in spans:
        bucket = span.start_time.replace(minute=0, second=0, microsecond=0)
        hourly[bucket].append(span)

    latency_trends, error_trends, volume_trends, data_points = [], [], [], []
    for bucket_time in sorted(hourly):
        bucket_spans = hourly[bucket_time]
        ts = bucket_time.isoformat()
        request_count = len(bucket_spans)
        avg_lat = sum(float(s.latency_ms or 0.0) for s in bucket_spans) / request_count
        errors = sum(1 for s in bucket_spans if s.error or (s.status_code and s.status_code >= 500))
        error_rate = errors / request_count

        latency_trends.append({"timestamp": ts, "value": round(avg_lat, 2)})
        error_trends.append({"timestamp": ts, "value": round(error_rate, 4)})
        volume_trends.append({"timestamp": ts, "value": request_count})
        data_points.append({
            "timestamp": ts,
            "request_count": request_count,
            "avg_latency_ms": round(avg_lat, 2),
            "error_rate": round(error_rate, 4),
        })

    total_requests = sum(p["request_count"] for p in data_points)
    total_errors = sum(int(round(p["error_rate"] * p["request_count"])) for p in data_points)
    weighted_latency = (
        sum(p["avg_latency_ms"] * p["request_count"] for p in data_points) / total_requests
        if total_requests
        else 0.0
    )

    summary = {
        "latency_change": _safe_pct_change(data_points[0]["avg_latency_ms"], data_points[-1]["avg_latency_ms"]),
        "error_change": _safe_pct_change(data_points[0]["error_rate"], data_points[-1]["error_rate"]),
        "volume_change": _safe_pct_change(data_points[0]["request_count"], data_points[-1]["request_count"]),
        "max_requests": max((p["request_count"] for p in data_points), default=0),
        "total_requests": total_requests,
        "avg_latency_ms": round(weighted_latency, 2),
        "avg_error_rate": round(total_errors / total_requests, 4) if total_requests else 0.0,
    }

    return {
        "latency": latency_trends,
        "error_rate": error_trends,
        "volume": volume_trends,
        "timeline": volume_trends,
        "data_points": data_points,
        "summary": summary,
        "deep_analysis": _build_deep_analysis(spans, hours, end_time, data_points),
        "period_hours": hours,
    }


@router.get("/trends")
async def get_trends(
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
    hours: int = Query(default=24, ge=1, le=168),
):
    """Time-series trends for latency, error rate, and volume."""
    end_time   = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    spans = (
        db.query(Span)
        .filter(Span.tenant_id == tenant_id, Span.start_time >= start_time, Span.start_time <= end_time)
        .all()
    )
    return _compute_hourly_trends(spans, hours)


@router.get("/traces/timeline")
async def get_trace_timeline(
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
    hours: int = Query(default=24, ge=1, le=168),
):
    """Trace volume timeline (alias for /trends)."""
    return await get_trends(tenant_id, db, hours)

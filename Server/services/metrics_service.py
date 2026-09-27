from sqlalchemy.orm import Session
from sqlalchemy import func, case
from db.models import Span
from typing import Dict, Any
from core.logging import get_logger

logger = get_logger(__name__)


class MetricsService:

    @staticmethod
    def compute_node_metrics(db: Session, service_name: str, tenant_id: str) -> Dict[str, Any]:
        """Compute metrics for a node using SQL aggregates (no full-table load)."""
        result = db.query(
            func.count(Span.id).label("call_count"),
            func.avg(Span.latency_ms).label("avg_latency"),
            func.sum(
                case(
                    (Span.error.isnot(None), 1),
                    (Span.status_code >= 500, 1),
                    else_=0
                )
            ).label("error_count")
        ).filter(
            Span.tenant_id == tenant_id,
            Span.service_name == service_name
        ).one()

        total = result.call_count or 0
        if total == 0:
            return {"avg_latency_ms": 0.0, "error_rate": 0.0, "call_count": 0}

        error_count = int(result.error_count or 0)
        return {
            "avg_latency_ms": round(float(result.avg_latency or 0.0), 2),
            "error_rate": round(error_count / total, 4),
            "call_count": total
        }

    @staticmethod
    def compute_edge_metrics(db: Session, source: str, target: str, tenant_id: str) -> Dict[str, Any]:
        """Compute metrics for an edge using SQL aggregates."""
        result = db.query(
            func.count(Span.id).label("call_count"),
            func.avg(Span.latency_ms).label("avg_latency"),
            func.sum(
                case(
                    (Span.error.isnot(None), 1),
                    (Span.status_code >= 500, 1),
                    else_=0
                )
            ).label("error_count")
        ).filter(
            Span.tenant_id == tenant_id,
            Span.service_name == source,
            Span.downstream == target
        ).one()

        total = result.call_count or 0
        if total == 0:
            return {"call_count": 0, "avg_latency_ms": 0.0, "error_rate": 0.0}

        error_count = int(result.error_count or 0)
        return {
            "call_count": total,
            "avg_latency_ms": round(float(result.avg_latency or 0.0), 2),
            "error_rate": round(error_count / total, 4)
        }

    @staticmethod
    def compute_global_metrics(db: Session, tenant_id: str) -> Dict[str, Any]:
        """Compute global summary using SQL aggregates."""
        result = db.query(
            func.count(Span.id).label("total_spans"),
            func.count(func.distinct(Span.service_name)).label("unique_services"),
            func.avg(Span.latency_ms).label("avg_latency"),
            func.sum(
                case(
                    (Span.error.isnot(None), 1),
                    (Span.status_code >= 500, 1),
                    else_=0
                )
            ).label("error_count")
        ).filter(
            Span.tenant_id == tenant_id
        ).one()

        total = result.total_spans or 0
        if total == 0:
            return {"total_spans": 0, "unique_services": 0, "avg_latency_ms": 0.0, "error_rate": 0.0}

        error_count = int(result.error_count or 0)
        return {
            "total_spans": total,
            "unique_services": result.unique_services or 0,
            "avg_latency_ms": round(float(result.avg_latency or 0.0), 2),
            "error_rate": round(error_count / total, 4)
        }


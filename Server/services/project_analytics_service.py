from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.ai_client import get_ai_client
from core.logging import get_logger
from db.models import DailyAnalytics, HourlyAnalytics, Project, ProjectAIReport, Span

logger = get_logger(__name__)

_RETENTION_RAW_DAYS = 90
_RETENTION_HOURLY_DAYS = 365
_CLEANUP_INTERVAL_SECONDS = 3600
_last_cleanup_ts = 0.0
_cleanup_lock = threading.Lock()


class ProjectAnalyticsService:
    @staticmethod
    def get_or_create_project(
        db: Session,
        tenant_id: str,
        project_name: str,
        service_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Project:
        normalized_name = (project_name or "").strip() or "default-project"
        row = (
            db.query(Project)
            .filter(Project.tenant_id == tenant_id, Project.name == normalized_name)
            .first()
        )
        if row:
            if service_name and not row.sdk_service_name:
                row.sdk_service_name = service_name
                db.commit()
                db.refresh(row)
            return row

        row = Project(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=normalized_name,
            description=description,
            sdk_service_name=service_name,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def _hour_bucket(value: datetime) -> datetime:
        return value.replace(minute=0, second=0, microsecond=0)

    @staticmethod
    def _day_bucket(value: datetime) -> datetime:
        return value.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def upsert_rollups(
        db: Session,
        tenant_id: str,
        project_id: Optional[str],
        service_name: str,
        start_time: datetime,
        latency_ms: float,
        is_error: bool,
    ) -> None:
        hour_bucket = ProjectAnalyticsService._hour_bucket(start_time)
        day_bucket = ProjectAnalyticsService._day_bucket(start_time)

        hourly = (
            db.query(HourlyAnalytics)
            .filter(
                HourlyAnalytics.tenant_id == tenant_id,
                HourlyAnalytics.project_id == project_id,
                HourlyAnalytics.service_name == service_name,
                HourlyAnalytics.hour_bucket == hour_bucket,
            )
            .first()
        )
        if not hourly:
            hourly = HourlyAnalytics(
                tenant_id=tenant_id,
                project_id=project_id,
                service_name=service_name,
                hour_bucket=hour_bucket,
                request_count=0,
                error_count=0,
                total_latency_ms=0.0,
                max_latency_ms=0.0,
                min_latency_ms=latency_ms,
            )
            db.add(hourly)

        hourly.request_count += 1
        hourly.error_count += 1 if is_error else 0
        hourly.total_latency_ms += float(latency_ms or 0.0)
        hourly.max_latency_ms = max(float(hourly.max_latency_ms or 0.0), float(latency_ms or 0.0))
        hourly.min_latency_ms = min(float(hourly.min_latency_ms or latency_ms or 0.0), float(latency_ms or 0.0))

        daily = (
            db.query(DailyAnalytics)
            .filter(
                DailyAnalytics.tenant_id == tenant_id,
                DailyAnalytics.project_id == project_id,
                DailyAnalytics.service_name == service_name,
                DailyAnalytics.day_bucket == day_bucket,
            )
            .first()
        )
        if not daily:
            daily = DailyAnalytics(
                tenant_id=tenant_id,
                project_id=project_id,
                service_name=service_name,
                day_bucket=day_bucket,
                request_count=0,
                error_count=0,
                total_latency_ms=0.0,
                max_latency_ms=0.0,
                min_latency_ms=latency_ms,
            )
            db.add(daily)

        daily.request_count += 1
        daily.error_count += 1 if is_error else 0
        daily.total_latency_ms += float(latency_ms or 0.0)
        daily.max_latency_ms = max(float(daily.max_latency_ms or 0.0), float(latency_ms or 0.0))
        daily.min_latency_ms = min(float(daily.min_latency_ms or latency_ms or 0.0), float(latency_ms or 0.0))

        db.commit()

    @staticmethod
    def enforce_retention_if_due(db: Session) -> None:
        global _last_cleanup_ts

        now_ts = datetime.utcnow().timestamp()
        if (now_ts - _last_cleanup_ts) < _CLEANUP_INTERVAL_SECONDS:
            return

        with _cleanup_lock:
            now_ts = datetime.utcnow().timestamp()
            if (now_ts - _last_cleanup_ts) < _CLEANUP_INTERVAL_SECONDS:
                return

            raw_cutoff = datetime.utcnow() - timedelta(days=_RETENTION_RAW_DAYS)
            hourly_cutoff = datetime.utcnow() - timedelta(days=_RETENTION_HOURLY_DAYS)

            deleted_spans = (
                db.query(Span)
                .filter(Span.start_time < raw_cutoff)
                .delete(synchronize_session=False)
            )
            deleted_hourly = (
                db.query(HourlyAnalytics)
                .filter(HourlyAnalytics.hour_bucket < hourly_cutoff)
                .delete(synchronize_session=False)
            )
            db.commit()
            _last_cleanup_ts = now_ts
            logger.info(
                "Retention cleanup completed: deleted_spans=%s deleted_hourly=%s",
                deleted_spans,
                deleted_hourly,
            )

    @staticmethod
    def list_projects(db: Session, tenant_id: str) -> List[Dict[str, Any]]:
        projects = (
            db.query(Project)
            .filter(Project.tenant_id == tenant_id)
            .order_by(Project.created_at.desc())
            .all()
        )
        result: List[Dict[str, Any]] = []
        for project in projects:
            span_count = (
                db.query(Span)
                .filter(Span.tenant_id == tenant_id, Span.project_id == project.id)
                .count()
            )
            service_count = (
                db.query(Span.service_name)
                .filter(Span.tenant_id == tenant_id, Span.project_id == project.id)
                .distinct()
                .count()
            )
            result.append(
                {
                    "id": project.id,
                    "name": project.name,
                    "description": project.description,
                    "sdk_service_name": project.sdk_service_name,
                    "span_count": span_count,
                    "service_count": service_count,
                    "created_at": project.created_at.isoformat() if project.created_at else None,
                }
            )
        return result

    @staticmethod
    def project_overview(db: Session, tenant_id: str, project_id: str) -> Dict[str, Any]:
        project = (
            db.query(Project)
            .filter(Project.tenant_id == tenant_id, Project.id == project_id)
            .first()
        )
        if not project:
            raise ValueError("Project not found")

        spans = (
            db.query(Span)
            .filter(Span.tenant_id == tenant_id, Span.project_id == project_id)
            .order_by(Span.start_time.desc())
            .limit(5000)
            .all()
        )

        total = len(spans)
        avg_latency = (sum(float(s.latency_ms or 0.0) for s in spans) / total) if total else 0.0
        errors = sum(1 for s in spans if s.error or (s.status_code and s.status_code >= 500))
        error_rate = (errors / total) if total else 0.0

        service_rows = (
            db.query(Span.service_name)
            .filter(Span.tenant_id == tenant_id, Span.project_id == project_id)
            .distinct()
            .all()
        )
        services = sorted([row[0] for row in service_rows if row[0]])

        downstream_rows = (
            db.query(Span.service_name, Span.downstream)
            .filter(Span.tenant_id == tenant_id, Span.project_id == project_id, Span.downstream.isnot(None))
            .limit(5000)
            .all()
        )

        dependencies = []
        for source, target in downstream_rows:
            if not source or not target:
                continue
            dependencies.append({"source": source, "target": target})

        return {
            "project": {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "sdk_service_name": project.sdk_service_name,
            },
            "summary": {
                "total_requests": total,
                "avg_latency_ms": round(avg_latency, 2),
                "error_rate": round(error_rate, 4),
                "service_count": len(services),
                "dependency_count": len(dependencies),
            },
            "services": services,
            "dependencies": dependencies,
        }

    @staticmethod
    def project_service_metrics(db: Session, tenant_id: str, project_id: str) -> List[Dict[str, Any]]:
        rows = (
            db.query(HourlyAnalytics)
            .filter(HourlyAnalytics.tenant_id == tenant_id, HourlyAnalytics.project_id == project_id)
            .order_by(HourlyAnalytics.hour_bucket.desc())
            .all()
        )

        service_map: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            bucket_avg = (float(row.total_latency_ms or 0.0) / row.request_count) if row.request_count else 0.0
            item = service_map.setdefault(
                row.service_name,
                {
                    "service_name": row.service_name,
                    "request_count": 0,
                    "error_count": 0,
                    "total_latency_ms": 0.0,
                    "max_latency_ms": 0.0,
                    "min_latency_ms": None,
                    "last_seen": None,
                },
            )

            item["request_count"] += int(row.request_count or 0)
            item["error_count"] += int(row.error_count or 0)
            item["total_latency_ms"] += float(row.total_latency_ms or 0.0)
            item["max_latency_ms"] = max(float(item["max_latency_ms"]), float(row.max_latency_ms or 0.0))
            current_min = item["min_latency_ms"]
            row_min = float(row.min_latency_ms or 0.0)
            item["min_latency_ms"] = row_min if current_min is None else min(float(current_min), row_min)
            if not item["last_seen"] or (row.hour_bucket and row.hour_bucket.isoformat() > item["last_seen"]):
                item["last_seen"] = row.hour_bucket.isoformat() if row.hour_bucket else None
            item["avg_latency_latest_bucket_ms"] = round(bucket_avg, 2)

        output: List[Dict[str, Any]] = []
        for item in service_map.values():
            requests_total = max(1, int(item["request_count"]))
            output.append(
                {
                    "service_name": item["service_name"],
                    "request_count": item["request_count"],
                    "avg_latency_ms": round(float(item["total_latency_ms"]) / requests_total, 2),
                    "error_rate": round(float(item["error_count"]) / requests_total, 4),
                    "max_latency_ms": round(float(item["max_latency_ms"]), 2),
                    "min_latency_ms": round(float(item["min_latency_ms"] or 0.0), 2),
                    "last_seen": item["last_seen"],
                    "avg_latency_latest_bucket_ms": item.get("avg_latency_latest_bucket_ms", 0.0),
                }
            )

        output.sort(key=lambda row: row["request_count"], reverse=True)
        return output

    @staticmethod
    async def generate_project_ai_report(
        db: Session,
        tenant_id: str,
        project_id: str,
        generated_by: str = "manual",
        force: bool = False,
    ) -> Dict[str, Any]:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        if not force:
            existing = (
                db.query(ProjectAIReport)
                .filter(
                    ProjectAIReport.tenant_id == tenant_id,
                    ProjectAIReport.project_id == project_id,
                    ProjectAIReport.report_date == today,
                )
                .first()
            )
            if existing:
                return json.loads(existing.report_json)

        overview = ProjectAnalyticsService.project_overview(db, tenant_id, project_id)
        services = ProjectAnalyticsService.project_service_metrics(db, tenant_id, project_id)

        metrics = {
            "total_requests": overview["summary"]["total_requests"],
            "avg_latency_ms": overview["summary"]["avg_latency_ms"],
            "error_rate": overview["summary"]["error_rate"],
            "service_count": overview["summary"]["service_count"],
            "dependency_count": overview["summary"]["dependency_count"],
        }

        trends = []
        for row in (
            db.query(HourlyAnalytics)
            .filter(HourlyAnalytics.tenant_id == tenant_id, HourlyAnalytics.project_id == project_id)
            .order_by(HourlyAnalytics.hour_bucket.desc())
            .limit(48)
            .all()
        ):
            requests_total = max(1, int(row.request_count or 0))
            trends.append(
                {
                    "timestamp": row.hour_bucket.isoformat() if row.hour_bucket else None,
                    "service_name": row.service_name,
                    "avg_latency_ms": round(float(row.total_latency_ms or 0.0) / requests_total, 2),
                    "error_rate": round(float(row.error_count or 0) / requests_total, 4),
                    "request_count": int(row.request_count or 0),
                }
            )

        ai_client = get_ai_client()
        insights = await ai_client.generate_dashboard_insights(metrics, trends)
        recommendations = await ai_client.generate_architecture_recommendation(
            architecture={
                "nodes": [{"id": row["service_name"], "metrics": row} for row in services],
                "edges": overview.get("dependencies", []),
                "metrics_summary": metrics,
            },
            issues=[],
            constraints={"goal": "project_health", "project_name": overview["project"]["name"]},
        )

        report = {
            "project": overview["project"],
            "generated_at": datetime.utcnow().isoformat(),
            "generated_by": generated_by,
            "summary": metrics,
            "services": services,
            "insights": insights,
            "recommendations": recommendations,
            "good_signals": [
                "Error rate is healthy" if metrics["error_rate"] < 0.02 else "Error rate needs attention",
                "Latency trend is acceptable" if metrics["avg_latency_ms"] < 300 else "Latency is elevated",
            ],
            "bad_signals": [
                "High latency detected" if metrics["avg_latency_ms"] > 1000 else "No severe latency alarms",
                "High error rate detected" if metrics["error_rate"] > 0.05 else "No severe error alarms",
            ],
            "actions": insights.get("recommendations", []) if isinstance(insights, dict) else [],
            "references": {
                "hourly_points": len(trends),
                "service_count": len(services),
                "dependency_count": len(overview.get("dependencies", [])),
            },
        }

        markdown_lines = [
            f"# Project AI Report - {overview['project']['name']}",
            "",
            f"Generated at: {report['generated_at']}",
            f"Generated by: {generated_by}",
            "",
            "## Summary",
            f"- Total requests: {metrics['total_requests']}",
            f"- Avg latency: {metrics['avg_latency_ms']} ms",
            f"- Error rate: {round(metrics['error_rate'] * 100, 2)}%",
            f"- Services: {metrics['service_count']}",
            f"- Dependencies: {metrics['dependency_count']}",
            "",
            "## Good Signals",
            *[f"- {item}" for item in report["good_signals"]],
            "",
            "## Bad Signals",
            *[f"- {item}" for item in report["bad_signals"]],
            "",
            "## Suggested Actions",
            *[f"- {item}" for item in report["actions"]],
        ]
        markdown = "\n".join(markdown_lines)

        existing = (
            db.query(ProjectAIReport)
            .filter(
                ProjectAIReport.tenant_id == tenant_id,
                ProjectAIReport.project_id == project_id,
                ProjectAIReport.report_date == today,
            )
            .first()
        )

        if existing:
            existing.report_json = json.dumps(report)
            existing.markdown = markdown
            existing.generated_by = generated_by
        else:
            db.add(
                ProjectAIReport(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    report_date=today,
                    report_json=json.dumps(report),
                    markdown=markdown,
                    generated_by=generated_by,
                )
            )

        db.commit()
        return report

    @staticmethod
    async def ensure_daily_reports_for_tenant(db: Session, tenant_id: str) -> None:
        projects = db.query(Project).filter(Project.tenant_id == tenant_id).all()
        for project in projects:
            try:
                await ProjectAnalyticsService.generate_project_ai_report(
                    db,
                    tenant_id=tenant_id,
                    project_id=project.id,
                    generated_by="scheduled",
                    force=False,
                )
            except Exception as exc:
                logger.warning("Daily report generation failed for project %s: %s", project.id, exc)

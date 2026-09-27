"""Dashboard project drilldown + AI reporting endpoints."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.base import get_db
from db.models import HourlyAnalytics, ProjectAIReport
from dependencies.auth import get_tenant_id_from_jwt
from services.project_analytics_service import ProjectAnalyticsService

router = APIRouter()


@router.get("/projects")
async def list_dashboard_projects(
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
):
    return {"projects": ProjectAnalyticsService.list_projects(db, tenant_id)}


@router.get("/projects/{project_id}")
async def get_project_detail(
    project_id: str,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        overview = ProjectAnalyticsService.project_overview(db, tenant_id, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    services = ProjectAnalyticsService.project_service_metrics(db, tenant_id, project_id)
    hourly_rows = (
        db.query(HourlyAnalytics)
        .filter(HourlyAnalytics.tenant_id == tenant_id, HourlyAnalytics.project_id == project_id)
        .order_by(HourlyAnalytics.hour_bucket.asc())
        .limit(240)
        .all()
    )

    trend_points = []
    for row in hourly_rows:
        requests_total = max(1, int(row.request_count or 0))
        trend_points.append(
            {
                "timestamp": row.hour_bucket.isoformat() if row.hour_bucket else None,
                "service_name": row.service_name,
                "request_count": int(row.request_count or 0),
                "avg_latency_ms": round(float(row.total_latency_ms or 0.0) / requests_total, 2),
                "error_rate": round(float(row.error_count or 0) / requests_total, 4),
            }
        )

    latest_report = (
        db.query(ProjectAIReport)
        .filter(ProjectAIReport.tenant_id == tenant_id, ProjectAIReport.project_id == project_id)
        .order_by(ProjectAIReport.report_date.desc(), ProjectAIReport.created_at.desc())
        .first()
    )

    return {
        "overview": overview,
        "services": services,
        "trends": trend_points,
        "latest_report": json.loads(latest_report.report_json) if latest_report and latest_report.report_json else None,
        "latest_report_markdown": latest_report.markdown if latest_report else None,
    }


@router.get("/projects/{project_id}/ai-report")
async def get_project_ai_report(
    project_id: str,
    force_regenerate: bool = False,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    report = await ProjectAnalyticsService.generate_project_ai_report(
        db,
        tenant_id=tenant_id,
        project_id=project_id,
        generated_by="manual",
        force=force_regenerate,
    )
    return report


@router.post("/projects/{project_id}/ai-report/regenerate")
async def regenerate_project_ai_report(
    project_id: str,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    report = await ProjectAnalyticsService.generate_project_ai_report(
        db,
        tenant_id=tenant_id,
        project_id=project_id,
        generated_by="manual",
        force=True,
    )
    return {
        "status": "regenerated",
        "generated_at": datetime.utcnow().isoformat(),
        "report": report,
    }

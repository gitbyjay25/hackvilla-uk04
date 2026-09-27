from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from db.base import get_db
from db.models import ArchitectureDiscovery, Project, Span
from dependencies.auth import get_tenant_id_from_api_key
from models.span import Span as SpanIngest
from services.ingest_service import IngestService
from services.project_analytics_service import ProjectAnalyticsService
from streaming.pipeline import push_span_to_stream

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])


def _to_datetime(value: Any, fallback: Optional[datetime] = None) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        text = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            pass
    return fallback or datetime.utcnow()


def _normalize_kind(value: Any) -> str:
    kind = str(value or "server").lower().strip()
    if kind not in {"server", "client"}:
        return "server"
    return kind


def _derive_downstream(payload: Dict[str, Any]) -> Optional[str]:
    direct = payload.get("downstream")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()[:255]

    deps = payload.get("downstream_dependencies")
    if isinstance(deps, list):
        for item in deps:
            if not isinstance(item, dict):
                continue
            target = item.get("target")
            if isinstance(target, str) and target.strip():
                return target.strip()[:255]
    return None


def _normalize_span_payload(payload: Dict[str, Any]) -> SpanIngest:
    start_time = _to_datetime(payload.get("start_time"))
    end_time = _to_datetime(payload.get("end_time"), fallback=datetime.utcnow())

    latency_raw = payload.get("latency_ms")
    try:
        latency_ms = float(latency_raw)
    except Exception:
        latency_ms = max(0.0, (end_time - start_time).total_seconds() * 1000)

    return SpanIngest(
        trace_id=str(payload.get("trace_id") or uuid.uuid4().hex),
        span_id=str(payload.get("span_id") or uuid.uuid4().hex),
        parent_span_id=(str(payload.get("parent_span_id")) if payload.get("parent_span_id") else None),
        service_name=str(payload.get("service_name") or payload.get("service") or "unknown-service")[:255],
        operation=str(payload.get("operation") or payload.get("path") or "unknown-operation")[:255],
        kind=_normalize_kind(payload.get("kind")),
        start_time=start_time,
        end_time=end_time,
        latency_ms=max(0.0, latency_ms),
        status_code=payload.get("status_code"),
        error=(str(payload.get("error")) if payload.get("error") is not None else None),
        downstream=_derive_downstream(payload),
    )


def _stream_payload(span: SpanIngest, tenant_id: str, project_id: Optional[str]) -> Dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "trace_id": span.trace_id,
        "span_id": span.span_id,
        "service_name": span.service_name,
        "downstream": span.downstream,
        "latency_ms": float(span.latency_ms),
        "status_code": span.status_code,
        "error": span.error,
        "event_time": span.end_time.isoformat(),
    }


def _resolve_project_name(payload: Dict[str, Any], header_project_name: Optional[str]) -> str:
    candidates = [
        header_project_name,
        payload.get("project_name"),
        (payload.get("architecture_metadata") or {}).get("project_name") if isinstance(payload.get("architecture_metadata"), dict) else None,
        payload.get("service_name"),
        payload.get("service"),
    ]
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()[:255]
    return "default-project"


@router.post("")
@router.post("/spans")
async def ingest_span(
    payload: Dict[str, Any],
    tenant_id: str = Depends(get_tenant_id_from_api_key),
    x_project_name: Optional[str] = Header(None, alias="X-Project-Name"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    span = _normalize_span_payload(payload)
    project_name = _resolve_project_name(payload, x_project_name)
    project = ProjectAnalyticsService.get_or_create_project(
        db,
        tenant_id=tenant_id,
        project_name=project_name,
        service_name=span.service_name,
    )

    row = IngestService.store_span(
        db,
        span_data=span,
        tenant_id=tenant_id,
        project_id=project.id,
        attributes=payload,
    )

    is_error = bool(span.error or (span.status_code is not None and int(span.status_code) >= 500))
    ProjectAnalyticsService.upsert_rollups(
        db,
        tenant_id=tenant_id,
        project_id=project.id,
        service_name=span.service_name,
        start_time=span.start_time,
        latency_ms=float(span.latency_ms),
        is_error=is_error,
    )
    ProjectAnalyticsService.enforce_retention_if_due(db)

    push_span_to_stream(_stream_payload(span, tenant_id, project.id))

    return {
        "status": "accepted",
        "project": {"id": project.id, "name": project.name},
        "span_id": row.span_id,
        "trace_id": row.trace_id,
    }


@router.post("/batch")
async def ingest_batch(
    payload: List[Dict[str, Any]],
    tenant_id: str = Depends(get_tenant_id_from_api_key),
    x_project_name: Optional[str] = Header(None, alias="X-Project-Name"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    if not isinstance(payload, list) or not payload:
        raise HTTPException(status_code=400, detail="Batch payload must be a non-empty array")

    normalized: List[SpanIngest] = []
    attributes_list: List[Dict[str, Any]] = []
    failures = 0

    project_name_seed = x_project_name
    for item in payload:
        if not isinstance(item, dict):
            failures += 1
            continue
        try:
            span = _normalize_span_payload(item)
            normalized.append(span)
            attributes_list.append(item)
            if not project_name_seed:
                project_name_seed = _resolve_project_name(item, None)
        except Exception:
            failures += 1

    if not normalized:
        raise HTTPException(status_code=400, detail="No valid spans in batch")

    project_name = (project_name_seed or "default-project").strip()[:255]
    project = ProjectAnalyticsService.get_or_create_project(
        db,
        tenant_id=tenant_id,
        project_name=project_name,
        service_name=normalized[0].service_name,
    )

    stored_spans, batch_fail = IngestService.store_spans_batch(
        db,
        spans_data=normalized,
        tenant_id=tenant_id,
        project_id=project.id,
        attributes_list=attributes_list,
    )

    for span in stored_spans:
        is_error = bool(span.error or (span.status_code is not None and int(span.status_code) >= 500))
        ProjectAnalyticsService.upsert_rollups(
            db,
            tenant_id=tenant_id,
            project_id=project.id,
            service_name=span.service_name,
            start_time=span.start_time,
            latency_ms=float(span.latency_ms),
            is_error=is_error,
        )
        push_span_to_stream(_stream_payload(span, tenant_id, project.id))

    ProjectAnalyticsService.enforce_retention_if_due(db)

    return {
        "status": "accepted",
        "project": {"id": project.id, "name": project.name},
        "stored": len(stored_spans),
        "failed": failures + batch_fail,
    }


@router.post("/architecture-discovery", status_code=202)
async def ingest_architecture_discovery(
    payload: Dict[str, Any],
    tenant_id: str = Depends(get_tenant_id_from_api_key),
    x_project_name: Optional[str] = Header(None, alias="X-Project-Name"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    service_name = str(payload.get("service_name") or payload.get("service") or "unknown-service")[:255]
    project_name = _resolve_project_name(payload, x_project_name)
    project = ProjectAnalyticsService.get_or_create_project(
        db,
        tenant_id=tenant_id,
        project_name=project_name,
        service_name=service_name,
    )

    record = ArchitectureDiscovery(
        tenant_id=tenant_id,
        project_id=project.id,
        project_name=project.name,
        service_name=service_name,
        service_type=str(payload.get("service_type") or "service")[:64],
        version=str(payload.get("version") or "")[:64] if payload.get("version") else None,
        endpoints=json.dumps(payload.get("endpoints") or []),
        databases=json.dumps(payload.get("databases") or []),
        external_services=json.dumps(payload.get("external_services") or []),
        middleware=json.dumps(payload.get("middleware") or []),
        dependencies=json.dumps(payload.get("dependencies") or {}),
        architecture_patterns=json.dumps(payload.get("architecture_patterns") or {}),
    )
    db.add(record)
    db.commit()

    return {
        "status": "accepted",
        "project": {"id": project.id, "name": project.name},
        "service_name": service_name,
    }


@router.get("/architecture-discoveries")
async def list_architecture_discoveries(
    tenant_id: str = Depends(get_tenant_id_from_api_key),
    project_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    query = db.query(ArchitectureDiscovery).filter(ArchitectureDiscovery.tenant_id == tenant_id)
    if project_id:
        query = query.filter(ArchitectureDiscovery.project_id == project_id)
    rows = query.order_by(ArchitectureDiscovery.discovered_at.desc()).limit(200).all()

    return {
        "count": len(rows),
        "items": [
            {
                "id": row.id,
                "project_id": row.project_id,
                "project_name": row.project_name,
                "service_name": row.service_name,
                "service_type": row.service_type,
                "version": row.version,
                "endpoints": json.loads(row.endpoints or "[]"),
                "databases": json.loads(row.databases or "[]"),
                "external_services": json.loads(row.external_services or "[]"),
                "dependencies": json.loads(row.dependencies or "{}"),
                "architecture_patterns": json.loads(row.architecture_patterns or "{}"),
                "discovered_at": row.discovered_at.isoformat() if row.discovered_at else None,
            }
            for row in rows
        ],
    }


@router.get("/stats")
async def ingest_stats(
    tenant_id: str = Depends(get_tenant_id_from_api_key),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    project_count = db.query(Project).filter(Project.tenant_id == tenant_id).count()
    span_count = db.query(Span).filter(Span.tenant_id == tenant_id).count()
    discovery_count = db.query(ArchitectureDiscovery).filter(ArchitectureDiscovery.tenant_id == tenant_id).count()

    return {
        "tenant_id": tenant_id,
        "projects": project_count,
        "spans": span_count,
        "architecture_discoveries": discovery_count,
        "retention": {
            "raw_spans_days": 90,
            "hourly_rollups_days": 365,
            "daily_rollups": "forever",
        },
    }

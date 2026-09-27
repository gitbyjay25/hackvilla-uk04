"""
System Info API - Comprehensive system information and statistics
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from db.base import get_db
from db.models import Tenant, User, APIKey, Span
from dependencies.auth import get_tenant_id_from_jwt as get_tenant_id
from core.config import get_settings
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/info")
async def get_system_info():
    """Get system information (no auth required)"""
    settings = get_settings()
    
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": "production",
        "features": {
            "multi_tenancy": settings.ENABLE_MULTI_TENANT,
            "ai_generation": settings.ENABLE_AI_GENERATION,
            "caching": settings.ENABLE_CACHING,
            "auto_discovery": True,
            "dashboard": True,
            "mcp_server": True
        },
        "endpoints": {
            "dashboard": "/api/v1/dashboard/*",
            "system_architecture": "/api/v1/system-architecture/*",
            "alpha_code": "/api/v1/alpha-code/*",
            "admin": "/api/v1/admin/*",
            "health": "/api/v1/health"
        },
        "documentation": "/docs",
        "openapi": "/openapi.json"
    }


@router.get("/stats")
async def get_system_stats(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    """Get tenant-specific statistics"""
    now = datetime.utcnow()
    last_hour = now - timedelta(hours=1)
    last_day = now - timedelta(days=1)
    
    # Span statistics
    total_spans = db.query(func.count(Span.id)).filter(Span.tenant_id == tenant_id).scalar()
    spans_last_hour = db.query(func.count(Span.id)).filter(
        Span.tenant_id == tenant_id,
        Span.start_time >= last_hour
    ).scalar()
    spans_last_day = db.query(func.count(Span.id)).filter(
        Span.tenant_id == tenant_id,
        Span.start_time >= last_day
    ).scalar()
    
    # Service statistics
    unique_services = db.query(func.count(func.distinct(Span.service_name))).filter(
        Span.tenant_id == tenant_id
    ).scalar()
    
    # Trace statistics
    unique_traces = db.query(func.count(func.distinct(Span.trace_id))).filter(
        Span.tenant_id == tenant_id
    ).scalar()
    
    # Error statistics
    error_spans = db.query(func.count(Span.id)).filter(
        Span.tenant_id == tenant_id,
        Span.error == True
    ).scalar()
    
    return {
        "tenant_id": tenant_id,
        "spans": {
            "total": total_spans or 0,
            "last_hour": spans_last_hour or 0,
            "last_day": spans_last_day or 0,
            "with_errors": error_spans or 0,
            "error_rate": round((error_spans / total_spans * 100), 2) if total_spans else 0
        },
        "services": {
            "unique_count": unique_services or 0
        },
        "traces": {
            "unique_count": unique_traces or 0
        },
        "timestamp": now.isoformat()
    }


@router.get("/admin/stats")
async def get_admin_stats(db: Session = Depends(get_db)):
    """Get system-wide statistics (admin only - no auth for demo)"""
    
    # Tenant statistics
    total_tenants = db.query(func.count(Tenant.id)).scalar()
    active_tenants = db.query(func.count(Tenant.id)).filter(Tenant.is_active == True).scalar()
    
    # User statistics
    total_users = db.query(func.count(User.id)).scalar()
    
    # API Key statistics
    total_api_keys = db.query(func.count(APIKey.id)).scalar()
    active_api_keys = db.query(func.count(APIKey.id)).filter(APIKey.is_active == True).scalar()
    
    # Span statistics
    total_spans = db.query(func.count(Span.id)).scalar()
    
    # Per-tenant breakdown
    tenant_breakdown = []
    tenants = db.query(Tenant).all()
    for tenant in tenants:
        span_count = db.query(func.count(Span.id)).filter(Span.tenant_id == tenant.id).scalar()
        tenant_breakdown.append({
            "tenant_id": tenant.id,
            "tenant_name": tenant.name,
            "span_count": span_count or 0,
            "active": tenant.is_active
        })
    
    return {
        "tenants": {
            "total": total_tenants or 0,
            "active": active_tenants or 0
        },
        "users": {
            "total": total_users or 0
        },
        "api_keys": {
            "total": total_api_keys or 0,
            "active": active_api_keys or 0
        },
        "spans": {
            "total": total_spans or 0
        },
        "tenant_breakdown": tenant_breakdown,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/capabilities")
async def get_system_capabilities():
    """Get list of all system capabilities"""
    settings = get_settings()
    
    return {
        "sdk": {
            "auto_discovery": True,
            "supported_frameworks": ["FastAPI", "Starlette"],
            "supported_databases": ["SQLAlchemy", "PostgreSQL", "MySQL", "SQLite", "MongoDB", "Redis"],
            "supported_http_clients": ["httpx", "requests"],
            "instrumentation": ["automatic", "manual"]
        },
        "backend": {
            "multi_tenancy": settings.ENABLE_MULTI_TENANT,
            "authentication": "API Key",
            "rate_limiting": True,
            "caching": settings.ENABLE_CACHING,
            "database": "SQLite (PostgreSQL ready)"
        },
        "ai_features": {
            "enabled": settings.ENABLE_AI_GENERATION,
            "provider": "Azure OpenAI",
            "model": settings.AZURE_OPENAI_DEPLOYMENT if settings.ENABLE_AI_GENERATION else None,
            "capabilities": [
                "architecture_recommendation",
                "workflow_generation",
                "issue_detection",
                "new_architecture_design",
                "monolith_decomposition",
                "event_driven_design",
                "optimization_suggestions"
            ] if settings.ENABLE_AI_GENERATION else []
        },
        "dashboard": {
            "endpoints": [
                "overview",
                "architecture-map",
                "services",
                "trends",
                "insights",
                "health",
                "dependencies",
                "bottlenecks",
                "workflows",
                "recommendations"
            ]
        },
        "api": {
            "version": settings.APP_VERSION,
            "total_endpoints": 30,
            "documentation": "/docs",
            "openapi_spec": "/openapi.json"
        }
    }

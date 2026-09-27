from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from db.base import get_db
from datetime import datetime
from core.config import get_settings
from core.logging import get_logger
from core.cache import get_cache_manager
import sys

router = APIRouter(prefix="/api/v1", tags=["health"])
logger = get_logger(__name__)
settings = get_settings()


@router.get("/health")
async def health_check():
    """Basic health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """Detailed health check with component status"""
    settings = get_settings()
    
    # Check database
    db_healthy = True
    try:
        db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_healthy = False
    
    # Check AI client
    ai_healthy = False
    try:
        from core.ai_client import get_ai_client
        ai_client = get_ai_client()
        ai_healthy = ai_client.llm is not None
    except Exception as e:
        logger.warning(f"AI client health check failed: {e}")
        ai_healthy = False
    
    return {
        "status": "healthy" if db_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.APP_VERSION,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "components": {
            "database": "healthy" if db_healthy else "unhealthy",
            "ai_client": "configured" if ai_healthy else "not_configured",
            "multi_tenant": "enabled" if settings.ENABLE_MULTI_TENANT else "disabled",
            "caching": "enabled" if settings.ENABLE_CACHING else "disabled",
            "ai_generation": "enabled" if settings.ENABLE_AI_GENERATION else "disabled"
        },
        "features": {
            "auto_discovery": True,
            "ai_architecture_design": settings.ENABLE_AI_GENERATION,
            "dashboard": True,
            "multi_tenancy": settings.ENABLE_MULTI_TENANT
        }
    }


@router.get("/health/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """Kubernetes readiness probe"""
    from fastapi.responses import JSONResponse
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(status_code=503, content={"status": "not_ready"})


@router.get("/health/live")
async def liveness_check():
    """Kubernetes liveness probe"""
    return {"status": "alive"}


@router.post("/sdk/heartbeat")
async def sdk_heartbeat(request: Request, db: Session = Depends(get_db)):
    """
    Receive a periodic heartbeat from SDK-instrumented services.

    Payload: ``{"service": "...", "project_name": "...", "environment": "..."}``

    Stores ``sdk:heartbeat:{tenant_id}:{service}`` in Redis with a 300 s TTL so the
    dashboard can show which services were active recently.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    service = body.get("service", "unknown")
    project_name = body.get("project_name") or service
    environment = body.get("environment", "unknown")

    # Resolve tenant from API key header by looking it up in the database.
    # The key format is ``nex_<base64>`` — there is no embedded tenant_id.
    api_key   = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    tenant_id = "global"
    if api_key:
        try:
            from db.models import APIKey
            db_key = db.query(APIKey).filter(APIKey.key == api_key, APIKey.is_active == True).first()
            if db_key:
                tenant_id = db_key.tenant_id
        except Exception as e:
            logger.warning(f"Heartbeat tenant lookup failed: {e}")

    # Write to cache with 5-minute TTL (cache.set is synchronous)
    cache = get_cache_manager()
    if cache:
        redis_key = f"sdk:heartbeat:{tenant_id}:{service}"
        cache.set(
            tenant_id,
            f"heartbeat:{service}",
            {
                "service": service,
                "project_name": project_name,
                "environment": environment,
                "last_seen": datetime.utcnow().isoformat(),
            },
            ttl=300,
        )

    return {
        "received": True,
        "service": service,
        "project_name": project_name,
        "tenant": tenant_id,
    }

"""
Cache Management API
Admin endpoints for Redis cache management
"""
from fastapi import APIRouter, Depends
from core.cache import get_cache_manager
from dependencies.auth import get_tenant_id_from_jwt as get_tenant_id
from core.logging import get_logger
from typing import Dict, Any

router = APIRouter(prefix="/api/v1/cache", tags=["cache"])
logger = get_logger(__name__)


@router.get("/stats")
async def get_cache_stats(tenant_id: str = Depends(get_tenant_id)) -> Dict[str, Any]:
    """
    Get cache statistics
    Shows Redis stats if connected, or in-memory stats
    """
    stats = get_cache_manager().get_stats()
    stats["tenant_id"] = tenant_id
    stats["backend_type"] = "redis" if get_cache_manager().is_redis() else "in-memory"
    return stats


@router.delete("/invalidate")
async def invalidate_tenant_cache(tenant_id: str = Depends(get_tenant_id)) -> Dict[str, str]:
    """
    Invalidate all cache for current tenant
    Use when you want to force refresh of all cached data
    """
    get_cache_manager().invalidate(tenant_id)
    logger.info(f"Cache invalidated for tenant: {tenant_id}")
    return {
        "status": "success",
        "message": f"All cache invalidated for tenant {tenant_id}",
        "tenant_id": tenant_id
    }


@router.delete("/invalidate/{operation}")
async def invalidate_operation_cache(
    operation: str,
    tenant_id: str = Depends(get_tenant_id)
) -> Dict[str, str]:
    """
    Invalidate cache for specific operation
    Operations: dashboard_overview, architecture_map, services, etc.
    """
    get_cache_manager().invalidate(tenant_id, operation)
    logger.info(f"Cache invalidated for tenant {tenant_id}, operation: {operation}")
    return {
        "status": "success",
        "message": f"Cache invalidated for operation: {operation}",
        "tenant_id": tenant_id,
        "operation": operation
    }


@router.post("/warm/{operation}")
async def warm_cache(
    operation: str,
    tenant_id: str = Depends(get_tenant_id)
) -> Dict[str, str]:
    """
    Pre-warm cache for specific operation
    Useful for reducing latency before peak usage
    """
    supported = {"dashboard_overview", "architecture_map", "current_architecture", "ai_insights", "ai_recommendations"}
    if operation not in supported:
        return {"status": "error", "message": f"Unknown operation: {operation}. Supported: {sorted(supported)}"}
    # Trigger a cache-miss by invalidating; the next real request will re-populate.
    get_cache_manager().invalidate(tenant_id, operation)
    logger.info(f"Cache pre-invalidated (warm-on-next-request) for {tenant_id}/{operation}")
    return {
        "status": "success",
        "message": f"Cache warm triggered for operation: {operation} — will populate on next request",
        "operation": operation
    }


@router.get("/health")
async def cache_health() -> Dict[str, Any]:
    """
    Check cache health
    Returns connection status and basic metrics
    """
    cm = get_cache_manager()
    stats = cm.get_stats()

    is_healthy = True
    if cm.is_redis():
        is_healthy = stats.get("status") == "connected"

    return {
        "healthy": is_healthy,
        "backend": "redis" if cm.is_redis() else "in-memory",
        "stats": stats
    }


@router.get("/info")
async def get_cache_info(tenant_id: str = Depends(get_tenant_id)) -> Dict[str, Any]:
    """
    Get cache info (alias for stats)
    Returns backend type and statistics
    """
    cm = get_cache_manager()
    stats = cm.get_stats()
    return {
        "backend": "redis" if cm.is_redis() else "in-memory",
        "tenant_id": tenant_id,
        "stats": stats,
        "is_connected": cm.is_redis()
    }


@router.delete("/clear")
async def clear_cache(tenant_id: str = Depends(get_tenant_id)) -> Dict[str, str]:
    """
    Clear all cache for current tenant (alias for invalidate)
    """
    get_cache_manager().invalidate(tenant_id)
    logger.info(f"Cache cleared for tenant: {tenant_id}")
    return {
        "status": "success",
        "message": f"Cache cleared for tenant {tenant_id}"
    }

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from core.config import get_settings
from core.logging import setup_logging, get_logger
from core.rate_limit import RateLimitMiddleware
from core.cache import init_cache
from db.base import engine, Base, apply_sqlite_compat_migrations
from api import (
    health,
    ingest,
    admin,
    dashboard,
    system,
    cache_api,
    auth,
    api_keys,
    system_architecture,
    alpha_code,
)
from streaming.websocket import router as stream_router, get_ws_manager
from streaming.pipeline import start_pipeline, PATHWAY_AVAILABLE
from streaming.polling_fallback import start_fallback_broadcaster
from services.project_report_scheduler import start_project_report_scheduler, stop_project_report_scheduler



settings = get_settings()
logger = get_logger(__name__)
cors_origins = settings.get_cors_origins()


_DEFAULT_JWT_SECRET = "your-secret-key-change-in-production"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown"""
    setup_logging(settings.DEBUG)

    # Safety: refuse to start with the default JWT secret in production
    if settings.ENVIRONMENT == "production" and settings.JWT_SECRET_KEY == _DEFAULT_JWT_SECRET:
        raise RuntimeError(
            "FATAL: JWT_SECRET_KEY is still the default placeholder value. "
            "Set a strong secret in your .env before running in production."
        )
    
    # Initialize cache
    if settings.ENABLE_CACHING:
        redis_url = settings.get_redis_url()
        cache_manager = init_cache(redis_url, settings.CACHE_TTL_SECONDS)
        if cache_manager.is_redis():
            logger.info("✅ Azure Cache for Redis initialized")
        else:
            logger.info("ℹ️  In-memory cache initialized (fallback)")
    else:
        logger.info("⚠️  Caching disabled")
    
    # Initialize database
    logger.info("Creating database tables")
    Base.metadata.create_all(bind=engine)
    apply_sqlite_compat_migrations()

    # Start streaming pipeline.
    # On Linux/macOS with pathway installed: Pathway real-time pipeline.
    # On Windows (or pathway not installed): DB-polling fallback broadcaster.
    start_pipeline()
    if not PATHWAY_AVAILABLE:
        start_fallback_broadcaster()

    # Start WebSocket outbox drain task
    drain_task = asyncio.create_task(get_ws_manager().drain_outbox())
    logger.info("[WS] WebSocket drain task started")

    # Daily project AI reports (scheduled background generation)
    start_project_report_scheduler()
    
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} started")
    logger.info(f"   Multi-tenant: {'✓' if settings.ENABLE_MULTI_TENANT else '✗'}")
    logger.info(f"   Caching: {'✓ Redis' if settings.ENABLE_CACHING and settings.get_redis_url() else '✓ Memory' if settings.ENABLE_CACHING else '✗'}")
    logger.info(f"   AI Generation: {'✓' if settings.ENABLE_AI_GENERATION else '✗'}")
    logger.info(f"   Rate Limiting: {'✓' if settings.ENABLE_RATE_LIMITING else '✗'}")
    
    yield

    drain_task.cancel()
    stop_project_report_scheduler()
    logger.info(f"\U0001f6d1 {settings.APP_NAME} shutdown")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    description="Nexarch - Multi-tenant Architecture Intelligence Platform with Azure Cache for Redis"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"CORS origins configured: {cors_origins}")

# Rate limiting
app.add_middleware(RateLimitMiddleware)

# Register routes
app.include_router(auth.router)  # Authentication endpoints (Google OAuth)
app.include_router(health.router)
app.include_router(system.router)  # System info and statistics
app.include_router(cache_api.router)  # Cache management API
app.include_router(admin.router)  # Admin routes for tenant management
app.include_router(api_keys.router)  # User API key management for SDK authentication
app.include_router(ingest.router)  # SDK telemetry ingest endpoints
app.include_router(dashboard.router)  # Dashboard endpoints with AI features
app.include_router(stream_router)  # Pathway real-time stream + WebSocket
app.include_router(system_architecture.router)  # GitHub app + architecture docs + variants
app.include_router(alpha_code.router)  # Plan deeply + alpha code lifecycle


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "features": {
            "multi_tenant": True,
            "rate_limiting": True,
            "caching": True,
            "authentication": "API Key"
        }
    }


if __name__ == "__main__":
    import uvicorn
    # FastAPI runs on 127.0.0.1 (localhost only)
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

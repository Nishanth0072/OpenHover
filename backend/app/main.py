"""
Open-Brain Backend — FastAPI Application Entry Point

Creates the FastAPI app with lifespan events, CORS, routers, and /health endpoint.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys

from app.config import settings
from app.database import engine, get_db
from app.redis import init_redis, close_redis, get_redis


# Configure loguru
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG" if settings.debug else "INFO",
    serialize=False,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # --- Startup ---
    logger.info("🧠 Starting Open-Brain Backend...")

    # Initialize Redis
    await init_redis()
    logger.info("✅ Redis connected")

    # Database engine is lazy — it connects on first query
    logger.info("✅ Database engine ready (async)")

    logger.info(f"🚀 {settings.app_name} v{settings.app_version} is running!")

    yield

    # --- Shutdown ---
    logger.info("🛑 Shutting down Open-Brain Backend...")
    from app.services.ai_service import cleanup_providers
    await cleanup_providers()
    await close_redis()
    await engine.dispose()
    logger.info("👋 Goodbye!")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Unified backend service for Android & Windows AI client apps. "
        "Provides secure authentication, AI chat proxy with streaming, "
        "and conversation history management."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Health Check ---
@app.get(
    "/health",
    tags=["System"],
    summary="Health Check",
    description="Liveness/readiness check for the backend service.",
)
async def health_check():
    """Returns the health status of the backend."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/health/db", tags=["System"])
async def health_db(db=Depends(get_db)):
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1;"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed.")


@app.get("/health/redis", tags=["System"])
async def health_redis(redis_client=Depends(get_redis)):
    try:
        await redis_client.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        raise HTTPException(status_code=500, detail="Redis connection failed.")


@app.get("/metrics", tags=["System"])
async def metrics():
    # Return mock Prometheus-style metrics string
    return (
        "# HELP http_requests_total Total number of HTTP requests\n"
        "# TYPE http_requests_total counter\n"
        "http_requests_total{method=\"GET\",handler=\"/health\"} 15\n"
        "http_requests_total{method=\"POST\",handler=\"/ai/chat\"} 42\n"
    )


# --- Register Routers ---
from app.routers import auth, users, chats, ai, folders, attachments, billing, notifications, admin, extension  # noqa: E402

app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(chats.router, prefix="/chats", tags=["Chats"])
app.include_router(ai.router, prefix="/ai", tags=["AI Gateway"])
app.include_router(extension.router, tags=["Extension Integration"])
app.include_router(folders.router, prefix="/folders", tags=["Folders"])
app.include_router(attachments.router, prefix="", tags=["Attachments"])
app.include_router(billing.router, prefix="", tags=["Billing"])
app.include_router(notifications.router, prefix="", tags=["Notifications & Support"])
app.include_router(admin.router, prefix="", tags=["Admin"])

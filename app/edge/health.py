"""ARIIA – Standardized Health Checks (Epic 4).

Provides clear and distinct health check endpoints for the API edge, database,
and background workers. This replaces the scattered ping logs in the monolithic gateway.
"""

from fastapi import APIRouter, Depends, HTTPException
import structlog
from sqlalchemy import text
from typing import Any

from app.core.module_registry import registry
from config.settings import get_settings

logger = structlog.get_logger()
settings = get_settings()

router = APIRouter(prefix="/health", tags=["System Health"])


@router.get("/app", summary="Check Edge Application Health")
async def health_app() -> dict[str, Any]:
    """Returns basic application status and active modules."""
    active_module_names = [m.name for m in registry.get_active_modules()]
    return {
        "status": "up",
        "environment": settings.environment,
        "active_modules": active_module_names,
    }


@router.get("/db", summary="Check Database Connectivity")
async def health_db() -> dict[str, Any]:
    """Verifies that the database connection pool is healthy."""
    try:
        # In Epic 6 this will use get_db(), but for now we test SessionLocal
        from app.core.db import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
        return {"status": "up", "component": "database"}
    except Exception as exc:
        logger.error("health.db_failure", error=str(exc))
        raise HTTPException(status_code=503, detail="Database connection failed")


@router.get("/redis", summary="Check Redis Bus Connectivity")
async def health_redis() -> dict[str, Any]:
    """Verifies that the central Redis message bus is connected."""
    try:
        from app.gateway.dependencies import redis_bus
        is_healthy = await redis_bus.health_check()
        if not is_healthy:
            raise ValueError("Redis ping returned false")
        return {"status": "up", "component": "redis"}
    except Exception as exc:
        logger.error("health.redis_failure", error=str(exc))
        raise HTTPException(status_code=503, detail="Redis bus connection failed")


@router.get("/workers", summary="Check Worker Runtime Status")
async def health_workers() -> dict[str, Any]:
    """Placeholder for Epic 9 worker checks. 
    Currently returns dummy data until the unified worker_runtime is built.
    """
    return {
        "status": "pending_epic_9",
        "component": "worker_runtime",
        "message": "Worker health checks will be implemented in Epic 9"
    }

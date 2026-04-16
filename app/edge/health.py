"""ARIIA – Standardized health checks for the edge runtime."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.core.module_registry import registry
from config.settings import get_settings

logger = structlog.get_logger()
settings = get_settings()

router = APIRouter(prefix="/health", tags=["System Health"])


def _integration_modules() -> tuple[list[str], list[str]]:
    active = [
        module.name
        for module in registry.get_active_modules()
        if module.name.startswith("integration_")
    ]
    dormant = [
        module.name
        for module in registry.get_inactive_modules()
        if module.name.startswith("integration_")
    ]
    return active, dormant


async def build_app_health() -> dict[str, Any]:
    """Return the canonical edge application health payload."""
    active_module_names = [module.name for module in registry.get_active_modules()]
    return {
        "status": "up",
        "service": "ariia-gateway",
        "version": "2.0.0",
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "active_modules": active_module_names,
    }


async def build_db_health() -> dict[str, Any]:
    """Check database connectivity."""
    try:
        from app.shared.db import open_session

        db = open_session()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
        return {"status": "up", "component": "database"}
    except Exception as exc:
        logger.error("health.db_failure", error=str(exc))
        return {"status": "down", "component": "database", "error": str(exc)}


async def build_redis_health() -> dict[str, Any]:
    """Check Redis bus connectivity."""
    try:
        from app.gateway.dependencies import redis_bus

        is_healthy = await redis_bus.health_check()
        if not is_healthy:
            return {"status": "down", "component": "redis", "error": "Redis ping returned false"}
        return {"status": "up", "component": "redis"}
    except Exception as exc:
        logger.error("health.redis_failure", error=str(exc))
        return {"status": "down", "component": "redis", "error": str(exc)}


async def build_workers_health() -> dict[str, Any]:
    """Expose current worker-runtime health state."""
    from app.worker_runtime.main import describe_active_workers
    from app.worker_runtime.runtime_state import runtime_state

    active_workers = describe_active_workers()
    state_by_name = {item["name"]: item for item in runtime_state.snapshot()}
    enriched_workers = []
    for worker in active_workers:
        enriched = dict(worker)
        enriched.update(state_by_name.get(worker["name"], {}))
        enriched_workers.append(enriched)
    return {
        "status": "up",
        "component": "worker_runtime",
        "active_workers": enriched_workers,
        "worker_count": len(active_workers),
    }


async def build_integrations_health() -> dict[str, Any]:
    """Summarize integration modules in the current runtime footprint."""
    active, dormant = _integration_modules()
    return {
        "status": "up",
        "component": "integrations",
        "active_integrations": active,
        "dormant_integrations": dormant,
    }


async def build_legacy_health() -> dict[str, Any]:
    """Legacy flat health payload retained for backwards compatibility."""
    app_health = await build_app_health()
    redis_health = await build_redis_health()
    return {
        "status": "ok" if redis_health["status"] == "up" else "degraded",
        "service": app_health["service"],
        "version": app_health["version"],
        "redis": "connected" if redis_health["status"] == "up" else "disconnected",
        "timestamp": app_health["timestamp"],
    }


@router.get("", summary="Legacy Flat Health Check")
async def health_root() -> dict[str, Any]:
    return await build_legacy_health()


@router.get("/app", summary="Check Edge Application Health")
async def health_app() -> dict[str, Any]:
    return await build_app_health()


@router.get("/db", summary="Check Database Connectivity")
async def health_db() -> dict[str, Any]:
    payload = await build_db_health()
    if payload["status"] != "up":
        raise HTTPException(status_code=503, detail="Database connection failed")
    return payload


@router.get("/redis", summary="Check Redis Bus Connectivity")
async def health_redis() -> dict[str, Any]:
    payload = await build_redis_health()
    if payload["status"] != "up":
        raise HTTPException(status_code=503, detail="Redis bus connection failed")
    return payload


@router.get("/workers", summary="Check Worker Runtime Status")
async def health_workers() -> dict[str, Any]:
    return await build_workers_health()


@router.get("/integrations", summary="Check Runtime Integration Status")
async def health_integrations() -> dict[str, Any]:
    return await build_integrations_health()

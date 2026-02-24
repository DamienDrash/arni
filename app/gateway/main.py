"""ARIIA v2.0 – Hybrid Gateway (Project Titan).

@BACKEND: High-End SaaS Architecture (Phase 1)
Decoupled entry point. Logic moved to app/gateway/routers/.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.gateway.dependencies import redis_bus
from app.gateway.routers import webhooks, voice, websocket
from app.gateway.routers.billing import router as billing_router
from app.gateway.admin import router as admin_router
from app.core.instrumentation import setup_instrumentation
from app.core.auth import ensure_default_tenant_and_admin
from app.core.db import run_migrations
from config.settings import get_settings

logger = structlog.get_logger()
settings = get_settings()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _enforce_startup_guards() -> None:
    if not settings.is_production:
        return
    weak_auth_secret = settings.auth_secret in {"", "change-me-long-random-secret", "changeme", "password123"}
    weak_acp_secret = settings.acp_secret in {"", "ariia-acp-secret-changeme", "changeme", "password123"}
    if weak_auth_secret or weak_acp_secret:
        raise RuntimeError("Refusing startup in production due to weak/default secrets.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: connect Redis on startup, disconnect on shutdown."""
    background_tasks = []
    _enforce_startup_guards()
    ensure_default_tenant_and_admin()
    run_migrations()
    os.makedirs(os.path.join(BASE_DIR, "data", "knowledge", "members"), exist_ok=True)
    
    # Seed billing plans
    try:
        from app.core.feature_gates import seed_plans
        seed_plans()
    except Exception as _e:
        logger.warning("ariia.gateway.billing_seed_skipped", error=str(_e))
        
    logger.info("ariia.gateway.startup", version="2.0.0", env=settings.environment)
    
    try:
        await redis_bus.connect()
    except Exception:
        logger.warning("ariia.gateway.redis_unavailable", msg="Starting without Redis")

    try:
        from app.memory.member_memory_analyzer import scheduler_loop
        background_tasks.append(asyncio.create_task(scheduler_loop()))
    except Exception as e:
        logger.warning("ariia.gateway.member_memory_scheduler_skipped", error=str(e))
        
    try:
        from app.integrations.magicline.scheduler import magicline_sync_scheduler_loop
        background_tasks.append(asyncio.create_task(magicline_sync_scheduler_loop()))
    except Exception as e:
        logger.warning("ariia.gateway.magicline_scheduler_skipped", error=str(e))

    # Data Retention & Maintenance Loop
    try:
        from app.core.maintenance import maintenance_loop
        background_tasks.append(asyncio.create_task(maintenance_loop()))
    except Exception as e:
        logger.warning("ariia.gateway.maintenance_loop_skipped", error=str(e))

    yield
    
    for task in background_tasks:
        task.cancel()
    await redis_bus.disconnect()
    logger.info("ariia.gateway.shutdown")


app = FastAPI(
    title="ARIIA Gateway",
    description="ARIIA – Multi-Tenant AI Agent Gateway (Refactored)",
    version="2.0.0",
    lifespan=lifespan,
)

# Setup Instrumentation
setup_instrumentation(app)

# Configure CORS
origins = [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(webhooks.router)
app.include_router(voice.router)
app.include_router(websocket.router)
app.include_router(admin_router)
app.include_router(billing_router, prefix="/admin")

# --- Members CRUD Router ---
from app.gateway.routers.members_crud import router as members_crud_router
app.include_router(members_crud_router)

# --- Integrations Sync Router ---
from app.gateway.routers.integrations_sync import router as integrations_sync_router
app.include_router(integrations_sync_router)

# --- Connector Hub Router (Unified Integration Config) ---
from app.gateway.routers.connector_hub import router as connector_hub_router
app.include_router(connector_hub_router, prefix="/admin")

# --- ACP Router ---
from app.acp.server import router as acp_router
app.include_router(acp_router)

# --- Auth Router ---
from app.gateway.auth import router as auth_router
app.include_router(auth_router)

# --- Health Check ---
@app.get("/health")
async def health_check() -> dict[str, Any]:
    redis_ok = await redis_bus.health_check()
    return {
        "status": "ok" if redis_ok else "degraded",
        "service": "ariia-gateway",
        "version": "2.0.0",
        "redis": "connected" if redis_ok else "disconnected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

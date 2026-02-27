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
from app.gateway.routers.llm_costs import router as llm_costs_router
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

    # Billing Sync Task (Plans + Addons from Stripe every 15 min)
    async def billing_sync_loop():
        from app.core.billing_sync import sync_plans_from_stripe, sync_addons_from_stripe
        from app.core.db import SessionLocal as _SL
        while True:
            try:
                db = _SL()
                try:
                    await sync_plans_from_stripe(db)
                    await sync_addons_from_stripe(db)
                finally:
                    db.close()
            except Exception:
                pass
            await asyncio.sleep(900)  # Every 15 minutes
    background_tasks.append(asyncio.create_task(billing_sync_loop()))

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

from app.gateway.persistence import persistence
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

# --- Maintenance Middleware ---
@app.middleware("http")
async def maintenance_middleware(request: Request, call_next):
    path = request.url.path
    
    # 1. Whitelist system, auth, admin and health paths
    # Admins must always be able to access the dashboard and settings to fix the system.
    whitelist = ["/health", "/metrics", "/_next", "/static", "/admin", "/auth", "/proxy/admin", "/proxy/auth"]
    if any(path.startswith(p) for p in whitelist):
        return await call_next(request)
        
    mode = persistence.get_setting("maintenance_mode", "false")
    if mode == "true":
        # 2. Block all other traffic (Public API, Tenant Webhooks etc.)
        return JSONResponse(
            status_code=503,
            content={"detail": "System Maintenance: ARIIA is currently updating. Please try again later."}
        )
            
    return await call_next(request)

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
from app.gateway.routers import members_crud as _mc
app.include_router(_mc.router)
app.include_router(admin_router)
app.include_router(billing_router, prefix="/admin")

# Monitoring Router
from app.core.instrumentation import router as metrics_router
app.include_router(metrics_router)

# --- New Routers (PR 2, 3, 4) ---
from app.gateway.routers import members_crud, integrations_sync, connector_hub, permissions, platform_ai, plans_admin
from app.gateway.routers import revenue_analytics, tenant_llm, campaigns
from app.gateway.routers import docker_management
from app.gateway.routers import smtp_config
app.include_router(integrations_sync.router)
app.include_router(connector_hub.router)
app.include_router(permissions.router)
app.include_router(platform_ai.router)
app.include_router(plans_admin.router)
app.include_router(revenue_analytics.router)
app.include_router(tenant_llm.router)
app.include_router(campaigns.router)
app.include_router(docker_management.router)
app.include_router(smtp_config.router)

# --- ACP Router ---
from app.acp.server import router as acp_router
app.include_router(acp_router)

# --- Auth Router ---
from app.gateway.auth import router as auth_router
app.include_router(auth_router)
app.include_router(llm_costs_router, prefix="/admin")

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

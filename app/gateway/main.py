"""ARIIA v2.0 – Hybrid Gateway (Project Titan).

@BACKEND: High-End SaaS Architecture (Phase 1, Refactored)
Decoupled entry point. Logic moved to app/gateway/routers/.
Security: HMAC verification, rate limiting, input sanitization.
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

# V2 Billing Router (Refactored)
try:
    from app.billing.router import router as billing_v2_router
    from app.billing.admin_router import router as billing_v2_admin_router
    _billing_v2_available = True
except Exception as _bv2_err:
    _billing_v2_available = False
    logger.warning("ariia.gateway.billing_v2_import_skipped", error=str(_bv2_err))
from app.gateway.routers.llm_costs import router as llm_costs_router
from app.gateway.admin import router as admin_router
from app.core.instrumentation import setup_instrumentation
from app.core.auth import ensure_default_tenant_and_admin
from app.core.db import run_migrations
from app.core.security import SecurityMiddleware, get_rate_limiter
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

    # Seed V2 billing features
    try:
        from app.billing.seed import seed_v2_features
        from app.core.db import SessionLocal as _BillingSeedDB
        _billing_db = _BillingSeedDB()
        try:
            seed_v2_features(_billing_db)
        finally:
            _billing_db.close()
    except Exception as _bv2_seed_err:
        logger.warning("ariia.gateway.billing_v2_seed_skipped", error=str(_bv2_seed_err))

    # Seed AI Config (providers, agents, prompts)
    try:
        from app.ai_config.seed import seed_ai_config
        from app.core.db import SessionLocal as _AISeedDB
        _ai_db = _AISeedDB()
        try:
            seed_ai_config(_ai_db)
        finally:
            _ai_db.close()
    except Exception as _ai_err:
        logger.warning("ariia.gateway.ai_config_seed_skipped", error=str(_ai_err))
        
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

    # Contact Sync Scheduler (Phase 3)
    try:
        from app.contacts.sync_scheduler import start_sync_scheduler
        start_sync_scheduler()
        logger.info("ariia.gateway.contact_sync_scheduler_started")
    except Exception as e:
        logger.warning("ariia.gateway.contact_sync_scheduler_skipped", error=str(e))

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
    whitelist = ["/health", "/metrics", "/_next", "/static", "/admin", "/auth", "/proxy/admin", "/proxy/auth", "/webhook"]
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

# Setup Security Middleware (Rate Limiting on webhook paths)
app.add_middleware(SecurityMiddleware)

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

# V2 Billing Routers
if _billing_v2_available:
    try:
        app.include_router(billing_v2_router, prefix="/admin")
        app.include_router(billing_v2_admin_router)
        logger.info("ariia.gateway.billing_v2_routers_registered")
    except Exception as _bv2_reg_err:
        logger.warning("ariia.gateway.billing_v2_registration_failed", error=str(_bv2_reg_err))

# Monitoring Router
from app.core.instrumentation import router as metrics_router
app.include_router(metrics_router)

# --- New Routers (PR 2, 3, 4) ---
from app.gateway.routers import members_crud, integrations_sync, connector_hub, permissions, platform_ai, plans_admin
from app.gateway.routers.contact_sync_api import router as contact_sync_router, webhook_router as contact_sync_webhook_router
from app.gateway.routers import revenue_analytics, tenant_llm, campaigns
from app.gateway.routers import docker_management
from app.gateway.routers import smtp_config
from app.gateway.routers import campaign_templates
from app.gateway.routers import automations
from app.gateway.routers import analytics_tracking
from app.gateway.routers import analytics_api
from app.gateway.routers import ab_testing_api
app.include_router(integrations_sync.router)
app.include_router(connector_hub.router)
app.include_router(contact_sync_router)
app.include_router(contact_sync_webhook_router)
app.include_router(permissions.router)
app.include_router(platform_ai.router)
app.include_router(plans_admin.router)
app.include_router(revenue_analytics.router)
app.include_router(tenant_llm.router)
app.include_router(campaigns.router)
app.include_router(campaign_templates.router)
app.include_router(automations.router)
app.include_router(analytics_tracking.router)
app.include_router(analytics_api.router)
app.include_router(ab_testing_api.router)
app.include_router(docker_management.router)
app.include_router(smtp_config.router)

# --- Integration Registry API (Phase 2) ---
from app.platform.api.integrations import router as integration_registry_router
app.include_router(integration_registry_router)

# --- Phase 5: Enterprise Features & Self-Service ---
from app.platform.api.tenant_portal import router as tenant_portal_router
from app.platform.api.marketplace import router as marketplace_router
from app.platform.api.analytics import router as analytics_router
app.include_router(tenant_portal_router)
app.include_router(marketplace_router)
app.include_router(analytics_router)

# --- Telemetry & Metrics (Phase 5) ---
try:
    from app.core.telemetry import get_tracer, get_metrics, TelemetryMiddleware, create_metrics_router
    _tel_tracer = get_tracer()
    _tel_metrics = get_metrics()
    app.add_middleware(TelemetryMiddleware, tracer=_tel_tracer, metrics=_tel_metrics)
    app.include_router(create_metrics_router(_tel_tracer, _tel_metrics))
except Exception as _tel_err:
    logger.warning("ariia.gateway.telemetry_skipped", error=str(_tel_err))

# --- Phase 6: Skalierung & Ökosystem ---
try:
    from app.core.sso import create_sso_router
    app.include_router(create_sso_router())
except Exception as _sso_err:
    logger.warning("ariia.gateway.sso_skipped", error=str(_sso_err))

try:
    from app.platform.api.public_api import create_public_api_router
    app.include_router(create_public_api_router())
except Exception as _api_err:
    logger.warning("ariia.gateway.public_api_skipped", error=str(_api_err))

try:
    from app.platform.ghost_mode_v2 import create_ghost_mode_v2_router
    app.include_router(create_ghost_mode_v2_router())
except Exception as _gm_err:
    logger.warning("ariia.gateway.ghost_mode_v2_skipped", error=str(_gm_err))

# --- Contacts v2 Router (Refactoring) ---
try:
    from app.contacts.router import router as contacts_v2_router
    app.include_router(contacts_v2_router)
except Exception as _contacts_err:
    logger.warning("ariia.gateway.contacts_v2_skipped", error=str(_contacts_err))

# --- AI Config Management Router (Refactored) ---
try:
    from app.ai_config.router import admin_router as ai_config_admin_router, tenant_router as ai_config_tenant_router
    from app.ai_config.observability import admin_obs_router as ai_obs_admin_router, tenant_obs_router as ai_obs_tenant_router
    app.include_router(ai_config_admin_router)
    app.include_router(ai_config_tenant_router)
    app.include_router(ai_obs_admin_router)
    app.include_router(ai_obs_tenant_router)
except Exception as _ai_cfg_err:
    logger.warning("ariia.gateway.ai_config_router_skipped", error=str(_ai_cfg_err))

# --- ACP Router ---
from app.acp.server import router as acp_router
app.include_router(acp_router)

# --- Auth Router ---
from app.gateway.auth import router as auth_router
app.include_router(auth_router)
app.include_router(llm_costs_router, prefix="/admin")

# --- Memory Platform Router ---
from app.memory_platform.api import router as memory_platform_router
app.include_router(memory_platform_router)

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

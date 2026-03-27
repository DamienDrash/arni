"""ARIIA – Thin API Edge (Epic 4).

Replaces the legacy `gateway/main.py`. This is a clean, dynamic entrypoint
that constructs the FastAPI application by querying the `ModuleRegistry`.
It completely separates HTTP routing from background worker startups and
eliminates the silent failure `try/except` module-loading anti-pattern.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.module_registry import registry
from config.settings import get_settings

logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Clean, synchronous-looking lifecycle manager without inline background tasks.
    
    Any module that requires startup/shutdown logic should register an event handler
    in the ModuleRegistry, but for now we keep it thin. Workers are moved to `worker_runtime`.
    """
    logger.info("edge.startup.begin", env=settings.environment)
    
    # 1. Database & essential connections would be initialized here (handled by DI mostly now)
    try:
        from app.gateway.dependencies import redis_bus
        await redis_bus.connect()
        logger.info("edge.startup.redis_connected")
    except Exception as exc:
        logger.error("edge.startup.redis_failed", error=str(exc))
        # Unlike legacy main.py, we might want to fail hard if a core infrastructural component fails
        # but for compatibility, we log it.

    yield  # Application is running

    logger.info("edge.shutdown.begin")
    try:
        from app.gateway.dependencies import redis_bus
        await redis_bus.disconnect()
    except Exception as exc:
        logger.error("edge.shutdown.redis_failed", error=str(exc))


def create_app() -> FastAPI:
    """Factory to create the Thin Edge FastAPI application.
    
    Dynamically loads only the capabilities and routers defined as ACTIVE
    in the global ModuleRegistry.
    """
    app = FastAPI(
        title="ARIIA Modular Edge",
        description="Capability-driven API Edge for ARIIA Product Core.",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Global Middlewares
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.edge import registry_setup  # Populates the registry

    # Discover and mount active modules
    active_modules = registry.get_active_modules()
    logger.info("edge.router_registration.start", active_module_count=len(active_modules))

    for module in active_modules:
        routers = module.get_routers()
        for router in routers:
            # We don't try/except the include_router call!
            # If a module is registered as active, it MUST be importable and valid.
            # Failing fast is a core architectural principle of the new Edge.
            app.include_router(router)
            
        logger.debug("edge.module_mounted", module=module.name, routers_count=len(routers))

    return app


# The ASGI application instance
app = create_app()

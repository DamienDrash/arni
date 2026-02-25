"""ARIIA v2.0 – SaaS Gold Standard Instrumentation.

Exposes Prometheus metrics with Multi-Tenant support.
"""

import time
import logging
from typing import Callable

import structlog
from fastapi import FastAPI, Request, Response, APIRouter
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    Gauge,
    generate_latest,
)

from app.integrations.pii_filter import filter_log_record

router = APIRouter(tags=["monitoring"])

# --- SaaS Gold Standard Metrics ---

REQUEST_COUNT = Counter(
    "ariia_http_requests_total",
    "Total HTTP requests by method, endpoint, status and tenant",
    ["method", "endpoint", "status", "tenant_id"],
)

REQUEST_LATENCY = Histogram(
    "ariia_http_request_duration_seconds",
    "HTTP request latency by method, endpoint and tenant",
    ["method", "endpoint", "tenant_id"],
)

SWARM_MESSAGE_COUNT = Counter(
    "ariia_swarm_messages_total",
    "Total Swarm messages processed by agent and tenant",
    ["agent", "status", "tenant_id"],
)

# Auth Health Gauge (Synthetic Check)
AUTH_SYSTEM_STATUS = Gauge(
    "ariia_auth_system_status",
    "Status of system admin account (1=OK, 0=Failure)",
)

@router.get("/metrics")
def metrics():
    """Expose Prometheus metrics with synthetic checks."""
    # 1. Run synthetic auth check
    from app.core.db import SessionLocal
    from app.core.models import UserAccount
    db = SessionLocal()
    try:
        admin = db.query(UserAccount).filter(
            UserAccount.role == "system_admin", 
            UserAccount.is_active == True
        ).first()
        AUTH_SYSTEM_STATUS.set(1 if admin else 0)
    except Exception:
        AUTH_SYSTEM_STATUS.set(0)
    finally:
        db.close()
        
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

def setup_logging():
    """Configure structlog with PII masking."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            filter_log_record,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

def setup_instrumentation(app: FastAPI) -> None:
    """Attach middleware for Multi-Tenant metric tracking."""
    setup_logging()

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        tenant_id = "unknown"
        if "x-tenant-id" in request.headers:
            tenant_id = request.headers["x-tenant-id"]
        
        path = request.url.path
        
        try:
            response = await call_next(request)
            status = str(response.status_code)
        except Exception:
            status = "500"
            raise
        finally:
            duration = time.time() - start_time
            REQUEST_COUNT.labels(
                method=request.method, 
                endpoint=path, 
                status=status, 
                tenant_id=tenant_id
            ).inc()
            
            REQUEST_LATENCY.labels(
                method=request.method, 
                endpoint=path, 
                tenant_id=tenant_id
            ).observe(duration)
            
        return response

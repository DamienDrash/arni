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

from app.domains.campaigns.models import Campaign
from app.domains.identity.models import UserAccount
from app.integrations.pii_filter import filter_log_record
from app.shared.db import open_session

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

# --- Campaign Engine Metrics ---

CAMPAIGN_SEND_TOTAL = Counter(
    "ariia_campaign_emails_sent_total",
    "Total campaign emails sent by status and tenant",
    ["status", "channel", "tenant_id"],
)

CAMPAIGN_SEND_DURATION = Histogram(
    "ariia_campaign_send_duration_seconds",
    "Time to send a single campaign email",
    ["channel"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

CAMPAIGN_QUEUE_SIZE = Gauge(
    "ariia_campaign_send_queue_size",
    "Current number of messages in the send queue",
)

CAMPAIGN_DLQ_SIZE = Gauge(
    "ariia_campaign_dlq_size",
    "Current number of messages in the dead letter queue",
)

CAMPAIGN_SCHEDULER_RUNS = Counter(
    "ariia_campaign_scheduler_runs_total",
    "Total campaign scheduler job runs by type",
    ["job_type", "result"],
)

CAMPAIGN_ACTIVE_COUNT = Gauge(
    "ariia_campaigns_active",
    "Number of campaigns currently in sending/queued state",
    ["status"],
)


@router.get("/metrics")
def metrics():
    """Expose Prometheus metrics with synthetic checks."""
    db = open_session()
    try:
        # 1. Run synthetic auth check
        admin = db.query(UserAccount).filter(
            UserAccount.role == "system_admin",
            UserAccount.is_active == True
        ).first()
        AUTH_SYSTEM_STATUS.set(1 if admin else 0)

        # 2. Campaign queue metrics
        try:
            from app.campaign_engine.send_queue import get_queue_length, get_dlq_length
            CAMPAIGN_QUEUE_SIZE.set(max(get_queue_length(), 0))
            CAMPAIGN_DLQ_SIZE.set(max(get_dlq_length(), 0))
        except Exception:
            pass

        # 3. Active campaign counts
        try:
            for status in ["queued", "sending", "ab_testing", "scheduled"]:
                count = db.query(Campaign).filter(Campaign.status == status).count()
                CAMPAIGN_ACTIVE_COUNT.labels(status=status).set(count)
        except Exception:
            pass

    except Exception:
        AUTH_SYSTEM_STATUS.set(0)
    finally:
        db.close()

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/health/campaigns")
def campaign_health():
    """Dedicated health endpoint for the campaign subsystem."""
    health = {
        "status": "healthy",
        "components": {},
    }

    # Check Redis connectivity (send queue)
    try:
        from app.campaign_engine.send_queue import get_queue_length, get_dlq_length
        q_len = get_queue_length()
        dlq_len = get_dlq_length()
        health["components"]["redis"] = {
            "status": "healthy" if q_len >= 0 else "unhealthy",
            "send_queue_length": max(q_len, 0),
            "dlq_length": max(dlq_len, 0),
        }
        if q_len < 0:
            health["status"] = "degraded"
    except Exception as e:
        health["components"]["redis"] = {"status": "unhealthy", "error": str(e)}
        health["status"] = "degraded"

    # Check database connectivity
    try:
        db = open_session()
        active = db.query(Campaign).filter(
            Campaign.status.in_(["queued", "sending", "ab_testing"])
        ).count()
        scheduled = db.query(Campaign).filter(Campaign.status == "scheduled").count()
        health["components"]["database"] = {
            "status": "healthy",
            "active_campaigns": active,
            "scheduled_campaigns": scheduled,
        }
        db.close()
    except Exception as e:
        health["components"]["database"] = {"status": "unhealthy", "error": str(e)}
        health["status"] = "unhealthy"
    finally:
        try:
            db.close()
        except Exception:
            pass

    return health


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

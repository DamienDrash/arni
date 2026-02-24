"""ARIIA v1.4 – Instrumentation & Metrics.

@OPS: Sprint 7b, Task 7b.1
Exposes Prometheus metrics at /metrics.
"""

import time
import logging
import sys
from typing import Callable

import structlog
from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

from app.integrations.pii_filter import filter_log_record

def setup_logging():
    """Configure structlog with PII masking (Gold Standard)."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            filter_log_record, # PII MASKING (PR 2)
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

def setup_instrumentation(app: FastAPI) -> None:
    """Attach instrumentation middleware and /metrics endpoint."""
    setup_logging()

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Normalize endpoint (avoid high cardinality with IDs)
        # Simple heuristic: replace digits/UUIDs with {id} if needed, 
        # but for now we rely on simple path or route.path if available.
        # However, getting route.path in middleware is tricky.
        # We'll use request.url.path for now.
        path = request.url.path
        
        try:
            response = await call_next(request)
            status = str(response.status_code)
        except Exception:
            status = "500"
            raise
        finally:
            duration = time.time() - start_time
            REQUEST_COUNT.labels(method=request.method, endpoint=path, status=status).inc()
            REQUEST_LATENCY.labels(method=request.method, endpoint=path).observe(duration)
            
        return response

    @app.get("/metrics")
    def metrics():
        """Expose Prometheus metrics."""
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

"""ARIIA v1.4 – Instrumentation & Metrics.

@OPS: Sprint 7b, Task 7b.1
Exposes Prometheus metrics at /metrics.
"""

import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

# --- Metrics Definition ---

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
)

SWARM_MESSAGE_COUNT = Counter(
    "swarm_messages_total",
    "Total Swarm messages processed",
    ["agent", "status"],
)


def setup_instrumentation(app: FastAPI) -> None:
    """Attach instrumentation middleware and /metrics endpoint."""

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

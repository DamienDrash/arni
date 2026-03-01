"""app/core/telemetry.py — OpenTelemetry Instrumentation for ARIIA.

Complements the existing Langfuse-based observability (observability.py) with:
- Distributed tracing across all services (OpenTelemetry-compatible)
- Custom metrics (conversation latency, token usage, error rates)
- Span context propagation through agent orchestration
- Prometheus-compatible metrics export
- FastAPI middleware for automatic request tracing

The two systems work together:
- Langfuse (observability.py) → LLM-specific tracing, prompt analysis
- OpenTelemetry (telemetry.py) → Infrastructure tracing, metrics, SRE dashboards

Components:
    TracingManager          → Manages tracer and span creation
    MetricsCollector        → Custom Prometheus-compatible metrics
    ObservabilityMiddleware → FastAPI middleware for automatic request tracing
    trace_function          → Decorator for function-level tracing
"""
from __future__ import annotations

import time
import functools
import secrets
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import structlog

logger = structlog.get_logger()


# ══════════════════════════════════════════════════════════════════════════════
# SPAN & TRACE DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SpanContext:
    """Lightweight span context for distributed tracing."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    service_name: str = "ariia-core"
    operation_name: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    status: str = "OK"
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        end = self.end_time or time.time()
        return round((end - self.start_time) * 1000, 2)

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[dict] = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })

    def finish(self, status: str = "OK") -> None:
        self.end_time = time.time()
        self.status = status

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "service": self.service_name,
            "operation": self.operation_name,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
            "start_time": datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time, tz=timezone.utc).isoformat()
                if self.end_time else None,
        }


# ══════════════════════════════════════════════════════════════════════════════
# TRACING MANAGER
# ══════════════════════════════════════════════════════════════════════════════

class TracingManager:
    """Manages distributed tracing across ARIIA services.

    Creates and manages spans for request tracing, agent orchestration,
    tool execution, and LLM calls. Supports both OpenTelemetry export
    and local span collection for debugging.
    """

    def __init__(self, service_name: str = "ariia-core",
                 export_enabled: bool = False,
                 export_endpoint: Optional[str] = None):
        self.service_name = service_name
        self.export_enabled = export_enabled
        self.export_endpoint = export_endpoint
        self._active_spans: dict[str, SpanContext] = {}
        self._completed_spans: list[SpanContext] = []
        self._max_completed = 10_000
        self._otel_tracer = None

        if export_enabled:
            self._init_otel(export_endpoint)

    def _init_otel(self, endpoint: Optional[str]) -> None:
        """Initialize OpenTelemetry SDK if available."""
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.resources import Resource

            resource = Resource.create({"service.name": self.service_name})
            provider = TracerProvider(resource=resource)

            if endpoint:
                try:
                    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                    from opentelemetry.sdk.trace.export import BatchSpanProcessor
                    exporter = OTLPSpanExporter(endpoint=endpoint)
                    provider.add_span_processor(BatchSpanProcessor(exporter))
                except ImportError:
                    logger.warning("otel.otlp_exporter_not_available")

            trace.set_tracer_provider(provider)
            self._otel_tracer = trace.get_tracer(self.service_name)
            logger.info("otel.initialized", service=self.service_name, endpoint=endpoint)
        except ImportError:
            logger.info("otel.sdk_not_installed", message="Using lightweight tracing")

    def create_trace_id(self) -> str:
        """Create a new trace ID."""
        return secrets.token_hex(16)

    def start_span(self, operation_name: str,
                   trace_id: Optional[str] = None,
                   parent_span_id: Optional[str] = None,
                   attributes: Optional[dict] = None) -> SpanContext:
        """Start a new span."""
        span = SpanContext(
            trace_id=trace_id or self.create_trace_id(),
            span_id=secrets.token_hex(8),
            parent_span_id=parent_span_id,
            service_name=self.service_name,
            operation_name=operation_name,
            attributes=attributes or {},
        )

        self._active_spans[span.span_id] = span

        logger.debug("span.started",
                      trace_id=span.trace_id,
                      span_id=span.span_id,
                      operation=operation_name)
        return span

    def finish_span(self, span: SpanContext, status: str = "OK") -> None:
        """Finish a span and record it."""
        span.finish(status)
        self._active_spans.pop(span.span_id, None)
        self._completed_spans.append(span)

        # Limit memory
        if len(self._completed_spans) > self._max_completed:
            self._completed_spans = self._completed_spans[-self._max_completed // 2:]

        logger.debug("span.finished",
                      trace_id=span.trace_id,
                      span_id=span.span_id,
                      operation=span.operation_name,
                      duration_ms=span.duration_ms,
                      status=status)

    @contextmanager
    def span(self, operation_name: str,
             trace_id: Optional[str] = None,
             parent_span_id: Optional[str] = None,
             attributes: Optional[dict] = None):
        """Context manager for automatic span lifecycle."""
        s = self.start_span(operation_name, trace_id, parent_span_id, attributes)
        try:
            yield s
            self.finish_span(s, "OK")
        except Exception as e:
            s.set_attribute("error", True)
            s.set_attribute("error.message", str(e)[:500])
            s.set_attribute("error.type", type(e).__name__)
            self.finish_span(s, "ERROR")
            raise

    def get_trace(self, trace_id: str) -> list[dict]:
        """Get all spans for a trace ID."""
        spans = [s for s in self._completed_spans if s.trace_id == trace_id]
        spans.extend(s for s in self._active_spans.values() if s.trace_id == trace_id)
        return [s.to_dict() for s in sorted(spans, key=lambda x: x.start_time)]

    def get_active_spans(self) -> list[dict]:
        """Get all currently active spans."""
        return [s.to_dict() for s in self._active_spans.values()]

    def get_recent_traces(self, limit: int = 50) -> list[dict]:
        """Get recent completed traces grouped by trace_id."""
        trace_ids = set()
        traces = []
        for span in reversed(self._completed_spans):
            if span.trace_id not in trace_ids:
                trace_ids.add(span.trace_id)
                traces.append({
                    "trace_id": span.trace_id,
                    "root_operation": span.operation_name,
                    "duration_ms": span.duration_ms,
                    "status": span.status,
                    "span_count": sum(1 for s in self._completed_spans
                                     if s.trace_id == span.trace_id),
                })
                if len(traces) >= limit:
                    break
        return traces


# ══════════════════════════════════════════════════════════════════════════════
# METRICS COLLECTOR
# ══════════════════════════════════════════════════════════════════════════════

class MetricsCollector:
    """Collects and exposes custom metrics for monitoring.

    Tracks:
    - Request latency (histogram)
    - Conversation counts (counter)
    - Token usage (counter)
    - Error rates (counter)
    - Active connections (gauge)
    - LLM call latency (histogram)
    """

    def __init__(self):
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = defaultdict(float)
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._histogram_max_size = 10_000

    def _key(self, name: str, labels: Optional[dict] = None) -> str:
        """Create a metric key with labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    # --- Counters ---

    def increment(self, name: str, value: float = 1.0,
                  labels: Optional[dict] = None) -> None:
        """Increment a counter metric."""
        self._counters[self._key(name, labels)] += value

    def get_counter(self, name: str, labels: Optional[dict] = None) -> float:
        """Get current counter value."""
        return self._counters.get(self._key(name, labels), 0)

    # --- Gauges ---

    def set_gauge(self, name: str, value: float,
                  labels: Optional[dict] = None) -> None:
        """Set a gauge metric."""
        self._gauges[self._key(name, labels)] = value

    def get_gauge(self, name: str, labels: Optional[dict] = None) -> float:
        """Get current gauge value."""
        return self._gauges.get(self._key(name, labels), 0)

    # --- Histograms ---

    def observe(self, name: str, value: float,
                labels: Optional[dict] = None) -> None:
        """Record a histogram observation."""
        key = self._key(name, labels)
        self._histograms[key].append(value)

        # Limit memory
        if len(self._histograms[key]) > self._histogram_max_size:
            self._histograms[key] = self._histograms[key][-self._histogram_max_size // 2:]

    def get_histogram_stats(self, name: str,
                            labels: Optional[dict] = None) -> dict[str, float]:
        """Get histogram statistics (count, avg, p50, p95, p99)."""
        key = self._key(name, labels)
        values = self._histograms.get(key, [])
        if not values:
            return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0,
                    "p50": 0, "p95": 0, "p99": 0}

        sorted_vals = sorted(values)
        n = len(sorted_vals)

        return {
            "count": n,
            "sum": round(sum(sorted_vals), 2),
            "avg": round(sum(sorted_vals) / n, 2),
            "min": round(sorted_vals[0], 2),
            "max": round(sorted_vals[-1], 2),
            "p50": round(sorted_vals[int(n * 0.5)], 2),
            "p95": round(sorted_vals[min(int(n * 0.95), n - 1)], 2),
            "p99": round(sorted_vals[min(int(n * 0.99), n - 1)], 2),
        }

    # --- Export ---

    def get_all_metrics(self) -> dict[str, Any]:
        """Get all metrics in a structured format."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                k: self.get_histogram_stats(k)
                for k in self._histograms
            },
        }

    def to_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []

        for key, value in sorted(self._counters.items()):
            name = key.split("{")[0]
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{key} {value}")

        for key, value in sorted(self._gauges.items()):
            name = key.split("{")[0]
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{key} {value}")

        for key in sorted(self._histograms.keys()):
            name = key.split("{")[0]
            stats = self.get_histogram_stats(key)
            lines.append(f"# TYPE {name} summary")
            lines.append(f'{key}{{quantile="0.5"}} {stats["p50"]}')
            lines.append(f'{key}{{quantile="0.95"}} {stats["p95"]}')
            lines.append(f'{key}{{quantile="0.99"}} {stats["p99"]}')
            lines.append(f"{name}_count {stats['count']}")
            lines.append(f"{name}_sum {stats['sum']}")

        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()


# ══════════════════════════════════════════════════════════════════════════════
# OBSERVABILITY MIDDLEWARE (ASGI)
# ══════════════════════════════════════════════════════════════════════════════

class TelemetryMiddleware:
    """FastAPI/ASGI middleware for automatic request tracing and metrics.

    Automatically:
    - Creates a span for each HTTP request
    - Records request latency histogram
    - Tracks error rates by status code
    - Propagates trace context via X-Trace-Id / X-Span-Id headers
    - Adds trace ID to response headers for debugging
    """

    TRACE_HEADER = "X-Trace-Id"
    SPAN_HEADER = "X-Span-Id"

    def __init__(self, app, tracer: TracingManager, metrics: MetricsCollector,
                 excluded_paths: Optional[set[str]] = None):
        self.app = app
        self.tracer = tracer
        self.metrics = metrics
        self.excluded_paths = excluded_paths or {"/health", "/metrics", "/favicon.ico"}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in self.excluded_paths:
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        headers = dict(scope.get("headers", []))

        # Extract or create trace context from incoming headers
        trace_id = None
        parent_span_id = None
        for key, value in headers.items():
            if key == b"x-trace-id":
                trace_id = value.decode("utf-8", errors="ignore")
            elif key == b"x-span-id":
                parent_span_id = value.decode("utf-8", errors="ignore")

        span = self.tracer.start_span(
            operation_name=f"{method} {path}",
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            attributes={
                "http.method": method,
                "http.path": path,
                "http.scheme": scope.get("scheme", "http"),
            },
        )

        self.metrics.increment("http_requests_total", labels={"method": method, "path": path})
        self.metrics.set_gauge("http_active_requests",
                               self.metrics.get_gauge("http_active_requests") + 1)

        status_code = 500
        start_time = time.time()

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
                # Inject trace headers into response
                headers_list = list(message.get("headers", []))
                headers_list.append((b"x-trace-id", span.trace_id.encode()))
                headers_list.append((b"x-span-id", span.span_id.encode()))
                message = {**message, "headers": headers_list}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            status_code = 500
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e)[:500])
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            span.set_attribute("http.status_code", status_code)
            self.tracer.finish_span(span, "OK" if status_code < 400 else "ERROR")

            self.metrics.observe("http_request_duration_ms",
                                 duration_ms,
                                 labels={"method": method, "path": path})
            self.metrics.increment("http_responses_total",
                                   labels={"method": method, "status": str(status_code)})
            self.metrics.set_gauge("http_active_requests",
                                   max(0, self.metrics.get_gauge("http_active_requests") - 1))


# ══════════════════════════════════════════════════════════════════════════════
# DECORATOR FOR FUNCTION TRACING
# ══════════════════════════════════════════════════════════════════════════════

def trace_function(tracer: TracingManager, operation_name: Optional[str] = None):
    """Decorator to trace function execution with automatic span management.

    Usage:
        tracer = get_tracer()

        @trace_function(tracer, "my_operation")
        async def my_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        op_name = operation_name or f"{func.__module__}.{func.__qualname__}"

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with tracer.span(op_name) as span:
                span.set_attribute("function.name", func.__name__)
                result = await func(*args, **kwargs)
                return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with tracer.span(op_name) as span:
                span.set_attribute("function.name", func.__name__)
                result = func(*args, **kwargs)
                return result

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# ══════════════════════════════════════════════════════════════════════════════
# METRICS ENDPOINT ROUTER
# ══════════════════════════════════════════════════════════════════════════════

def create_metrics_router(tracer: TracingManager, metrics: MetricsCollector):
    """Create a FastAPI router for metrics and tracing endpoints.

    Endpoints:
        GET /metrics          → Prometheus-format metrics
        GET /metrics/json     → JSON-format metrics
        GET /traces/recent    → Recent traces
        GET /traces/{id}      → Specific trace detail
        GET /spans/active     → Currently active spans
    """
    from fastapi import APIRouter
    from fastapi.responses import PlainTextResponse

    router = APIRouter(tags=["observability"])

    @router.get("/metrics", response_class=PlainTextResponse)
    async def get_prometheus_metrics():
        """Export metrics in Prometheus text format."""
        return metrics.to_prometheus()

    @router.get("/metrics/json")
    async def get_json_metrics():
        """Export metrics in JSON format."""
        return metrics.get_all_metrics()

    @router.get("/traces/recent")
    async def get_recent_traces(limit: int = 50):
        """Get recent completed traces."""
        return {"traces": tracer.get_recent_traces(limit)}

    @router.get("/traces/{trace_id}")
    async def get_trace_detail(trace_id: str):
        """Get all spans for a specific trace."""
        spans = tracer.get_trace(trace_id)
        return {"trace_id": trace_id, "spans": spans, "span_count": len(spans)}

    @router.get("/spans/active")
    async def get_active_spans():
        """Get currently active spans."""
        spans = tracer.get_active_spans()
        return {"active_spans": spans, "count": len(spans)}

    return router


# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCES
# ══════════════════════════════════════════════════════════════════════════════

_tracer: Optional[TracingManager] = None
_metrics: Optional[MetricsCollector] = None


def get_tracer(service_name: str = "ariia-core",
               export_enabled: bool = False,
               export_endpoint: Optional[str] = None) -> TracingManager:
    """Get or create the global TracingManager singleton."""
    global _tracer
    if _tracer is None:
        _tracer = TracingManager(
            service_name=service_name,
            export_enabled=export_enabled,
            export_endpoint=export_endpoint,
        )
    return _tracer


def get_metrics() -> MetricsCollector:
    """Get or create the global MetricsCollector singleton."""
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics

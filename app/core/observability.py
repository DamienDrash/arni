"""app/core/observability.py — ARIIA Observability Service (K4).

Provides:
  - ObservabilityService singleton wrapping Langfuse
  - simple_trace(name) decorator for sync + async functions
  - Trace ID propagation via contextvars (no invasive signature changes)
  - Graceful no-op fallback when Langfuse keys are missing or library absent

Environment variables (set in .env or Docker-Compose):
  LANGFUSE_PUBLIC_KEY=pk-lf-...
  LANGFUSE_SECRET_KEY=sk-lf-...
  LANGFUSE_HOST=https://cloud.langfuse.com   (optional, default above)

Usage:
    from app.core.observability import simple_trace, new_trace_context

    # Start a top-level trace (e.g. per request)
    with new_trace_context(name="whatsapp_inbound", user_id="...", tenant_id="..."):
        result = await handle_message(...)

    # Decorate any handler to create a span under the active trace
    @simple_trace("handle_message")
    async def handle_message(...):
        ...
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Optional

import structlog

logger = structlog.get_logger()

# ── Langfuse import (graceful) ─────────────────────────────────────────────────
try:
    from langfuse import Langfuse
    from langfuse.model import StatefulTraceClient, StatefulSpanClient
    HAS_LANGFUSE = True
except ImportError:
    Langfuse = None  # type: ignore[misc,assignment]
    HAS_LANGFUSE = False

# ── Active trace propagation via contextvars ───────────────────────────────────
# Holds the current Langfuse trace object for the active request context.
# Each async task / coroutine chain shares this without explicit passing.
_active_trace: ContextVar[Any] = ContextVar("_active_trace", default=None)


# ── Singleton ──────────────────────────────────────────────────────────────────

class ObservabilityService:
    """Thread-safe Langfuse wrapper with graceful no-op fallback.

    Use ObservabilityService.get_instance() everywhere — do not instantiate
    directly. The singleton is initialised once at import time.
    """

    _instance: Optional["ObservabilityService"] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self.enabled = False
        self.client: Any = None

        if not HAS_LANGFUSE:
            logger.warning("observability.disabled", reason="langfuse_library_not_installed")
            return

        pk   = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
        sk   = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com").strip()

        if not (pk and sk):
            logger.warning("observability.disabled", reason="missing_langfuse_keys")
            return

        try:
            self.client = Langfuse(public_key=pk, secret_key=sk, host=host)
            self.enabled = True
            logger.info("observability.init.success", provider="langfuse", host=host)
        except Exception as exc:
            logger.error("observability.init.failed", error=str(exc))

    @classmethod
    def get_instance(cls) -> "ObservabilityService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── Trace creation ─────────────────────────────────────────────────────────

    def start_trace(
        self,
        name: str,
        user_id: str | None = None,
        tenant_id: str | int | None = None,
        metadata: dict[str, Any] | None = None,
        input: Any = None,
    ) -> Any:
        """Create a new top-level Langfuse trace and return it.

        Returns None and logs if Langfuse is disabled.
        """
        if not self.enabled or not self.client:
            return None
        try:
            return self.client.trace(
                name=name,
                user_id=str(user_id) if user_id else None,
                metadata={**(metadata or {}), "tenant_id": str(tenant_id) if tenant_id else None},
                input=input,
            )
        except Exception as exc:
            logger.warning("observability.trace_create_failed", name=name, error=str(exc))
            return None

    def create_span(
        self,
        name: str,
        trace: Any = None,
        input: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """Create a Langfuse span under the given trace (or active context trace)."""
        effective_trace = trace or _active_trace.get()
        if not self.enabled or not effective_trace:
            return None
        try:
            return effective_trace.span(name=name, input=input, metadata=metadata or {})
        except Exception as exc:
            logger.warning("observability.span_create_failed", name=name, error=str(exc))
            return None

    def end_span(
        self,
        span: Any,
        output: Any = None,
        error: Exception | None = None,
    ) -> None:
        if not span:
            return
        try:
            if error is not None:
                span.end(
                    output=str(error),
                    level="ERROR",
                    status_message=f"{type(error).__name__}: {error}",
                )
            else:
                span.end(output=output)
        except Exception as exc:
            logger.warning("observability.span_end_failed", error=str(exc))

    def log_llm_generation(
        self,
        trace: Any,
        name: str,
        model: str,
        prompt: str,
        completion: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an LLM generation event under the given trace."""
        if not self.enabled or not trace:
            return
        try:
            trace.generation(
                name=name,
                model=model,
                prompt=prompt,
                completion=completion,
                usage={"input": input_tokens, "output": output_tokens},
                metadata=metadata or {},
            )
        except Exception as exc:
            logger.warning("observability.generation_failed", name=name, error=str(exc))

    def flush(self) -> None:
        """Flush all pending traces to Langfuse. Call before process exit."""
        if self.enabled and self.client:
            try:
                self.client.flush()
            except Exception as exc:
                logger.warning("observability.flush_failed", error=str(exc))

    def trace(self, **kwargs: Any) -> Any:
        """Backward-compat alias for start_trace (used by older callers)."""
        return self.start_trace(**kwargs) if kwargs else None


# ── Public convenience functions ───────────────────────────────────────────────

def get_obs() -> ObservabilityService:
    """Return the shared ObservabilityService singleton."""
    return ObservabilityService.get_instance()


@contextmanager
def new_trace_context(
    name: str,
    user_id: str | None = None,
    tenant_id: str | int | None = None,
    metadata: dict[str, Any] | None = None,
    input: Any = None,
):
    """Sync context manager that creates a Langfuse trace and sets it as active.

    Example:
        with new_trace_context("whatsapp_inbound", user_id=uid, tenant_id=tid):
            await handle_message(...)
    """
    obs = get_obs()
    trace = obs.start_trace(name=name, user_id=user_id, tenant_id=tenant_id, metadata=metadata, input=input)
    token = _active_trace.set(trace)
    try:
        yield trace
    finally:
        _active_trace.reset(token)
        obs.flush()


@asynccontextmanager
async def async_trace_context(
    name: str,
    user_id: str | None = None,
    tenant_id: str | int | None = None,
    metadata: dict[str, Any] | None = None,
    input: Any = None,
):
    """Async context manager variant of new_trace_context."""
    obs = get_obs()
    trace = obs.start_trace(name=name, user_id=user_id, tenant_id=tenant_id, metadata=metadata, input=input)
    token = _active_trace.set(trace)
    try:
        yield trace
    finally:
        _active_trace.reset(token)


def simple_trace(name: str, log_args: bool = False):
    """Decorator that wraps sync or async functions with a Langfuse span.

    The span is created under the active trace from _active_trace context var.
    If no trace is active or Langfuse is disabled, the function runs unchanged.

    Args:
        name:     Span name shown in Langfuse UI (e.g. "swarm.route_message")
        log_args: If True, passes positional args as input to the span (use carefully for PII)

    Example:
        @simple_trace("swarm.intent_classify")
        async def classify(message: str) -> str:
            ...
    """
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                obs = get_obs()
                span_input = list(args) if log_args else None
                span = obs.create_span(name=name, input=span_input)
                t0 = time.monotonic()
                try:
                    result = await func(*args, **kwargs)
                    duration_ms = round((time.monotonic() - t0) * 1000)
                    obs.end_span(span, output=f"ok ({duration_ms}ms)")
                    return result
                except Exception as exc:
                    obs.end_span(span, error=exc)
                    raise
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                obs = get_obs()
                span_input = list(args) if log_args else None
                span = obs.create_span(name=name, input=span_input)
                t0 = time.monotonic()
                try:
                    result = func(*args, **kwargs)
                    duration_ms = round((time.monotonic() - t0) * 1000)
                    obs.end_span(span, output=f"ok ({duration_ms}ms)")
                    return result
                except Exception as exc:
                    obs.end_span(span, error=exc)
                    raise
            return sync_wrapper
    return decorator

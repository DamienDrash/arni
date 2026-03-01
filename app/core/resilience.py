"""ARIIA v2.0 – Resilience Layer (Circuit Breaker & Retry).

@ARCH: Phase 1, Meilenstein 1.3 – Asynchrone & Resiliente I/O
Provides a Circuit Breaker pattern and a resilient async HTTP client
for all external integrations (Magicline, WhatsApp, Telegram, etc.).

Circuit Breaker States:
- CLOSED: Normal operation, requests pass through.
- OPEN: Requests are immediately rejected (fail-fast).
- HALF_OPEN: A single probe request is allowed to test recovery.

Design:
- Each integration gets its own circuit breaker instance.
- State is stored in-memory (single instance) or Redis (multi-instance).
- Configurable thresholds per integration.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import httpx
import structlog

logger = structlog.get_logger()


# ─── Circuit Breaker ─────────────────────────────────────────────────────────


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker instance."""

    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes in half-open before closing
    timeout_seconds: float = 60.0  # Time in OPEN state before trying HALF_OPEN
    excluded_exceptions: tuple = ()  # Exceptions that don't count as failures


@dataclass
class CircuitBreaker:
    """Circuit breaker for protecting external service calls.

    Usage:
        cb = CircuitBreaker(name="magicline", config=CircuitBreakerConfig())

        async with cb:
            result = await external_api_call()
    """

    name: str
    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    last_state_change: float = field(default_factory=time.monotonic)

    def _transition(self, new_state: CircuitState) -> None:
        """Transition to a new state with logging."""
        old_state = self.state
        self.state = new_state
        self.last_state_change = time.monotonic()
        logger.info(
            "circuit_breaker.state_change",
            name=self.name,
            old_state=old_state.value,
            new_state=new_state.value,
            failure_count=self.failure_count,
        )

    def _record_success(self) -> None:
        """Record a successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.failure_count = 0
                self.success_count = 0
                self._transition(CircuitState.CLOSED)
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def _record_failure(self, error: Exception) -> None:
        """Record a failed call."""
        # Don't count excluded exceptions
        if isinstance(error, self.config.excluded_exceptions):
            return

        self.failure_count += 1
        self.last_failure_time = time.monotonic()

        if self.state == CircuitState.HALF_OPEN:
            # Any failure in half-open goes back to open
            self.success_count = 0
            self._transition(CircuitState.OPEN)
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self._transition(CircuitState.OPEN)

    def _should_allow_request(self) -> bool:
        """Determine if a request should be allowed through."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            elapsed = time.monotonic() - self.last_failure_time
            if elapsed >= self.config.timeout_seconds:
                self._transition(CircuitState.HALF_OPEN)
                return True
            return False

        # HALF_OPEN: allow one probe request
        return True

    def get_status(self) -> dict[str, Any]:
        """Return current circuit breaker status for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "last_state_change": self.last_state_change,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "timeout_seconds": self.config.timeout_seconds,
            },
        }

    async def __aenter__(self):
        if not self._should_allow_request():
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is OPEN. "
                f"Retry after {self.config.timeout_seconds}s."
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._record_success()
        elif exc_val is not None:
            self._record_failure(exc_val)
        return False  # Don't suppress the exception


class CircuitBreakerOpenError(Exception):
    """Raised when a circuit breaker is open and rejects a request."""

    pass


# ─── Circuit Breaker Registry ───────────────────────────────────────────────

_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None,
) -> CircuitBreaker:
    """Get or create a named circuit breaker.

    Args:
        name: Unique name for the circuit breaker (e.g., 'magicline', 'whatsapp').
        config: Optional configuration. Uses defaults if not provided.

    Returns:
        The circuit breaker instance.
    """
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(
            name=name,
            config=config or CircuitBreakerConfig(),
        )
    return _breakers[name]


def get_all_circuit_breakers() -> dict[str, CircuitBreaker]:
    """Get all registered circuit breakers (for monitoring)."""
    return dict(_breakers)


# ─── Resilient HTTP Client ──────────────────────────────────────────────────


class ResilientHTTPClient:
    """Async HTTP client with circuit breaker, retry, and timeout support.

    Wraps httpx.AsyncClient with enterprise-grade resilience patterns.
    Replaces the synchronous `requests` library used in the old codebase.

    Usage:
        client = ResilientHTTPClient(
            base_url="https://api.magicline.com",
            circuit_breaker_name="magicline",
        )
        response = await client.get("/v1/customers", params={"limit": 10})
    """

    def __init__(
        self,
        base_url: str = "",
        circuit_breaker_name: str = "default",
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
        headers: Optional[dict[str, str]] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self._cb = get_circuit_breaker(circuit_breaker_name, circuit_breaker_config)
        self._default_headers = headers or {}

        # Shared httpx client (connection pooling)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the underlying httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                headers=self._default_headers,
                follow_redirects=True,
                limits=httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=20,
                    keepalive_expiry=30,
                ),
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
        data: Optional[dict] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> httpx.Response:
        """Make a resilient HTTP request with circuit breaker and retry.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.).
            path: URL path (appended to base_url).
            params: Query parameters.
            json: JSON body.
            data: Form data.
            headers: Additional headers.
            timeout: Override default timeout.

        Returns:
            httpx.Response object.

        Raises:
            CircuitBreakerOpenError: If the circuit breaker is open.
            httpx.HTTPError: If all retries are exhausted.
        """
        client = await self._get_client()
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                async with self._cb:
                    response = await client.request(
                        method,
                        path,
                        params=params,
                        json=json,
                        data=data,
                        headers=headers,
                        timeout=timeout or self.timeout,
                    )

                    # Treat 5xx as failures for circuit breaker
                    if response.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            f"Server error: {response.status_code}",
                            request=response.request,
                            response=response,
                        )

                    return response

            except CircuitBreakerOpenError:
                raise  # Don't retry when circuit is open

            except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
                last_error = e
                if attempt < self.max_retries:
                    wait = self.retry_backoff * (2 ** (attempt - 1))
                    logger.warning(
                        "resilient_http.retry",
                        attempt=attempt,
                        max_retries=self.max_retries,
                        wait_seconds=wait,
                        error=str(e),
                        path=path,
                    )
                    await asyncio.sleep(wait)

            except Exception as e:
                last_error = e
                logger.error(
                    "resilient_http.unexpected_error",
                    error=str(e),
                    path=path,
                    attempt=attempt,
                )
                break  # Don't retry unexpected errors

        raise last_error or httpx.HTTPError(f"Request failed after {self.max_retries} retries")

    # ─── Convenience Methods ─────────────────────────────────────────────

    async def get(self, path: str, **kwargs) -> httpx.Response:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs) -> httpx.Response:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs) -> httpx.Response:
        return await self.request("PUT", path, **kwargs)

    async def patch(self, path: str, **kwargs) -> httpx.Response:
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs) -> httpx.Response:
        return await self.request("DELETE", path, **kwargs)

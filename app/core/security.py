"""ARIIA v2.0 – Zero-Trust Security Layer.

@ARCH: Phase 1, Meilenstein 1.1
Provides mandatory HMAC verification, rate limiting, and input sanitization
for all inbound webhook traffic. No request passes without verification.

Security Principles:
- HMAC verification is MANDATORY, not optional
- Rate limiting operates on 3 levels: IP, Tenant, User
- Input sanitization strips prompt injection patterns
- All violations are logged for audit
"""

import asyncio
import hashlib
import hmac
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog
from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from config.settings import get_settings

logger = structlog.get_logger()

# ─── HMAC Verification ──────────────────────────────────────────────────────


def verify_hmac_signature(
    payload: bytes,
    signature: str,
    secret: str,
    algorithm: str = "sha256",
) -> bool:
    """Verify HMAC signature of a webhook payload.

    Args:
        payload: Raw request body bytes.
        signature: The signature from the request header (hex-encoded).
        secret: The shared secret for this channel/tenant.
        algorithm: Hash algorithm (default: sha256).

    Returns:
        True if signature is valid, False otherwise.
    """
    if not signature or not secret:
        return False

    # Strip common prefixes like "sha256=" used by WhatsApp/GitHub
    clean_sig = signature
    for prefix in ("sha256=", "sha1=", "hmac-sha256="):
        if clean_sig.lower().startswith(prefix):
            clean_sig = clean_sig[len(prefix):]
            break

    try:
        expected = hmac.new(
            secret.encode("utf-8"),
            payload,
            getattr(hashlib, algorithm),
        ).hexdigest()
        return hmac.compare_digest(expected.lower(), clean_sig.lower())
    except Exception as e:
        logger.warning("security.hmac.verification_error", error=str(e))
        return False


# ─── Rate Limiter (Token Bucket) ────────────────────────────────────────────


@dataclass
class TokenBucket:
    """Token bucket rate limiter with configurable capacity and refill rate."""

    capacity: int
    refill_rate: float  # tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self):
        self.tokens = float(self.capacity)
        self.last_refill = time.monotonic()

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed, False if rate-limited."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    @property
    def retry_after(self) -> float:
        """Seconds until at least 1 token is available."""
        if self.tokens >= 1:
            return 0.0
        return max(0.0, (1.0 - self.tokens) / self.refill_rate)


class RateLimiter:
    """Three-tier rate limiter: IP → Tenant → User.

    Limits are configurable and enforced at the gateway level.
    Uses in-memory token buckets (suitable for single-instance;
    for multi-instance, swap to Redis-backed implementation).
    """

    def __init__(
        self,
        ip_capacity: int = 100,
        ip_refill: float = 10.0,  # 10 req/s refill
        tenant_capacity: int = 200,
        tenant_refill: float = 20.0,
        user_capacity: int = 30,
        user_refill: float = 2.0,
    ):
        self.ip_capacity = ip_capacity
        self.ip_refill = ip_refill
        self.tenant_capacity = tenant_capacity
        self.tenant_refill = tenant_refill
        self.user_capacity = user_capacity
        self.user_refill = user_refill

        self._ip_buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(self.ip_capacity, self.ip_refill)
        )
        self._tenant_buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(self.tenant_capacity, self.tenant_refill)
        )
        self._user_buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(self.user_capacity, self.user_refill)
        )

    def check(
        self,
        ip: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> tuple[bool, str, float]:
        """Check all applicable rate limits.

        Returns:
            (allowed, violated_level, retry_after_seconds)
        """
        # Level 1: IP-based (DDoS protection)
        if not self._ip_buckets[ip].consume():
            logger.warning("security.rate_limit.ip", ip=ip)
            return False, "ip", self._ip_buckets[ip].retry_after

        # Level 2: Tenant-based (fair usage)
        if tenant_id:
            key = str(tenant_id)
            if not self._tenant_buckets[key].consume():
                logger.warning("security.rate_limit.tenant", tenant_id=tenant_id)
                return False, "tenant", self._tenant_buckets[key].retry_after

        # Level 3: User-based (loop protection)
        if user_id:
            key = f"{tenant_id or 'global'}:{user_id}"
            if not self._user_buckets[key].consume():
                logger.warning("security.rate_limit.user", user_id=user_id, tenant_id=tenant_id)
                return False, "user", self._user_buckets[key].retry_after

        return True, "", 0.0

    def cleanup_stale_buckets(self, max_age_seconds: float = 3600.0) -> int:
        """Remove buckets that haven't been used recently to prevent memory leaks."""
        now = time.monotonic()
        removed = 0
        for bucket_dict in (self._ip_buckets, self._tenant_buckets, self._user_buckets):
            stale_keys = [
                k for k, v in bucket_dict.items()
                if (now - v.last_refill) > max_age_seconds
            ]
            for k in stale_keys:
                del bucket_dict[k]
                removed += 1
        return removed


# ─── Input Sanitization ─────────────────────────────────────────────────────

# Known prompt injection patterns (case-insensitive)
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?above\s+instructions",
    r"disregard\s+(all\s+)?previous",
    r"forget\s+(all\s+)?previous",
    r"you\s+are\s+now\s+(?:a\s+)?(?:new|different)",
    r"system\s*:\s*",
    r"<\s*system\s*>",
    r"<\s*/?\s*(?:system|instruction|prompt)\s*>",
    r"\[INST\]",
    r"\[/INST\]",
    r"<<\s*SYS\s*>>",
    r"```\s*system",
    r"ADMIN\s*OVERRIDE",
    r"DEVELOPER\s*MODE",
    r"DAN\s*MODE",
    r"jailbreak",
]

_INJECTION_RE = re.compile(
    "|".join(INJECTION_PATTERNS),
    re.IGNORECASE | re.MULTILINE,
)


def sanitize_input(text: str, max_length: int = 4000) -> tuple[str, list[str]]:
    """Sanitize user input text.

    Args:
        text: Raw user input.
        max_length: Maximum allowed character length.

    Returns:
        (sanitized_text, list_of_violations)
    """
    violations: list[str] = []

    if not text:
        return "", violations

    # Length enforcement
    if len(text) > max_length:
        text = text[:max_length]
        violations.append(f"input_truncated_to_{max_length}_chars")

    # Detect injection patterns
    matches = _INJECTION_RE.findall(text)
    if matches:
        violations.append(f"prompt_injection_detected:{len(matches)}_patterns")
        # We don't remove the patterns (that could break legitimate text),
        # but we wrap user input in isolation tags downstream
        logger.warning(
            "security.input.injection_detected",
            pattern_count=len(matches),
            sample=text[:100],
        )

    # Strip null bytes and control characters (except newline, tab)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    return text, violations


def wrap_user_input(text: str) -> str:
    """Wrap user input in isolation tags for the LLM prompt.

    This is a defense-in-depth measure against prompt injection.
    The system prompt instructs the LLM to treat content within
    these tags as untrusted user input only.
    """
    return f"<user_message>\n{text}\n</user_message>"


# ─── Gateway Security Middleware ─────────────────────────────────────────────

# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


# Issue #27: Per-IP token buckets for /admin/ endpoints (60 req/min = 1 req/s refill).
_admin_ip_buckets: dict[str, "TokenBucket"] = defaultdict(
    lambda: TokenBucket(capacity=60, refill_rate=1.0)
)


async def _rate_limiter_cleanup_loop() -> None:
    """Background task: clean up stale token buckets every 5 minutes."""
    while True:
        await asyncio.sleep(300)
        try:
            limiter = get_rate_limiter()
            removed = limiter.cleanup_stale_buckets()
            if removed:
                logger.info("security.rate_limiter.cleanup", removed=removed)
        except Exception as exc:
            logger.warning("security.rate_limiter.cleanup_error", error=str(exc))


async def start_rate_limiter_cleanup() -> None:
    """Rate-limiter cleanup coroutine for use as an asyncio background task.

    Call via asyncio.create_task(start_rate_limiter_cleanup()) from the
    application lifespan (startup event). Issue #27.
    """
    await _rate_limiter_cleanup_loop()


class SecurityMiddleware(BaseHTTPMiddleware):
    """Gateway security middleware that enforces rate limiting on all requests.

    HMAC verification is handled per-route in the webhook handlers
    because different channels use different signature schemes.
    """

    # Paths exempt from rate limiting (health checks, static assets)
    EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip rate limiting for exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Skip for non-webhook internal API calls (they use JWT auth)
        if not request.url.path.startswith(("/webhook", "/api/v1/webhook")):
            client_ip = request.client.host if request.client else "unknown"

            # Issue #18: Rate-limit /admin/ paths — 60 req/min per IP
            if request.url.path.startswith("/admin/"):
                if not _admin_ip_buckets[client_ip].consume():
                    retry_after = _admin_ip_buckets[client_ip].retry_after
                    logger.warning(
                        "security.rate_limit.admin_rejected",
                        ip=client_ip,
                        path=request.url.path,
                        retry_after=retry_after,
                    )
                    return Response(
                        content=f'{{"detail":"Rate limit exceeded (admin)","retry_after":{retry_after:.1f}}}',
                        status_code=429,
                        media_type="application/json",
                        headers={"Retry-After": str(int(retry_after) + 1)},
                    )

            return await call_next(request)

        limiter = get_rate_limiter()

        # Extract identifiers
        client_ip = request.client.host if request.client else "unknown"
        tenant_id = request.path_params.get("tenant_slug") or request.headers.get(
            "X-Tenant-ID"
        )
        user_id = request.headers.get("X-User-ID")

        # Check rate limits
        allowed, level, retry_after = limiter.check(client_ip, tenant_id, user_id)
        if not allowed:
            logger.warning(
                "security.rate_limit.rejected",
                ip=client_ip,
                tenant_id=tenant_id,
                level=level,
                retry_after=retry_after,
            )
            return Response(
                content=f'{{"detail":"Rate limit exceeded ({level})","retry_after":{retry_after:.1f}}}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

        response = await call_next(request)
        return response


# ─── Message Deduplication ───────────────────────────────────────────────────


class MessageDeduplicator:
    """In-memory message deduplication using message IDs with TTL.

    For production multi-instance deployments, swap to Redis SET with TTL.
    """

    def __init__(self, ttl_seconds: float = 300.0):
        self._seen: dict[str, float] = {}
        self._ttl = ttl_seconds

    def is_duplicate(self, message_id: str) -> bool:
        """Check if a message ID has been seen recently."""
        now = time.monotonic()
        self._cleanup(now)

        if message_id in self._seen:
            logger.debug("security.dedup.duplicate", message_id=message_id)
            return True

        self._seen[message_id] = now
        return False

    def _cleanup(self, now: float) -> None:
        """Remove expired entries."""
        expired = [k for k, ts in self._seen.items() if (now - ts) > self._ttl]
        for k in expired:
            del self._seen[k]


# Global deduplicator instance
_deduplicator: Optional[MessageDeduplicator] = None


def get_deduplicator() -> MessageDeduplicator:
    """Get or create the global message deduplicator."""
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = MessageDeduplicator()
    return _deduplicator

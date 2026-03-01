"""ARIIA v2.0 – Tenant-scoped Redis key factory.

@ARCH: Phase 1, Meilenstein 1.2 – Strikte Datenisolation
All Redis keys MUST go through this module to ensure tenant isolation.
No key may be stored without a tenant prefix.

Key schema:
    t{tenant_id}:{domain}:{identifier}

Examples:
    t7:token:123456
    t7:user_token:+4915112345678
    t7:human_mode:+4915112345678
    t7:dialog:+4915112345678
    t7:blacklist:jti:{jti}
    t7:user_blacklisted:{user_id}
    t7:rate_limit:user:+4915112345678
    t7:session:cache:{session_id}
    t7:usage:{year}:{month}
    t7:circuit_breaker:{integration_name}
"""

from __future__ import annotations

from typing import Optional


def redis_key(tenant_id: int | str, *parts: str) -> str:
    """Build a tenant-scoped Redis key.

    Args:
        tenant_id: Numeric tenant ID. Will be prefixed as 't{id}'.
        *parts:    Key path segments joined with ':'.

    Returns:
        Fully-qualified key string like 't7:token:123456'.

    Raises:
        ValueError: If no path parts are provided or tenant_id is invalid.
    """
    if not parts:
        raise ValueError("redis_key requires at least one path part")
    if tenant_id is None:
        raise ValueError("redis_key requires a valid tenant_id (got None)")
    return f"t{tenant_id}:" + ":".join(str(p) for p in parts)


# ─── Authentication Keys ────────────────────────────────────────────────────


def token_key(tenant_id: int | str, token: str) -> str:
    """Verification token storage."""
    return redis_key(tenant_id, "token", token)


def user_token_key(tenant_id: int | str, user_id: str) -> str:
    """User-to-token mapping."""
    return redis_key(tenant_id, "user_token", user_id)


def jti_blacklist_key(tenant_id: int | str, jti: str) -> str:
    """JWT ID blacklist for token revocation."""
    return redis_key(tenant_id, "blacklist", "jti", jti)


def user_blacklisted_key(tenant_id: int | str, user_id: int | str) -> str:
    """Blacklisted user flag."""
    return redis_key(tenant_id, "user_blacklisted", str(user_id))


# ─── Conversation State Keys ────────────────────────────────────────────────


def human_mode_key(tenant_id: int | str, user_id: str) -> str:
    """Human handoff mode flag for a user."""
    return redis_key(tenant_id, "human_mode", user_id)


def dialog_context_key(tenant_id: int | str, user_id: str) -> str:
    """Active dialog context for a user."""
    return redis_key(tenant_id, "dialog", user_id)


def session_cache_key(tenant_id: int | str, session_id: str) -> str:
    """Cached session data for fast lookup."""
    return redis_key(tenant_id, "session", "cache", session_id)


def conversation_lock_key(tenant_id: int | str, user_id: str) -> str:
    """Distributed lock for concurrent message handling per user."""
    return redis_key(tenant_id, "lock", "conversation", user_id)


# ─── Rate Limiting Keys ─────────────────────────────────────────────────────


def rate_limit_key(tenant_id: int | str, level: str, identifier: str) -> str:
    """Rate limit counter. Level: 'ip', 'tenant', 'user'."""
    return redis_key(tenant_id, "rate_limit", level, identifier)


# ─── Usage & Metering Keys ──────────────────────────────────────────────────


def usage_counter_key(tenant_id: int | str, year: int, month: int) -> str:
    """Monthly usage counter (messages, tokens, etc.)."""
    return redis_key(tenant_id, "usage", str(year), str(month))


def usage_field_key(tenant_id: int | str, field: str) -> str:
    """Individual usage field for atomic increments."""
    return redis_key(tenant_id, "usage", "current", field)


# ─── Circuit Breaker Keys ───────────────────────────────────────────────────


def circuit_breaker_key(tenant_id: int | str, integration: str) -> str:
    """Circuit breaker state for an external integration."""
    return redis_key(tenant_id, "circuit_breaker", integration)


def circuit_breaker_failure_key(tenant_id: int | str, integration: str) -> str:
    """Failure counter for circuit breaker decisions."""
    return redis_key(tenant_id, "circuit_breaker", integration, "failures")


# ─── Message Deduplication Keys ──────────────────────────────────────────────


def message_dedup_key(tenant_id: int | str, message_id: str) -> str:
    """Message deduplication (idempotency)."""
    return redis_key(tenant_id, "dedup", message_id)


# ─── Integration Cache Keys ─────────────────────────────────────────────────


def integration_cache_key(
    tenant_id: int | str, integration: str, resource: str, identifier: str = ""
) -> str:
    """Cached integration response data."""
    parts = ["cache", integration, resource]
    if identifier:
        parts.append(identifier)
    return redis_key(tenant_id, *parts)


# ─── Context-Aware Helpers ───────────────────────────────────────────────────


def redis_key_from_context(*parts: str) -> str:
    """Build a Redis key using the current TenantContext.

    Convenience function that reads tenant_id from the active context.
    Use this in code that already has a TenantContext set.

    Raises:
        RuntimeError: If no TenantContext is set.
    """
    from app.core.tenant_context import get_current_tenant_id

    return redis_key(get_current_tenant_id(), *parts)

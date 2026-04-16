"""ARIIA v2.0 – Tenant Context Manager.

@ARCH: Phase 1, Meilenstein 1.2 – Strikte Datenisolation
Provides a request-scoped TenantContext that propagates tenant_id
through the entire processing pipeline. Every database query, Redis
operation, and vector store access MUST go through this context.

Design Principles:
- TenantContext is set ONCE at the gateway boundary
- It propagates via Python contextvars (async-safe)
- All downstream code reads from the context, never from request params
- Missing context in production = hard error (fail-closed)
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog
from sqlalchemy import text

from app.domains.billing.models import Plan, Subscription
from app.domains.identity.models import Tenant
from app.shared.db import open_session

logger = structlog.get_logger()

# ─── Context Variable ────────────────────────────────────────────────────────

_tenant_ctx: contextvars.ContextVar[Optional["TenantContext"]] = contextvars.ContextVar(
    "tenant_context", default=None
)


@dataclass(frozen=True)
class TenantContext:
    """Immutable tenant context for the current request scope.

    Attributes:
        tenant_id: Numeric tenant identifier (from DB).
        tenant_slug: URL-safe tenant slug.
        plan_slug: Current plan slug (for feature gating).
        user_id: Platform-specific user ID (if available).
        channel: Inbound channel (whatsapp, telegram, etc.).
        trace_id: Distributed tracing ID for observability.
        metadata: Additional context data (e.g., from webhook).
    """

    tenant_id: int
    tenant_slug: str = ""
    plan_slug: str = "starter"
    user_id: str = ""
    channel: str = ""
    trace_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def redis_prefix(self) -> str:
        """Redis key prefix for this tenant."""
        return f"t{self.tenant_id}"

    @property
    def vector_namespace(self) -> str:
        """Vector DB namespace for this tenant."""
        if self.tenant_slug:
            return f"ariia_tenant_{self.tenant_slug}"
        return f"ariia_tenant_{self.tenant_id}"

    @property
    def kb_collection(self) -> str:
        """Knowledge base collection name for this tenant."""
        if self.tenant_slug:
            return f"ariia_tenant_{self.tenant_slug}_kb"
        return f"ariia_tenant_{self.tenant_id}_kb"

    @property
    def user_memory_collection(self) -> str:
        """User memory collection name for this tenant."""
        if self.tenant_slug:
            return f"ariia_tenant_{self.tenant_slug}_user_memory"
        return f"ariia_tenant_{self.tenant_id}_user_memory"


# ─── Context Access Functions ────────────────────────────────────────────────


def set_tenant_context(ctx: TenantContext) -> contextvars.Token:
    """Set the tenant context for the current async scope.

    Returns a token that can be used to reset the context.
    """
    logger.debug(
        "tenant_context.set",
        tenant_id=ctx.tenant_id,
        tenant_slug=ctx.tenant_slug,
        channel=ctx.channel,
    )
    return _tenant_ctx.set(ctx)


def get_tenant_context() -> TenantContext:
    """Get the current tenant context.

    Raises:
        RuntimeError: If no tenant context is set (fail-closed).
    """
    ctx = _tenant_ctx.get()
    if ctx is None:
        raise RuntimeError(
            "TenantContext not set. This indicates a bug: "
            "every request must pass through the tenant resolution middleware."
        )
    return ctx


def get_tenant_context_or_none() -> Optional[TenantContext]:
    """Get the current tenant context, or None if not set.

    Use this only in code paths that legitimately run without
    tenant context (e.g., platform admin endpoints, health checks).
    """
    return _tenant_ctx.get()


def get_current_tenant_id() -> int:
    """Convenience: get just the tenant_id from the current context."""
    return get_tenant_context().tenant_id


def reset_tenant_context(token: contextvars.Token) -> None:
    """Reset the tenant context to its previous value."""
    _tenant_ctx.reset(token)


@contextmanager
def tenant_scope(ctx: TenantContext):
    """Context manager for setting tenant context in a scope.

    Usage:
        with tenant_scope(TenantContext(tenant_id=7, tenant_slug="demo")):
            # All code here sees tenant_id=7
            do_stuff()
    """
    token = set_tenant_context(ctx)
    try:
        yield ctx
    finally:
        reset_tenant_context(token)


# ─── Database Integration ────────────────────────────────────────────────────


def get_db_with_tenant():
    """FastAPI dependency that provides a DB session with tenant context set.

    The tenant_id is propagated to PostgreSQL via SET LOCAL for RLS policies.
    """
    from app.core.db import tenant_context as db_tenant_var

    ctx = get_tenant_context_or_none()
    if ctx:
        db_tenant_var.set(ctx.tenant_id)

    db = open_session()
    try:
        if ctx:
            # Set PostgreSQL session variable for RLS
            db.execute(text(f"SET LOCAL app.current_tenant_id = '{ctx.tenant_id}'"))
        yield db
    finally:
        db.close()
        if ctx:
            db_tenant_var.set(None)


# ─── Middleware Helper ───────────────────────────────────────────────────────


def resolve_tenant_from_slug(slug: str) -> Optional[TenantContext]:
    """Resolve a tenant slug to a full TenantContext.

    Queries the database for the tenant and builds the context.
    Returns None if the tenant is not found or inactive.
    """
    if not slug:
        return None

    db = open_session()
    try:
        tenant = db.query(Tenant).filter(
            Tenant.slug == slug.strip().lower(),
            Tenant.is_active.is_(True),
        ).first()
        if not tenant:
            return None

        # Try to load plan slug
        plan_slug = "starter"
        try:
            sub = db.query(Subscription).filter(
                Subscription.tenant_id == tenant.id,
                Subscription.status.in_(["active", "trialing"]),
            ).first()
            if sub:
                plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()
                if plan:
                    plan_slug = plan.slug
        except Exception:
            pass  # Plan resolution is best-effort

        return TenantContext(
            tenant_id=tenant.id,
            tenant_slug=tenant.slug,
            plan_slug=plan_slug,
        )
    finally:
        db.close()

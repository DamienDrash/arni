from __future__ import annotations

import json as _json
from typing import Any

import structlog

from app.core.auth import AuthContext, require_role
from app.gateway.admin_shared_repository import admin_shared_repository
from app.gateway.persistence import persistence
from app.shared.db import session_scope, transaction_scope
from config.settings import get_settings

logger = structlog.get_logger()
REDACTED_SECRET_VALUE = "__REDACTED__"
settings = get_settings()
SENSITIVE_SETTING_KEYS = {
    "auth_secret",
    "acp_secret",
    "telegram_bot_token",
    "telegram_webhook_secret",
    "meta_access_token",
    "meta_app_secret",
    "magicline_api_key",
    "smtp_username",
    "smtp_password",
    "postmark_server_token",
    "postmark_inbound_token",
    "twilio_auth_token",
    "credentials_encryption_key",
    "openai_api_key",
    "bridge_auth_dir",
    "billing_stripe_secret_key",
    "billing_stripe_webhook_secret",
}


def require_system_admin(user: AuthContext) -> None:
    require_role(user, {"system_admin"})


def require_tenant_admin_or_system(user: AuthContext) -> None:
    require_role(user, {"system_admin", "tenant_admin"})


def safe_tenant_slug(user: AuthContext) -> str:
    raw = (user.tenant_slug or "system").strip().lower()
    cleaned = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "-" for ch in raw)
    cleaned = cleaned.strip("-_")
    return cleaned or "system"


def resolve_tenant_id_for_slug(user: AuthContext, tenant_slug_param: str | None) -> int | None:
    if user.role != "system_admin" or not tenant_slug_param:
        return user.tenant_id

    raw = tenant_slug_param.strip().lower()
    safe = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "-" for ch in raw)
    safe = safe.strip("-_") or "system"
    if safe == safe_tenant_slug(user):
        return user.tenant_id

    with session_scope() as db:
        tenant = admin_shared_repository.get_tenant_by_slug(db, tenant_slug=safe)
        return tenant.id if tenant else user.tenant_id


def is_sensitive_key(key: str) -> bool:
    normalized = (key or "").strip().lower()
    if normalized in SENSITIVE_SETTING_KEYS:
        return True
    return any(token in normalized for token in ("password", "secret", "token", "api_key", "apikey"))


def mask_if_sensitive(key: str, value: str | None) -> str | None:
    if value is None:
        return None
    if is_sensitive_key(key) and value != "":
        return REDACTED_SECRET_VALUE
    return value


def get_setting_with_env_fallback(
    key: str,
    env_attr: str | None = None,
    default: str = "",
    tenant_id: int | None = None,
) -> str:
    # Never fall back to system-tenant settings when a specific tenant is requested.
    value = persistence.get_setting(key, None, tenant_id=tenant_id, fallback_to_system=False)
    if value is not None:
        return value
    if env_attr and tenant_id is None:
        return str(getattr(settings, env_attr, default) or default)
    return default


def write_admin_audit(
    *,
    actor: AuthContext | None,
    action: str,
    category: str,
    target_type: str | None = None,
    target_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    try:
        actor_user_id = actor.user_id if actor else None
        actor_email = actor.email if actor else None
        actor_tenant_id = actor.tenant_id if actor else None
        if actor and getattr(actor, "is_impersonating", False):
            actor_user_id = getattr(actor, "impersonator_user_id", actor_user_id)
            actor_email = getattr(actor, "impersonator_email", actor_email)
            actor_tenant_id = getattr(actor, "impersonator_tenant_id", actor_tenant_id)
        with transaction_scope() as db:
            admin_shared_repository.add_audit_log(
                db,
                actor_user_id=actor_user_id,
                actor_email=actor_email,
                tenant_id=actor_tenant_id,
                action=action,
                category=category,
                target_type=target_type,
                target_id=target_id,
                details_json=_json.dumps(details or {}, ensure_ascii=False),
            )
    except Exception as exc:
        logger.error("admin.audit_write_failed", action=action, error=str(exc))

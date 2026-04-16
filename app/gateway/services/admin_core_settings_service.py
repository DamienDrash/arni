from __future__ import annotations

from typing import Any

from app.core.auth import AuthContext
from app.gateway.admin_shared import (
    REDACTED_SECRET_VALUE,
    is_sensitive_key,
    mask_if_sensitive,
    write_admin_audit,
)
from app.gateway.persistence import persistence
from app.shared.db import session_scope


class AdminCoreSettingsService:
    def get_all_settings(self, user: AuthContext) -> list[dict[str, Any]]:
        settings = persistence.get_settings(tenant_id=user.tenant_id)
        return [
            {
                "key": setting.key,
                "value": mask_if_sensitive(setting.key, setting.value),
                "description": setting.description,
                "tenant_id": setting.tenant_id,
            }
            for setting in settings
        ]

    def update_settings_batch(self, user: AuthContext, body: list[dict[str, Any]]) -> dict[str, str]:
        updated_keys: list[str] = []
        for entry in body:
            key = entry.get("key")
            value = entry.get("value")
            desc = entry.get("description")
            if key:
                persistence.upsert_setting(key, str(value), desc, tenant_id=user.tenant_id)
                updated_keys.append(key)

        if updated_keys:
            write_admin_audit(
                actor=user,
                action="settings.batch_update",
                category="settings",
                target_type="system_config",
                target_id="batch",
                details={
                    "keys_count": len(updated_keys),
                    "keys": updated_keys,
                    "msg": "AI Engine or Platform settings updated via infrastructure manager.",
                },
            )

        return {"status": "ok", "count": str(len(body))}

    def update_setting(self, user: AuthContext, key: str, value: str, description: str | None = None) -> dict[str, str]:
        current_value = persistence.get_setting(key, "", tenant_id=user.tenant_id)
        next_value = value
        if is_sensitive_key(key) and value == REDACTED_SECRET_VALUE:
            existing = persistence.get_setting(key, None, tenant_id=user.tenant_id)
            if existing is not None:
                next_value = existing

        persistence.upsert_setting(key, next_value, description, tenant_id=user.tenant_id)
        write_admin_audit(
            actor=user,
            action="setting.update",
            category="settings",
            target_type="setting",
            target_id=key,
            details={
                "key": key,
                "reason": (description or "").strip(),
                "sensitive": is_sensitive_key(key),
                "previous_value": REDACTED_SECRET_VALUE if is_sensitive_key(key) and current_value else current_value,
                "next_value": REDACTED_SECRET_VALUE if is_sensitive_key(key) and next_value else next_value,
            },
        )
        return {"status": "ok", "key": key, "value": mask_if_sensitive(key, next_value) or ""}

    def get_tenant_preferences(self, user: AuthContext) -> dict[str, str]:
        display_name = persistence.get_setting("tenant_display_name", None, tenant_id=user.tenant_id) or ""
        if not display_name:
            from app.domains.identity.models import Tenant as TenantModel

            with session_scope() as db:
                tenant = db.query(TenantModel).filter(TenantModel.id == user.tenant_id).first()
                if tenant:
                    display_name = tenant.name

        return {
            "tenant_display_name": display_name,
            "tenant_timezone": persistence.get_setting("tenant_timezone", None, tenant_id=user.tenant_id) or "Europe/Berlin",
            "tenant_locale": persistence.get_setting("tenant_locale", None, tenant_id=user.tenant_id) or "de-DE",
            "tenant_notify_email": persistence.get_setting("tenant_notify_email", None, tenant_id=user.tenant_id) or "",
            "tenant_notify_telegram": persistence.get_setting("tenant_notify_telegram", None, tenant_id=user.tenant_id) or "",
            "tenant_escalation_sla_minutes": persistence.get_setting("tenant_escalation_sla_minutes", None, tenant_id=user.tenant_id) or "15",
            "tenant_live_refresh_seconds": persistence.get_setting("tenant_live_refresh_seconds", None, tenant_id=user.tenant_id) or "5",
            "tenant_logo_url": persistence.get_setting("tenant_logo_url", None, tenant_id=user.tenant_id) or "",
            "tenant_primary_color": persistence.get_setting("tenant_primary_color", None, tenant_id=user.tenant_id) or "#3B82F6",
            "tenant_app_title": persistence.get_setting("tenant_app_title", None, tenant_id=user.tenant_id) or "ARIIA",
            "tenant_support_email": persistence.get_setting("tenant_support_email", None, tenant_id=user.tenant_id) or "",
        }

    def update_tenant_preferences(self, user: AuthContext, payload: dict[str, Any]) -> dict[str, str]:
        for key, value in payload.items():
            persistence.upsert_setting(key, str(value), tenant_id=user.tenant_id)
        write_admin_audit(
            actor=user,
            action="tenant.preferences.update",
            category="settings",
            target_type="tenant",
            target_id=str(user.tenant_id),
            details={"changed_keys": sorted(payload.keys())},
        )
        return {"status": "ok"}


service = AdminCoreSettingsService()

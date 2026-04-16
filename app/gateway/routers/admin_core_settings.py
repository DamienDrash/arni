from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import AuthContext, get_current_user
from app.gateway.admin_shared import require_system_admin, require_tenant_admin_or_system
from app.gateway.services.admin_core_settings_service import service

router = APIRouter(
    prefix="/admin",
    tags=["admin-core-settings"],
    dependencies=[Depends(get_current_user)],
)


class SettingUpdate(BaseModel):
    value: str
    description: str | None = None


class TenantPreferencesUpdate(BaseModel):
    tenant_display_name: str | None = None
    tenant_timezone: str | None = None
    tenant_locale: str | None = None
    tenant_notify_email: str | None = None
    tenant_notify_telegram: str | None = None
    tenant_escalation_sla_minutes: str | None = None
    tenant_live_refresh_seconds: str | None = None
    tenant_logo_url: str | None = None
    tenant_primary_color: str | None = None
    tenant_app_title: str | None = None
    tenant_support_email: str | None = None


@router.get("/settings")
async def get_all_settings(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    require_tenant_admin_or_system(user)
    return service.get_all_settings(user)


@router.put("/settings")
async def update_settings_batch(
    body: list[dict[str, Any]],
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    require_system_admin(user)
    return service.update_settings_batch(user, body)


@router.put("/settings/{key}")
async def update_setting(
    key: str,
    body: SettingUpdate,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    require_system_admin(user)
    return service.update_setting(user, key, body.value, body.description)


@router.get("/tenant-preferences")
async def get_tenant_preferences(user: AuthContext = Depends(get_current_user)) -> dict[str, str]:
    require_tenant_admin_or_system(user)
    return service.get_tenant_preferences(user)


@router.put("/tenant-preferences")
async def update_tenant_preferences(
    body: TenantPreferencesUpdate,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    require_tenant_admin_or_system(user)
    return service.update_tenant_preferences(user, body.model_dump(exclude_none=True))

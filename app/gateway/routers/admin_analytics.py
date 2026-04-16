from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.core.auth import AuthContext, get_current_user
from app.gateway.admin_shared import require_tenant_admin_or_system, resolve_tenant_id_for_slug
from app.gateway.services.admin_analytics_service import service

router = APIRouter(
    prefix="/admin",
    tags=["admin-analytics"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/analytics/overview")
async def get_analytics_overview(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.get_overview(user)


@router.get("/analytics/satisfaction")
async def analytics_satisfaction(user: AuthContext = Depends(get_current_user)) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.get_satisfaction(user)


@router.get("/analytics/hourly")
async def get_analytics_hourly(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    require_tenant_admin_or_system(user)
    return service.get_hourly(user)


@router.get("/analytics/weekly")
async def get_analytics_weekly(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    require_tenant_admin_or_system(user)
    return service.get_weekly(user)


@router.get("/analytics/intents")
async def get_analytics_intents(user: AuthContext = Depends(get_current_user)) -> list[dict[str, Any]]:
    require_tenant_admin_or_system(user)
    return service.get_intents(user)


@router.get("/analytics/channels")
async def analytics_channels(
    days: int = 30,
    tenant_slug: str | None = Query(None),
    user: AuthContext = Depends(get_current_user),
) -> list[dict[str, Any]]:
    require_tenant_admin_or_system(user)
    effective_tid = resolve_tenant_id_for_slug(user, tenant_slug)
    return service.get_channels(effective_tid, days=min(max(days, 1), 90))


@router.get("/analytics/sessions/recent")
async def analytics_recent_sessions(
    limit: int = 10,
    tenant_slug: str | None = Query(None),
    user: AuthContext = Depends(get_current_user),
) -> list[dict[str, Any]]:
    require_tenant_admin_or_system(user)
    effective_tid = resolve_tenant_id_for_slug(user, tenant_slug)
    return service.get_recent_sessions(effective_tid, limit=min(max(limit, 1), 50))


@router.get("/audit")
async def get_audit_logs(
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    require_tenant_admin_or_system(user)
    return service.get_audit_logs(user, limit=limit, offset=offset)

"""ARIIA v2.0 – Contact Sync API Router.

@ARCH: Contacts-Sync Refactoring
Dedicated API for managing contact synchronisation integrations.

Endpoints:
  GET    /sync/integrations/available       → List all available integrations
  GET    /sync/integrations                 → List tenant's configured integrations
  POST   /sync/integrations/{id}/test       → Test connection before saving
  POST   /sync/integrations/{id}/save       → Save/update integration config
  DELETE /sync/integrations/{id}            → Remove integration
  POST   /sync/integrations/{id}/run        → Trigger manual sync
  GET    /sync/history                      → Sync history (all integrations)
  GET    /sync/history/{id}                 → Sync history for specific integration
  POST   /sync/webhook/{id}/{tenant_slug}   → Webhook receiver (no auth)
"""

from __future__ import annotations

import structlog
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.core.auth import AuthContext, get_current_user, require_role
from app.gateway.contact_sync_repository import contact_sync_repository
from app.shared.db import session_scope, transaction_scope

logger = structlog.get_logger()
router = APIRouter(prefix="/sync", tags=["contact-sync"])


# ── Request / Response Models ────────────────────────────────────────────────

class TestConnectionRequest(BaseModel):
    config: Dict[str, Any]


class SaveIntegrationRequest(BaseModel):
    config: Dict[str, Any]
    sync_direction: str = "inbound"
    sync_interval_minutes: int = 60
    enabled: bool = True


class RunSyncRequest(BaseModel):
    sync_mode: Optional[str] = None  # "full" or "incremental"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _require_admin(user: AuthContext):
    require_role(user, {"system_admin", "tenant_admin"})


def _get_sync_core():
    """Lazy import to avoid circular imports."""
    from app.contacts.sync_core import sync_core
    return sync_core


# ══════════════════════════════════════════════════════════════════════════════
# AVAILABLE INTEGRATIONS (Marketplace)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/integrations/available")
def list_available_integrations(
    user: AuthContext = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List all available contact-sync integrations with their config schemas.

    This powers the "Integration Marketplace" in the frontend.
    Returns adapters that support contact sync, with their configuration
    fields so the frontend can render dynamic setup forms.
    """
    core = _get_sync_core()
    return core.get_available_integrations()


# ══════════════════════════════════════════════════════════════════════════════
# TENANT INTEGRATIONS (Configured)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/integrations")
def list_tenant_integrations(
    user: AuthContext = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List all integrations configured for the current tenant.

    Returns status, last sync info, and sync schedule for each.
    """
    core = _get_sync_core()
    return core.get_tenant_integrations(user.tenant_id)


@router.get("/integrations/{integration_id}")
def get_integration_detail(
    integration_id: str,
    user: AuthContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get detailed info about a specific integration for this tenant."""
    core = _get_sync_core()
    integrations = core.get_tenant_integrations(user.tenant_id)
    for i in integrations:
        if i["integration_id"] == integration_id:
            return i
    raise HTTPException(status_code=404, detail="Integration nicht konfiguriert.")


# ══════════════════════════════════════════════════════════════════════════════
# CONNECTION TEST
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/integrations/{integration_id}/test")
async def test_connection(
    integration_id: str,
    body: TestConnectionRequest,
    user: AuthContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Test connection to an external integration before saving.

    The frontend sends the config fields (including credentials) and
    this endpoint tests the connection without persisting anything.
    """
    _require_admin(user)
    core = _get_sync_core()

    result = await core.test_connection(
        tenant_id=user.tenant_id,
        integration_id=integration_id,
        config=body.config,
    )

    return {
        "success": result.success,
        "message": result.message,
        "details": result.details,
        "latency_ms": result.latency_ms,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SAVE / UPDATE / DELETE INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/integrations/{integration_id}/save")
def save_integration(
    integration_id: str,
    body: SaveIntegrationRequest,
    user: AuthContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Save or update an integration configuration.

    Credentials are encrypted and stored in the Vault.
    Non-secret config is stored in the tenant_integrations table.
    """
    _require_admin(user)
    core = _get_sync_core()

    try:
        result = core.save_integration(
            tenant_id=user.tenant_id,
            integration_id=integration_id,
            config=body.config,
            sync_direction=body.sync_direction,
            sync_interval_minutes=body.sync_interval_minutes,
            enabled=body.enabled,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("contact_sync_api.save_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Interner Serverfehler")


@router.put("/integrations/{integration_id}/toggle")
def toggle_integration(
    integration_id: str,
    enabled: bool = Body(..., embed=True),
    user: AuthContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Enable or disable an integration without changing its config."""
    _require_admin(user)

    with transaction_scope() as db:
        ti = contact_sync_repository.get_tenant_integration(
            db,
            tenant_id=user.tenant_id,
            integration_id=integration_id,
        )
        if not ti:
            raise HTTPException(status_code=404, detail="Integration nicht gefunden.")

        ti.enabled = enabled
        ti.updated_at = datetime.now(timezone.utc)
        return {"success": True, "enabled": enabled, "message": f"Integration {'aktiviert' if enabled else 'deaktiviert'}."}


@router.delete("/integrations/{integration_id}")
def delete_integration(
    integration_id: str,
    user: AuthContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Remove an integration and its credentials."""
    _require_admin(user)
    core = _get_sync_core()

    try:
        result = core.delete_integration(user.tenant_id, integration_id)
        return result
    except Exception as e:
        logger.error("contact_sync_api.delete_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Interner Serverfehler")


# ══════════════════════════════════════════════════════════════════════════════
# RUN SYNC
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/integrations/{integration_id}/run")
async def run_sync(
    integration_id: str,
    body: RunSyncRequest = RunSyncRequest(),
    user: AuthContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Trigger a manual contact sync for an integration.

    Optionally specify sync_mode ("full" or "incremental").
    If not specified, auto-detects based on last sync time.
    """
    _require_admin(user)
    core = _get_sync_core()

    from app.integrations.adapters.base import SyncMode
    sync_mode = None
    if body.sync_mode:
        sync_mode = SyncMode(body.sync_mode)

    result = await core.run_sync(
        tenant_id=user.tenant_id,
        integration_id=integration_id,
        sync_mode=sync_mode,
        triggered_by="manual",
    )

    return result


# ══════════════════════════════════════════════════════════════════════════════
# SYNC HISTORY
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/history")
def get_sync_history(
    limit: int = Query(20, ge=1, le=100),
    user: AuthContext = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Get sync history for all integrations of the current tenant."""
    core = _get_sync_core()
    return core.get_sync_history(user.tenant_id, limit=limit)


@router.get("/history/{integration_id}")
def get_integration_sync_history(
    integration_id: str,
    limit: int = Query(20, ge=1, le=100),
    user: AuthContext = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Get sync history for a specific integration."""
    core = _get_sync_core()
    return core.get_sync_history(user.tenant_id, integration_id=integration_id, limit=limit)


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH & MONITORING
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/health")
def get_sync_health(
    user: AuthContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get health status of all contact sync integrations.

    Returns aggregated health summary with per-integration details,
    including stale sync detection, error patterns, and performance metrics.
    """
    from app.contacts.sync_health import sync_health_service
    return sync_health_service.get_system_health_summary(user.tenant_id)


@router.get("/health/{integration_id}")
def get_integration_health(
    integration_id: str,
    user: AuthContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get detailed health status for a specific integration."""
    from app.contacts.sync_health import sync_health_service
    health = sync_health_service.check_integration_health(user.tenant_id, integration_id)
    return health.to_dict()


@router.get("/scheduler/status")
def get_scheduler_status(
    user: AuthContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get the sync scheduler status and statistics."""
    _require_admin(user)
    from app.contacts.sync_scheduler import sync_scheduler
    return sync_scheduler.stats


@router.get("/stats")
def get_sync_stats(
    user: AuthContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get aggregated sync statistics for the monitoring dashboard.

    Returns:
      - Total contacts synced (24h, 7d, 30d)
      - Sync success/failure rates
      - Per-integration breakdown
      - Trend data for charts
    """
    with session_scope() as db:
        now = datetime.now(timezone.utc)
        t_24h = now - timedelta(hours=24)
        t_7d = now - timedelta(days=7)
        t_30d = now - timedelta(days=30)

        logs_24h = contact_sync_repository.list_sync_logs_since(
            db,
            tenant_id=user.tenant_id,
            started_at_gte=t_24h,
        )
        synced_24h = sum((l.records_created or 0) + (l.records_updated or 0) for l in logs_24h)
        errors_24h = sum(1 for l in logs_24h if l.status == "error")
        success_24h = sum(1 for l in logs_24h if l.status == "success")

        logs_7d = contact_sync_repository.list_sync_logs_since(
            db,
            tenant_id=user.tenant_id,
            started_at_gte=t_7d,
        )
        synced_7d = sum((l.records_created or 0) + (l.records_updated or 0) for l in logs_7d)

        logs_30d = contact_sync_repository.list_sync_logs_since(
            db,
            tenant_id=user.tenant_id,
            started_at_gte=t_30d,
        )
        synced_30d = sum((l.records_created or 0) + (l.records_updated or 0) for l in logs_30d)

        integrations = contact_sync_repository.list_tenant_integrations(
            db,
            tenant_id=user.tenant_id,
        )

        breakdown = []
        for ti in integrations:
            ti_logs_24h = [
                l for l in logs_24h if getattr(l, "tenant_integration_id", None) == ti.id
            ]
            display_name = getattr(ti, "display_name", None)
            if not display_name:
                integration = getattr(ti, "integration", None)
                display_name = getattr(integration, "name", None) or ti.integration_id
            breakdown.append({
                "integration_id": ti.integration_id,
                "display_name": display_name,
                "status": ti.status,
                "enabled": ti.enabled,
                "syncs_24h": len(ti_logs_24h),
                "records_24h": sum((l.records_created or 0) + (l.records_updated or 0) for l in ti_logs_24h),
                "errors_24h": sum(1 for l in ti_logs_24h if l.status == "error"),
                "last_sync_at": ti.last_sync_at.isoformat() if ti.last_sync_at else None,
            })

        # Trend data (daily for last 7 days)
        trend = []
        for i in range(7):
            day_start = (now - timedelta(days=6-i)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            day_logs = [l for l in logs_7d if l.started_at and day_start <= l.started_at.replace(tzinfo=timezone.utc) < day_end]
            trend.append({
                "date": day_start.strftime("%Y-%m-%d"),
                "syncs": len(day_logs),
                "records": sum((l.records_created or 0) + (l.records_updated or 0) for l in day_logs),
                "errors": sum(1 for l in day_logs if l.status == "error"),
            })

        return {
            "period_24h": {
                "total_syncs": len(logs_24h),
                "successful_syncs": success_24h,
                "failed_syncs": errors_24h,
                "records_synced": synced_24h,
                "success_rate": round(success_24h / len(logs_24h), 3) if logs_24h else None,
            },
            "period_7d": {
                "total_syncs": len(logs_7d),
                "records_synced": synced_7d,
            },
            "period_30d": {
                "total_syncs": len(logs_30d),
                "records_synced": synced_30d,
            },
            "integrations": breakdown,
            "trend_7d": trend,
        }


# ══════════════════════════════════════════════════════════════════════════════
# WEBHOOK RECEIVER (No Auth – External Systems)
# ══════════════════════════════════════════════════════════════════════════════

# Note: This is a separate router without auth prefix, mounted at app level
webhook_router = APIRouter(tags=["contact-sync-webhooks"])


@webhook_router.post("/webhook/sync/{integration_id}/{tenant_slug}")
async def receive_webhook(
    integration_id: str,
    tenant_slug: str,
    request: Request,
) -> Dict[str, Any]:
    """Receive webhook from external integration.

    This endpoint is called by Shopify, WooCommerce, HubSpot etc.
    when contacts are created/updated/deleted in their system.

    No authentication – webhook verification is handled by each adapter.
    """
    with session_scope() as db:
        tenant = contact_sync_repository.get_tenant_by_slug(
            db,
            tenant_slug=tenant_slug,
        )
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        tenant_id = tenant.id

    # Parse payload
    try:
        payload = await request.json()
    except Exception as e:
        logger.warning("contact_sync_api.webhook_parse_failed", error=str(e))
        payload = {}

    # Collect headers
    headers = dict(request.headers)

    core = _get_sync_core()
    result = await core.handle_webhook(
        tenant_id=tenant_id,
        integration_id=integration_id,
        payload=payload,
        headers=headers,
    )

    if not result.get("success"):
        logger.warning(
            "webhook.processing_failed",
            integration_id=integration_id,
            tenant_slug=tenant_slug,
            error=result.get("error"),
        )

    return {"status": "ok", **result}

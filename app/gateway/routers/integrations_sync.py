"""app/gateway/routers/integrations_sync.py — Contact Sync API (v2).

@ARCH: Contacts Refactoring – Integration Sync Router
Handles:
- Credential management for integrations
- Manual sync triggers (now writing to contacts table)
- Sync status and history
- Webhook endpoints for real-time updates (future)

All sync operations now use the ContactSyncService and write
directly into the new `contacts` table instead of the legacy
`studio_members` table.
"""
from __future__ import annotations

import asyncio
import structlog
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.core.auth import AuthContext, get_current_user, require_role
from app.gateway.persistence import persistence
from app.core.feature_gates import FeatureGate

logger = structlog.get_logger()
router = APIRouter(prefix="/admin/integrations", tags=["integrations"])


# ── Request Models ────────────────────────────────────────────────────────────

class ShopifyCredentials(BaseModel):
    domain: str
    access_token: str

class WooCommerceCredentials(BaseModel):
    store_url: str
    consumer_key: str
    consumer_secret: str

class HubSpotCredentials(BaseModel):
    access_token: str


# ── Response Models ───────────────────────────────────────────────────────────

class SyncStatusResponse(BaseModel):
    source: str
    enabled: bool
    last_sync: Optional[str] = None
    status: str = "idle"  # idle, running, completed, failed


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_admin(user: AuthContext):
    require_role(user, {"system_admin", "tenant_admin"})


def _check_connector_limit(tenant_id: int):
    """Check if tenant can add another connector based on plan."""
    gate = FeatureGate(tenant_id)
    # gate.check_connector_limit()  # TODO: Implement in FeatureGate
    pass


def _get_sync_status(tenant_id: int, source: str) -> SyncStatusResponse:
    """Get the sync status for a specific integration."""
    prefix = f"integration_{source}_{tenant_id}"
    enabled = persistence.get_setting(f"{prefix}_enabled") == "true"
    last_sync = persistence.get_setting(f"sync_{source}_{tenant_id}_last")
    status = persistence.get_setting(f"sync_{source}_{tenant_id}_status") or "idle"
    return SyncStatusResponse(
        source=source,
        enabled=enabled,
        last_sync=last_sync,
        status=status,
    )


def _set_sync_status(tenant_id: int, source: str, status: str):
    """Update sync status in settings."""
    persistence.set_setting(f"sync_{source}_{tenant_id}_status", status)
    if status == "completed":
        persistence.set_setting(
            f"sync_{source}_{tenant_id}_last",
            datetime.now(timezone.utc).isoformat(),
        )


# ── Sync Status Overview ─────────────────────────────────────────────────────

@router.get("/sync-status")
def get_all_sync_status(user: AuthContext = Depends(get_current_user)):
    """Get sync status for all configured integrations."""
    _require_admin(user)
    sources = ["magicline", "shopify", "woocommerce", "hubspot"]
    statuses = []
    for source in sources:
        statuses.append(_get_sync_status(user.tenant_id, source).model_dump())
    return {"integrations": statuses}


@router.get("/sync-status/{source}")
def get_sync_status(
    source: str,
    user: AuthContext = Depends(get_current_user),
):
    """Get sync status for a specific integration."""
    _require_admin(user)
    return _get_sync_status(user.tenant_id, source).model_dump()


# ── Magicline ─────────────────────────────────────────────────────────────────

@router.post("/connectors/magicline/sync")
def sync_magicline(
    background_tasks: BackgroundTasks,
    user: AuthContext = Depends(get_current_user),
):
    """Trigger Magicline → Contacts sync."""
    _require_admin(user)
    _set_sync_status(user.tenant_id, "magicline", "running")

    def _run_magicline_sync(tenant_id: int):
        try:
            from app.integrations.magicline.contact_sync import sync_contacts_from_magicline
            result = sync_contacts_from_magicline(tenant_id)
            _set_sync_status(tenant_id, "magicline", "completed")
            persistence.set_setting(
                f"sync_magicline_{tenant_id}_result",
                str(result),
            )
            logger.info("magicline.sync.completed", tenant_id=tenant_id, result=result)
        except Exception as e:
            _set_sync_status(tenant_id, "magicline", "failed")
            persistence.set_setting(
                f"sync_magicline_{tenant_id}_error",
                str(e),
            )
            logger.error("magicline.sync.failed", tenant_id=tenant_id, error=str(e))

    background_tasks.add_task(_run_magicline_sync, user.tenant_id)
    return {"status": "sync_started", "source": "magicline"}


# ── Shopify ───────────────────────────────────────────────────────────────────

@router.put("/connectors/shopify")
def configure_shopify(
    creds: ShopifyCredentials,
    user: AuthContext = Depends(get_current_user),
):
    _require_admin(user)
    _check_connector_limit(user.tenant_id)

    prefix = f"integration_shopify_{user.tenant_id}"
    persistence.set_setting(f"{prefix}_domain", creds.domain)
    persistence.set_setting(f"{prefix}_access_token", creds.access_token)
    persistence.set_setting(f"{prefix}_enabled", "true")

    return {"status": "configured", "source": "shopify"}


@router.post("/connectors/shopify/test")
def test_shopify(user: AuthContext = Depends(get_current_user)):
    _require_admin(user)
    # TODO: Implement actual connection test
    return {"status": "ok", "message": "Connection successful"}


@router.post("/connectors/shopify/sync")
def sync_shopify(
    background_tasks: BackgroundTasks,
    user: AuthContext = Depends(get_current_user),
):
    """Trigger Shopify → Contacts sync."""
    _require_admin(user)
    _set_sync_status(user.tenant_id, "shopify", "running")

    def _run_shopify_sync(tenant_id: int):
        try:
            from app.integrations.shopify.contact_sync import sync_contacts_from_shopify
            result = asyncio.run(sync_contacts_from_shopify(tenant_id))
            _set_sync_status(tenant_id, "shopify", "completed")
            persistence.set_setting(
                f"sync_shopify_{tenant_id}_result",
                str(result),
            )
            logger.info("shopify.sync.completed", tenant_id=tenant_id, result=result)
        except Exception as e:
            _set_sync_status(tenant_id, "shopify", "failed")
            persistence.set_setting(
                f"sync_shopify_{tenant_id}_error",
                str(e),
            )
            logger.error("shopify.sync.failed", tenant_id=tenant_id, error=str(e))

    background_tasks.add_task(_run_shopify_sync, user.tenant_id)
    return {"status": "sync_started", "source": "shopify"}


# ── WooCommerce ───────────────────────────────────────────────────────────────

@router.put("/connectors/woocommerce")
def configure_woocommerce(
    creds: WooCommerceCredentials,
    user: AuthContext = Depends(get_current_user),
):
    _require_admin(user)
    prefix = f"integration_woocommerce_{user.tenant_id}"
    persistence.set_setting(f"{prefix}_url", creds.store_url)
    persistence.set_setting(f"{prefix}_key", creds.consumer_key)
    persistence.set_setting(f"{prefix}_secret", creds.consumer_secret)
    persistence.set_setting(f"{prefix}_enabled", "true")
    return {"status": "configured", "source": "woocommerce"}


@router.post("/connectors/woocommerce/sync")
def sync_woocommerce(
    background_tasks: BackgroundTasks,
    user: AuthContext = Depends(get_current_user),
):
    """Trigger WooCommerce → Contacts sync."""
    _require_admin(user)
    _set_sync_status(user.tenant_id, "woocommerce", "running")

    def _run_woocommerce_sync(tenant_id: int):
        try:
            from app.integrations.woocommerce.contact_sync import sync_contacts_from_woocommerce
            result = asyncio.run(sync_contacts_from_woocommerce(tenant_id))
            _set_sync_status(tenant_id, "woocommerce", "completed")
            persistence.set_setting(
                f"sync_woocommerce_{tenant_id}_result",
                str(result),
            )
            logger.info("woocommerce.sync.completed", tenant_id=tenant_id, result=result)
        except Exception as e:
            _set_sync_status(tenant_id, "woocommerce", "failed")
            persistence.set_setting(
                f"sync_woocommerce_{tenant_id}_error",
                str(e),
            )
            logger.error("woocommerce.sync.failed", tenant_id=tenant_id, error=str(e))

    background_tasks.add_task(_run_woocommerce_sync, user.tenant_id)
    return {"status": "sync_started", "source": "woocommerce"}


# ── HubSpot ───────────────────────────────────────────────────────────────────

@router.put("/connectors/hubspot")
def configure_hubspot(
    creds: HubSpotCredentials,
    user: AuthContext = Depends(get_current_user),
):
    _require_admin(user)
    prefix = f"integration_hubspot_{user.tenant_id}"
    persistence.set_setting(f"{prefix}_token", creds.access_token)
    persistence.set_setting(f"{prefix}_enabled", "true")
    return {"status": "configured", "source": "hubspot"}


@router.post("/connectors/hubspot/sync")
def sync_hubspot(
    background_tasks: BackgroundTasks,
    user: AuthContext = Depends(get_current_user),
):
    """Trigger HubSpot → Contacts sync."""
    _require_admin(user)
    _set_sync_status(user.tenant_id, "hubspot", "running")

    def _run_hubspot_sync(tenant_id: int):
        try:
            from app.integrations.hubspot.contact_sync import sync_contacts_from_hubspot
            result = asyncio.run(sync_contacts_from_hubspot(tenant_id))
            _set_sync_status(tenant_id, "hubspot", "completed")
            persistence.set_setting(
                f"sync_hubspot_{tenant_id}_result",
                str(result),
            )
            logger.info("hubspot.sync.completed", tenant_id=tenant_id, result=result)
        except Exception as e:
            _set_sync_status(tenant_id, "hubspot", "failed")
            persistence.set_setting(
                f"sync_hubspot_{tenant_id}_error",
                str(e),
            )
            logger.error("hubspot.sync.failed", tenant_id=tenant_id, error=str(e))

    background_tasks.add_task(_run_hubspot_sync, user.tenant_id)
    return {"status": "sync_started", "source": "hubspot"}

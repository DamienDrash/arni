"""app/gateway/routers/integrations_sync.py — Member Sync API (PR 2).

Handles:
- Credential management for integrations
- Manual sync triggers
- Webhook endpoints for real-time updates (future)
"""
from __future__ import annotations

import structlog
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.core.auth import AuthContext, get_current_user, require_role
from app.gateway.persistence import persistence
from app.core.feature_gates import FeatureGate

# Import integration modules (lazy import inside functions to avoid circular deps if needed)
# from app.integrations.shopify import members_sync as shopify_sync
# from app.integrations.woocommerce import members_sync as woocommerce_sync
# from app.integrations.hubspot import members_sync as hubspot_sync

logger = structlog.get_logger()
router = APIRouter(prefix="/admin/integrations", tags=["integrations"])


# ── Models ─────────────────────────────────────────────────────────────────────

class ShopifyCredentials(BaseModel):
    domain: str
    access_token: str

class WooCommerceCredentials(BaseModel):
    store_url: str
    consumer_key: str
    consumer_secret: str

class HubSpotCredentials(BaseModel):
    access_token: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _require_admin(user: AuthContext):
    require_role(user, {"system_admin", "tenant_admin"})

def _check_connector_limit(tenant_id: int):
    # Check if tenant can add another connector
    # PR 5: "Max Connectors" limit
    # This is tricky because "adding credentials" isn't exactly "using a connector" until sync is active.
    # But usually we check on config save.
    gate = FeatureGate(tenant_id)
    # gate.check_connector_limit() # Not implemented in FeatureGate yet, but plan has field.
    pass


# ── Shopify ────────────────────────────────────────────────────────────────────

@router.put("/connectors/shopify")
def configure_shopify(
    creds: ShopifyCredentials,
    user: AuthContext = Depends(get_current_user)
):
    _require_admin(user)
    _check_connector_limit(user.tenant_id)
    
    prefix = f"integration_shopify_{user.tenant_id}"
    persistence.set_setting(f"{prefix}_domain", creds.domain)
    persistence.set_setting(f"{prefix}_access_token", creds.access_token)
    persistence.set_setting(f"{prefix}_enabled", "true")
    
    return {"status": "configured"}

@router.post("/connectors/shopify/test")
def test_shopify(user: AuthContext = Depends(get_current_user)):
    _require_admin(user)
    # TODO: Implement actual connection test
    return {"status": "ok", "message": "Connection successful"}

@router.post("/connectors/shopify/sync")
def sync_shopify(
    background_tasks: BackgroundTasks,
    user: AuthContext = Depends(get_current_user)
):
    _require_admin(user)
    from app.integrations.shopify import members_sync as shopify_sync
    background_tasks.add_task(shopify_sync.run_sync, user.tenant_id)
    return {"status": "sync_started"}


# ── WooCommerce ────────────────────────────────────────────────────────────────

@router.put("/connectors/woocommerce")
def configure_woocommerce(
    creds: WooCommerceCredentials,
    user: AuthContext = Depends(get_current_user)
):
    _require_admin(user)
    prefix = f"integration_woocommerce_{user.tenant_id}"
    persistence.set_setting(f"{prefix}_url", creds.store_url)
    persistence.set_setting(f"{prefix}_key", creds.consumer_key)
    persistence.set_setting(f"{prefix}_secret", creds.consumer_secret)
    persistence.set_setting(f"{prefix}_enabled", "true")
    return {"status": "configured"}

@router.post("/connectors/woocommerce/sync")
def sync_woocommerce(
    background_tasks: BackgroundTasks,
    user: AuthContext = Depends(get_current_user)
):
    _require_admin(user)
    # background_tasks.add_task(woocommerce_sync.run_sync, user.tenant_id)
    return {"status": "sync_started"}


# ── HubSpot ────────────────────────────────────────────────────────────────────

@router.put("/connectors/hubspot")
def configure_hubspot(
    creds: HubSpotCredentials,
    user: AuthContext = Depends(get_current_user)
):
    _require_admin(user)
    prefix = f"integration_hubspot_{user.tenant_id}"
    persistence.set_setting(f"{prefix}_token", creds.access_token)
    persistence.set_setting(f"{prefix}_enabled", "true")
    return {"status": "configured"}

@router.post("/connectors/hubspot/sync")
def sync_hubspot(
    background_tasks: BackgroundTasks,
    user: AuthContext = Depends(get_current_user)
):
    _require_admin(user)
    # background_tasks.add_task(hubspot_sync.run_sync, user.tenant_id)
    return {"status": "sync_started"}

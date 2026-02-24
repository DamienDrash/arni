"""Integrations Sync Router — Shopify, WooCommerce, HubSpot member sync.

Provides endpoints for:
- Triggering sync from each platform
- Testing connections
- Managing connector settings (credentials)
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import AuthContext, get_current_user, require_role
from app.gateway import persistence

router = APIRouter(prefix="/admin/integrations", tags=["integrations"])
logger = structlog.get_logger()


def _require_tenant_admin_or_system(user: AuthContext) -> None:
    require_role(user, {"system_admin", "tenant_admin"})


# ─── Connector Settings Schemas ──────────────────────────────────────────────

class ShopifyConnectorSettings(BaseModel):
    shop_domain: str
    access_token: str


class WooCommerceConnectorSettings(BaseModel):
    store_url: str
    consumer_key: str
    consumer_secret: str


class HubSpotConnectorSettings(BaseModel):
    access_token: str


# ─── Connector Settings CRUD ─────────────────────────────────────────────────

@router.get("/connectors")
async def list_connectors(
    user: AuthContext = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List all available integration connectors and their status."""
    _require_tenant_admin_or_system(user)
    tid = user.tenant_id

    connectors = []

    # Magicline (existing)
    ml_url = persistence.get_setting("magicline_base_url", tenant_id=tid)
    ml_key = persistence.get_setting("magicline_api_key", tenant_id=tid)
    connectors.append({
        "id": "magicline",
        "name": "Magicline",
        "description": "Studio-Management-Software für Fitnessstudios",
        "icon": "database",
        "is_configured": bool(ml_url and ml_key),
        "settings_keys": ["magicline_base_url", "magicline_api_key"],
        "last_sync": persistence.get_setting("magicline_last_sync_at", tenant_id=tid),
        "last_sync_status": persistence.get_setting("magicline_last_sync_status", tenant_id=tid),
    })

    # Shopify
    sh_domain = persistence.get_setting("shopify_shop_domain", tenant_id=tid)
    sh_token = persistence.get_setting("shopify_access_token", tenant_id=tid)
    connectors.append({
        "id": "shopify",
        "name": "Shopify",
        "description": "E-Commerce-Plattform — Kunden-Sync",
        "icon": "shopping-bag",
        "is_configured": bool(sh_domain and sh_token),
        "settings_keys": ["shopify_shop_domain", "shopify_access_token"],
        "last_sync": persistence.get_setting("shopify_last_sync_at", tenant_id=tid),
        "last_sync_status": persistence.get_setting("shopify_last_sync_status", tenant_id=tid),
    })

    # WooCommerce
    wc_url = persistence.get_setting("woocommerce_store_url", tenant_id=tid)
    wc_key = persistence.get_setting("woocommerce_consumer_key", tenant_id=tid)
    wc_secret = persistence.get_setting("woocommerce_consumer_secret", tenant_id=tid)
    connectors.append({
        "id": "woocommerce",
        "name": "WooCommerce",
        "description": "WordPress E-Commerce — Kunden-Sync",
        "icon": "shopping-cart",
        "is_configured": bool(wc_url and wc_key and wc_secret),
        "settings_keys": ["woocommerce_store_url", "woocommerce_consumer_key", "woocommerce_consumer_secret"],
        "last_sync": persistence.get_setting("woocommerce_last_sync_at", tenant_id=tid),
        "last_sync_status": persistence.get_setting("woocommerce_last_sync_status", tenant_id=tid),
    })

    # HubSpot
    hs_token = persistence.get_setting("hubspot_access_token", tenant_id=tid)
    connectors.append({
        "id": "hubspot",
        "name": "HubSpot",
        "description": "CRM-Plattform — Kontakte-Sync",
        "icon": "users",
        "is_configured": bool(hs_token),
        "settings_keys": ["hubspot_access_token"],
        "last_sync": persistence.get_setting("hubspot_last_sync_at", tenant_id=tid),
        "last_sync_status": persistence.get_setting("hubspot_last_sync_status", tenant_id=tid),
    })

    return connectors


# ─── Shopify ──────────────────────────────────────────────────────────────────

@router.put("/connectors/shopify")
async def save_shopify_settings(
    body: ShopifyConnectorSettings,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Save Shopify connector credentials."""
    _require_tenant_admin_or_system(user)
    persistence.upsert_setting("shopify_shop_domain", body.shop_domain.strip(), tenant_id=user.tenant_id)
    persistence.upsert_setting("shopify_access_token", body.access_token.strip(), tenant_id=user.tenant_id)
    return {"status": "ok"}


@router.post("/connectors/shopify/test")
async def test_shopify(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Test the Shopify connection."""
    _require_tenant_admin_or_system(user)
    from app.integrations.shopify.members_sync import test_shopify_connection
    return test_shopify_connection(user.tenant_id)


@router.post("/connectors/shopify/sync")
async def sync_shopify(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Trigger a full Shopify customer sync."""
    _require_tenant_admin_or_system(user)
    from datetime import datetime, timezone
    from app.integrations.shopify.members_sync import sync_members_from_shopify

    try:
        started_at = datetime.now(timezone.utc).isoformat()
        result = sync_members_from_shopify(tenant_id=user.tenant_id)
        persistence.upsert_setting("shopify_last_sync_at", started_at, tenant_id=user.tenant_id)
        persistence.upsert_setting("shopify_last_sync_status", "ok", tenant_id=user.tenant_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        persistence.upsert_setting("shopify_last_sync_status", "error", tenant_id=user.tenant_id)
        persistence.upsert_setting("shopify_last_sync_error", str(e), tenant_id=user.tenant_id)
        raise HTTPException(status_code=502, detail=f"Shopify Sync fehlgeschlagen: {e}")


# ─── WooCommerce ──────────────────────────────────────────────────────────────

@router.put("/connectors/woocommerce")
async def save_woocommerce_settings(
    body: WooCommerceConnectorSettings,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Save WooCommerce connector credentials."""
    _require_tenant_admin_or_system(user)
    persistence.upsert_setting("woocommerce_store_url", body.store_url.strip(), tenant_id=user.tenant_id)
    persistence.upsert_setting("woocommerce_consumer_key", body.consumer_key.strip(), tenant_id=user.tenant_id)
    persistence.upsert_setting("woocommerce_consumer_secret", body.consumer_secret.strip(), tenant_id=user.tenant_id)
    return {"status": "ok"}


@router.post("/connectors/woocommerce/test")
async def test_woocommerce(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Test the WooCommerce connection."""
    _require_tenant_admin_or_system(user)
    from app.integrations.woocommerce.members_sync import test_woocommerce_connection
    return test_woocommerce_connection(user.tenant_id)


@router.post("/connectors/woocommerce/sync")
async def sync_woocommerce(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Trigger a full WooCommerce customer sync."""
    _require_tenant_admin_or_system(user)
    from datetime import datetime, timezone
    from app.integrations.woocommerce.members_sync import sync_members_from_woocommerce

    try:
        started_at = datetime.now(timezone.utc).isoformat()
        result = sync_members_from_woocommerce(tenant_id=user.tenant_id)
        persistence.upsert_setting("woocommerce_last_sync_at", started_at, tenant_id=user.tenant_id)
        persistence.upsert_setting("woocommerce_last_sync_status", "ok", tenant_id=user.tenant_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        persistence.upsert_setting("woocommerce_last_sync_status", "error", tenant_id=user.tenant_id)
        persistence.upsert_setting("woocommerce_last_sync_error", str(e), tenant_id=user.tenant_id)
        raise HTTPException(status_code=502, detail=f"WooCommerce Sync fehlgeschlagen: {e}")


# ─── HubSpot ─────────────────────────────────────────────────────────────────

@router.put("/connectors/hubspot")
async def save_hubspot_settings(
    body: HubSpotConnectorSettings,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Save HubSpot connector credentials."""
    _require_tenant_admin_or_system(user)
    persistence.upsert_setting("hubspot_access_token", body.access_token.strip(), tenant_id=user.tenant_id)
    return {"status": "ok"}


@router.post("/connectors/hubspot/test")
async def test_hubspot(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Test the HubSpot connection."""
    _require_tenant_admin_or_system(user)
    from app.integrations.hubspot.members_sync import test_hubspot_connection
    return test_hubspot_connection(user.tenant_id)


@router.post("/connectors/hubspot/sync")
async def sync_hubspot(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Trigger a full HubSpot contact sync."""
    _require_tenant_admin_or_system(user)
    from datetime import datetime, timezone
    from app.integrations.hubspot.members_sync import sync_members_from_hubspot

    try:
        started_at = datetime.now(timezone.utc).isoformat()
        result = sync_members_from_hubspot(tenant_id=user.tenant_id)
        persistence.upsert_setting("hubspot_last_sync_at", started_at, tenant_id=user.tenant_id)
        persistence.upsert_setting("hubspot_last_sync_status", "ok", tenant_id=user.tenant_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        persistence.upsert_setting("hubspot_last_sync_status", "error", tenant_id=user.tenant_id)
        persistence.upsert_setting("hubspot_last_sync_error", str(e), tenant_id=user.tenant_id)
        raise HTTPException(status_code=502, detail=f"HubSpot Sync fehlgeschlagen: {e}")

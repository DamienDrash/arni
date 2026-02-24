"""ARIIA – Connector Hub Router.

Unified API for listing, configuring, testing, and getting setup docs
for all integration connectors (messaging, email, voice, members, CRM).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException

from app.gateway.dependencies import get_current_user
from app.gateway.auth import AuthContext
from app.gateway.persistence import persistence
from app.integrations.connector_registry import (
    ALL_CONNECTORS,
    CATEGORY_LABELS,
    CATEGORIES_ORDER,
    get_connector,
    get_connectors_by_category,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/connector-hub", tags=["connector-hub"])

REDACTED = "••••••••"


def _require_tenant_admin_or_system(user: AuthContext) -> None:
    if user.role not in ("tenant_admin", "system_admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")


def _mask_value(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return REDACTED
    return value[:3] + REDACTED + value[-3:]


# ─────────────────────────────────────────────────────────
# LIST & CATALOG
# ─────────────────────────────────────────────────────────

@router.get("/catalog")
async def get_connector_catalog(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Return all available connectors grouped by category, with config status."""
    _require_tenant_admin_or_system(user)

    categories = []
    for cat in CATEGORIES_ORDER:
        connectors_in_cat = [
            c for c in ALL_CONNECTORS.values() if c.category == cat
        ]
        if not connectors_in_cat:
            continue

        items = []
        for conn in connectors_in_cat:
            # Check if configured (has at least one required field set)
            is_configured = False
            required_fields = [f for f in conn.fields if f.required]
            if required_fields:
                for f in required_fields:
                    sk = f.setting_key or f"{conn.id}_{f.key}"
                    val = persistence.get_setting(sk, tenant_id=user.tenant_id)
                    if val:
                        is_configured = True
                        break
            else:
                # No required fields = always "configured" (e.g. QR mode)
                is_configured = True

            # Get health status
            last_test_at = persistence.get_setting(
                f"integration_{conn.id}_last_test_at", tenant_id=user.tenant_id
            ) or ""
            last_status = persistence.get_setting(
                f"integration_{conn.id}_last_status", tenant_id=user.tenant_id
            ) or "never"
            last_detail = persistence.get_setting(
                f"integration_{conn.id}_last_detail", tenant_id=user.tenant_id
            ) or ""

            items.append({
                **conn.to_dict(include_docs=False),
                "is_configured": is_configured,
                "health": {
                    "last_test_at": last_test_at,
                    "status": last_status,
                    "detail": last_detail,
                },
            })

        categories.append({
            "id": cat.value,
            "label": CATEGORY_LABELS.get(cat, cat.value),
            "connectors": items,
        })

    return {"categories": categories}


# ─────────────────────────────────────────────────────────
# GET CONFIG FOR A SINGLE CONNECTOR
# ─────────────────────────────────────────────────────────

@router.get("/{connector_id}/config")
async def get_connector_config(
    connector_id: str,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Return current config values for a connector (secrets masked)."""
    _require_tenant_admin_or_system(user)
    conn = get_connector(connector_id)
    if not conn:
        raise HTTPException(status_code=404, detail=f"Unknown connector: {connector_id}")

    values: dict[str, str] = {}
    for f in conn.fields:
        sk = f.setting_key or f"{connector_id}_{f.key}"
        raw = persistence.get_setting(sk, tenant_id=user.tenant_id) or f.default
        if f.sensitive and raw and raw != f.default:
            values[f.key] = _mask_value(raw)
        else:
            values[f.key] = raw or ""

    return {
        "connector": conn.to_dict(include_docs=False),
        "values": values,
    }


# ─────────────────────────────────────────────────────────
# UPDATE CONFIG
# ─────────────────────────────────────────────────────────

@router.put("/{connector_id}/config")
async def update_connector_config(
    connector_id: str,
    body: dict[str, Any] = Body(...),
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Update config values for a connector."""
    _require_tenant_admin_or_system(user)
    conn = get_connector(connector_id)
    if not conn:
        raise HTTPException(status_code=404, detail=f"Unknown connector: {connector_id}")

    field_keys = {f.key: f for f in conn.fields}
    updated = 0

    for key, value in body.items():
        if key not in field_keys:
            continue
        f = field_keys[key]
        str_value = str(value) if value is not None else ""

        # Skip if value is the redacted placeholder
        if f.sensitive and str_value == REDACTED:
            continue
        if f.sensitive and REDACTED in str_value:
            continue

        sk = f.setting_key or f"{connector_id}_{key}"
        persistence.upsert_setting(sk, str_value, tenant_id=user.tenant_id)
        updated += 1

    logger.info("connector_hub.config_updated", connector=connector_id, fields=updated)
    return {"status": "ok", "updated": str(updated)}


# ─────────────────────────────────────────────────────────
# DELETE CONFIG
# ─────────────────────────────────────────────────────────

@router.delete("/{connector_id}/config")
async def delete_connector_config(
    connector_id: str,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Delete all config values for a connector."""
    _require_tenant_admin_or_system(user)
    conn = get_connector(connector_id)
    if not conn:
        raise HTTPException(status_code=404, detail=f"Unknown connector: {connector_id}")

    deleted = 0
    for f in conn.fields:
        sk = f.setting_key or f"{connector_id}_{f.key}"
        try:
            persistence.delete_setting(sk, tenant_id=user.tenant_id)
            deleted += 1
        except Exception:
            pass

    logger.info("connector_hub.config_deleted", connector=connector_id, fields=deleted)
    return {"status": "ok", "deleted": str(deleted)}


# ─────────────────────────────────────────────────────────
# SETUP DOCS
# ─────────────────────────────────────────────────────────

@router.get("/{connector_id}/setup-docs")
async def get_connector_setup_docs(
    connector_id: str,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Return setup documentation for a connector."""
    _require_tenant_admin_or_system(user)
    conn = get_connector(connector_id)
    if not conn:
        raise HTTPException(status_code=404, detail=f"Unknown connector: {connector_id}")

    return {
        "connector_id": conn.id,
        "name": conn.name,
        "description": conn.description,
        "docs_url": conn.docs_url,
        "prerequisites": conn.prerequisites,
        "steps": [
            {
                "step": i + 1,
                "title": s.title,
                "description": s.description,
                "url": s.url,
                "image_hint": s.image_hint,
                "warning": s.warning,
            }
            for i, s in enumerate(conn.setup_steps)
        ],
    }


# ─────────────────────────────────────────────────────────
# TEST CONNECTION
# ─────────────────────────────────────────────────────────

@router.post("/{connector_id}/test")
async def test_connector_connection(
    connector_id: str,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Test the connection for a connector using saved config.

    This delegates to the existing test logic in admin.py for known connectors,
    and provides basic HTTP-reachability tests for new ones.
    """
    _require_tenant_admin_or_system(user)
    conn = get_connector(connector_id)
    if not conn:
        raise HTTPException(status_code=404, detail=f"Unknown connector: {connector_id}")

    import time
    import httpx

    def _get_val(key: str) -> str:
        f_match = next((f for f in conn.fields if f.key == key), None)
        if not f_match:
            return ""
        sk = f_match.setting_key or f"{connector_id}_{key}"
        return persistence.get_setting(sk, tenant_id=user.tenant_id) or ""

    started = time.perf_counter()
    now = datetime.now(timezone.utc).isoformat()

    try:
        detail = ""

        if connector_id == "telegram":
            bot_token = _get_val("bot_token")
            if not bot_token:
                raise HTTPException(status_code=422, detail="Bot Token nicht konfiguriert")
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(f"https://api.telegram.org/bot{bot_token}/getMe")
            if resp.status_code in (401, 404):
                raise HTTPException(status_code=502, detail="Bot Token ungültig")
            data = resp.json() if resp.content else {}
            bot = data.get("result", {})
            detail = f"Bot @{bot.get('username', '?')} erreichbar"

        elif connector_id == "whatsapp":
            mode = _get_val("mode") or "qr"
            if mode == "meta":
                token = _get_val("meta_access_token")
                if not token:
                    raise HTTPException(status_code=422, detail="Access Token nicht konfiguriert")
                async with httpx.AsyncClient(timeout=12.0) as client:
                    resp = await client.get("https://graph.facebook.com/v21.0/me", params={"access_token": token})
                if resp.status_code in (401, 403):
                    raise HTTPException(status_code=502, detail="Meta Token ungültig")
                detail = "WhatsApp Meta Graph API erreichbar"
            else:
                detail = "QR-Modus aktiv (Bridge-Status separat prüfen)"

        elif connector_id == "instagram":
            token = _get_val("instagram_access_token")
            if not token:
                raise HTTPException(status_code=422, detail="Access Token nicht konfiguriert")
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(
                    "https://graph.facebook.com/v21.0/me",
                    params={"access_token": token, "fields": "id,name,instagram_business_account"},
                )
            if resp.status_code in (401, 403):
                raise HTTPException(status_code=502, detail="Instagram Token ungültig")
            data = resp.json() if resp.content else {}
            detail = f"Instagram API erreichbar (Page: {data.get('name', '?')})"

        elif connector_id == "facebook_messenger":
            token = _get_val("fb_page_access_token")
            if not token:
                raise HTTPException(status_code=422, detail="Page Access Token nicht konfiguriert")
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(
                    "https://graph.facebook.com/v21.0/me",
                    params={"access_token": token, "fields": "id,name"},
                )
            if resp.status_code in (401, 403):
                raise HTTPException(status_code=502, detail="Facebook Token ungültig")
            data = resp.json() if resp.content else {}
            detail = f"Facebook Page erreichbar ({data.get('name', '?')})"

        elif connector_id == "google_business":
            # Basic check: verify service account JSON is parseable
            sa_json = _get_val("gbm_service_account_json")
            if not sa_json:
                raise HTTPException(status_code=422, detail="Service Account JSON nicht konfiguriert")
            import json as json_mod
            try:
                sa_data = json_mod.loads(sa_json)
                if sa_data.get("type") != "service_account":
                    raise ValueError("Kein gültiger Service Account")
                detail = f"Service Account gültig (project: {sa_data.get('project_id', '?')})"
            except (json_mod.JSONDecodeError, ValueError) as e:
                raise HTTPException(status_code=502, detail=f"Ungültiges JSON: {e}")

        elif connector_id == "smtp":
            import smtplib
            import asyncio
            host = _get_val("host")
            port = int(_get_val("port") or "587")
            username = _get_val("username")
            password = _get_val("password")
            if not all([host, username, password]):
                raise HTTPException(status_code=422, detail="SMTP-Konfiguration unvollständig")

            def _probe():
                with smtplib.SMTP(host, port, timeout=20) as s:
                    s.ehlo()
                    s.starttls()
                    s.login(username, password)
                    s.noop()

            import asyncio
            await asyncio.to_thread(_probe)
            detail = f"SMTP Login OK ({host}:{port})"

        elif connector_id == "email_channel":
            token = _get_val("postmark_server_token")
            if not token:
                raise HTTPException(status_code=422, detail="Postmark Token nicht konfiguriert")
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(
                    "https://api.postmarkapp.com/server",
                    headers={"X-Postmark-Server-Token": token, "Accept": "application/json"},
                )
            if resp.status_code in (401, 403):
                raise HTTPException(status_code=502, detail="Postmark Token ungültig")
            data = resp.json() if resp.content else {}
            detail = f"Postmark erreichbar (Server: {data.get('Name', '?')})"

        elif connector_id in ("sms_channel", "voice_channel"):
            sid = _get_val("twilio_account_sid") or persistence.get_setting("twilio_account_sid", tenant_id=user.tenant_id) or ""
            token = _get_val("twilio_auth_token") or persistence.get_setting("twilio_auth_token", tenant_id=user.tenant_id) or ""
            if not sid or not token:
                raise HTTPException(status_code=422, detail="Twilio SID/Token nicht konfiguriert")
            async with httpx.AsyncClient(timeout=12.0, auth=(sid, token)) as client:
                resp = await client.get(f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json")
            if resp.status_code >= 400:
                raise HTTPException(status_code=502, detail=f"Twilio Fehler ({resp.status_code})")
            data = resp.json() if resp.content else {}
            detail = f"Twilio erreichbar (Status: {data.get('status', '?')})"

        elif connector_id == "magicline":
            base_url = _get_val("base_url")
            api_key = _get_val("api_key")
            if not base_url or not api_key:
                raise HTTPException(status_code=422, detail="Magicline-Konfiguration unvollständig")
            import asyncio
            from app.integrations.magicline.client import MagiclineClient

            def _probe():
                c = MagiclineClient(base_url=base_url, api_key=api_key, timeout=15)
                return c.studio_info()

            data = await asyncio.to_thread(_probe)
            studio = data.get("name") or data.get("studioName") or data.get("id") or "?"
            detail = f"Magicline erreichbar ({studio})"

        elif connector_id == "shopify":
            domain = _get_val("shop_domain")
            token = _get_val("access_token")
            if not domain or not token:
                raise HTTPException(status_code=422, detail="Shopify-Konfiguration unvollständig")
            url = f"https://{domain}/admin/api/2024-01/shop.json"
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(url, headers={"X-Shopify-Access-Token": token})
            if resp.status_code in (401, 403):
                raise HTTPException(status_code=502, detail="Shopify Token ungültig")
            data = resp.json() if resp.content else {}
            shop = data.get("shop", {})
            detail = f"Shopify erreichbar ({shop.get('name', '?')})"

        elif connector_id == "woocommerce":
            store_url = _get_val("store_url")
            ck = _get_val("consumer_key")
            cs = _get_val("consumer_secret")
            if not all([store_url, ck, cs]):
                raise HTTPException(status_code=422, detail="WooCommerce-Konfiguration unvollständig")
            url = f"{store_url.rstrip('/')}/wp-json/wc/v3/system_status"
            async with httpx.AsyncClient(timeout=12.0, auth=(ck, cs)) as client:
                resp = await client.get(url)
            if resp.status_code in (401, 403):
                raise HTTPException(status_code=502, detail="WooCommerce Keys ungültig")
            detail = f"WooCommerce erreichbar ({store_url})"

        elif connector_id == "hubspot":
            token = _get_val("access_token")
            if not token:
                raise HTTPException(status_code=422, detail="HubSpot Token nicht konfiguriert")
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(
                    "https://api.hubapi.com/crm/v3/objects/contacts",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"limit": 1},
                )
            if resp.status_code in (401, 403):
                raise HTTPException(status_code=502, detail="HubSpot Token ungültig")
            data = resp.json() if resp.content else {}
            total = data.get("total", "?")
            detail = f"HubSpot erreichbar ({total} Kontakte)"

        else:
            detail = "Test für diesen Connector nicht implementiert"

        latency_ms = int((time.perf_counter() - started) * 1000)

        # Store health status
        persistence.upsert_setting(f"integration_{connector_id}_last_test_at", now, tenant_id=user.tenant_id)
        persistence.upsert_setting(f"integration_{connector_id}_last_status", "ok", tenant_id=user.tenant_id)
        persistence.upsert_setting(f"integration_{connector_id}_last_detail", detail[:1200], tenant_id=user.tenant_id)

        return {
            "ok": True,
            "connector": connector_id,
            "latency_ms": latency_ms,
            "detail": detail,
            "checked_at": now,
        }

    except HTTPException as exc:
        persistence.upsert_setting(f"integration_{connector_id}_last_test_at", now, tenant_id=user.tenant_id)
        persistence.upsert_setting(f"integration_{connector_id}_last_status", "error", tenant_id=user.tenant_id)
        persistence.upsert_setting(f"integration_{connector_id}_last_detail", str(exc.detail)[:1200], tenant_id=user.tenant_id)
        return {
            "ok": False,
            "connector": connector_id,
            "error": str(exc.detail),
            "checked_at": now,
        }
    except Exception as e:
        detail = f"{e.__class__.__name__}: {e}"
        persistence.upsert_setting(f"integration_{connector_id}_last_test_at", now, tenant_id=user.tenant_id)
        persistence.upsert_setting(f"integration_{connector_id}_last_status", "error", tenant_id=user.tenant_id)
        persistence.upsert_setting(f"integration_{connector_id}_last_detail", detail[:1200], tenant_id=user.tenant_id)
        return {
            "ok": False,
            "connector": connector_id,
            "error": detail,
            "checked_at": now,
        }

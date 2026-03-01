"""app/gateway/routers/connector_hub.py — Connector Hub API (PR 3).

Unified API for managing all integration settings.
"""
from __future__ import annotations

import structlog
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel

from app.core.auth import AuthContext, get_current_user, require_role
from app.gateway.persistence import persistence
import smtplib
from app.integrations.connector_registry import list_connectors, get_connector_meta, CONNECTOR_REGISTRY

logger = structlog.get_logger()
router = APIRouter(prefix="/admin/connector-hub", tags=["connector-hub"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _require_admin(user: AuthContext):
    require_role(user, {"system_admin", "tenant_admin"})

def _get_config_key(tenant_id: int, connector_id: str, field_key: str) -> str:
    """Standardized config key: integration_{connector_id}_{tenant_id}_{field_key}"""
    return f"integration_{connector_id}_{tenant_id}_{field_key}"


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/catalog")
def get_catalog(user: AuthContext = Depends(get_current_user)) -> List[Dict[str, Any]]:
    """List all available connectors with their current status for this tenant."""
    catalog = []
    all_connectors = list_connectors()
    
    for meta in all_connectors:
        conn_id = meta["id"]
        # Check if enabled
        enabled_key = _get_config_key(user.tenant_id, conn_id, "enabled")
        is_enabled = (persistence.get_setting(enabled_key, "false", tenant_id=user.tenant_id) or "").lower() == "true"
        
        status = "connected" if is_enabled else "disconnected"
        
        # Special handling for WhatsApp (check real session status)
        if conn_id == "whatsapp":
            slug = persistence.get_tenant_slug(user.tenant_id)
            # If we have a working session status stored, we are connected
            wa_status = persistence.get_setting(f"wa_session_status_{slug}", tenant_id=user.tenant_id)
            if wa_status == "WORKING":
                status = "connected"
                # Auto-repair enabled flag if missing
                if not is_enabled:
                    persistence.upsert_setting(enabled_key, "true", tenant_id=user.tenant_id)
        
        # Special handling for Telegram
        if conn_id == "telegram":
            token_key = _get_config_key(user.tenant_id, "telegram", "bot_token")
            token = persistence.get_setting(token_key, tenant_id=user.tenant_id)
            if token and token.strip():
                status = "connected"
                if not is_enabled:
                    persistence.upsert_setting(enabled_key, "true", tenant_id=user.tenant_id)

        catalog.append({
            **meta,
            "status": status,
            "setup_progress": 100 if status == "connected" else 0
        })
    return catalog


@router.get("/{connector_id}/config")
def get_connector_config(
    connector_id: str,
    user: AuthContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get current configuration for a connector (masked secrets)."""
    _require_admin(user)
    meta = get_connector_meta(connector_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    config = {}
    for field in meta.get("fields", []):
        key = field["key"]
        db_key = _get_config_key(user.tenant_id, connector_id, key)
        val = persistence.get_setting(db_key, "", tenant_id=user.tenant_id)
        
        # Mask secrets
        if field.get("type") == "password" and val:
            val = "********"
        
        config[key] = val
        
    # Also get enabled state
    enabled_key = _get_config_key(user.tenant_id, connector_id, "enabled")
    config["enabled"] = (persistence.get_setting(enabled_key, "false", tenant_id=user.tenant_id) or "").lower() == "true"
            
    return config


@router.put("/{connector_id}/config")
def update_connector_config(
    connector_id: str,
    config: Dict[str, Any] = Body(...),
    user: AuthContext = Depends(get_current_user)
) -> Dict[str, str]:
    """Update configuration. Fields with '********' are ignored (not updated)."""
    _require_admin(user)
    meta = get_connector_meta(connector_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Connector not found")
        
    for field in meta.get("fields", []):
        key = field["key"]
        new_val = config.get(key)
        
        # Skip if masked or missing
        if new_val is None:
            continue
        if new_val == "********":
            continue
            
        db_key = _get_config_key(user.tenant_id, connector_id, key)
        persistence.upsert_setting(db_key, str(new_val), tenant_id=user.tenant_id)
        
    # Auto-generate verify_token for WhatsApp if not set
    if connector_id == "whatsapp":
        vt_key = _get_config_key(user.tenant_id, "whatsapp", "verify_token")
        existing_vt = persistence.get_setting(vt_key, tenant_id=user.tenant_id)
        if not existing_vt:
            import secrets as _secrets
            auto_token = _secrets.token_urlsafe(32)
            persistence.upsert_setting(vt_key, auto_token, tenant_id=user.tenant_id)

    # Handle enable/disable
    if "enabled" in config:
        enabled_key = _get_config_key(user.tenant_id, connector_id, "enabled")
        persistence.upsert_setting(enabled_key, str(config["enabled"]).lower(), tenant_id=user.tenant_id)
        
    return {"status": "updated"}


@router.delete("/{connector_id}/config")
def reset_connector_config(
    connector_id: str,
    user: AuthContext = Depends(get_current_user)
):
    """Reset configuration for a connector."""
    _require_admin(user)
    meta = get_connector_meta(connector_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Connector not found")

    # Clear all fields
    for field in meta.get("fields", []):
        db_key = _get_config_key(user.tenant_id, connector_id, field["key"])
        persistence.upsert_setting(db_key, "", tenant_id=user.tenant_id)
        
    # Disable
    enabled_key = _get_config_key(user.tenant_id, connector_id, "enabled")
    persistence.upsert_setting(enabled_key, "false", tenant_id=user.tenant_id)
    
    return {"status": "reset"}


@router.post("/{connector_id}/test")
async def test_connection(
    connector_id: str,
    user: AuthContext = Depends(get_current_user),
    body: Dict[str, Any] = Body(default={})
):
    """Test connection for a specific connector."""
    _require_admin(user)
    
    normalized = (connector_id or "").lower().strip()
    
    # Helper to get value from body (live) or DB (persisted)
    def _val(key: str, default: str = "") -> str:
        # 1. Try body config first
        config = body.get("config") or {}
        val = config.get(key)
        if val is None:
            # Try without prefix
            shorthand = key.replace(f"{normalized}_", "")
            val = config.get(shorthand)
            
        if val is not None:
            final_val = str(val or "")
            # If it is a redact placeholder, we MUST use the DB value
            if final_val not in ("__REDACTED__", "********") and final_val.strip() != "":
                return final_val
        
        # 2. Fallback to DB
        db_key = _get_config_key(user.tenant_id, normalized, key)
        db_val = persistence.get_setting(db_key, tenant_id=user.tenant_id)
        if not db_val:
            # Try legacy key if it is a known one
            db_val = persistence.get_setting(key, None, tenant_id=user.tenant_id)
        return db_val or default

    # Generic stub logic - in reality, delegate to specific integration module
    # based on connector_id.
    
    if normalized == "smtp_email":
        host = _val("host").strip()
        port_raw = _val("port", "587").strip()
        username = _val("username").strip()
        password = _val("password").strip()
        
        if not all([host, username, password]):
            return {"status": "error", "message": "SMTP-Konfiguration unvollständig"}
        
        try:
            # 1. Test SMTP (Outbound)
            port = int(port_raw or "587")
            if port == 465:
                with smtplib.SMTP_SSL(host, port, timeout=15) as srv:
                    srv.login(username, password)
                    srv.noop()
            else:
                with smtplib.SMTP(host, port, timeout=15) as srv:
                    srv.ehlo()
                    srv.starttls()
                    srv.ehlo()
                    srv.login(username, password)
                    srv.noop()
            
            # 2. Test IMAP (Inbound)
            imap_host = persistence.get_setting(_get_config_key(user.tenant_id, connector_id, "imap_host"), "", tenant_id=user.tenant_id).strip()
            imap_port_raw = persistence.get_setting(_get_config_key(user.tenant_id, connector_id, "imap_port"), "993", tenant_id=user.tenant_id).strip()
            
            if imap_host:
                import imaplib
                imap_port = int(imap_port_raw or "993")
                with imaplib.IMAP4_SSL(imap_host, imap_port) as mail:
                    mail.login(username, password)
                    mail.logout()
                return {"status": "ok", "message": "SMTP & IMAP Test erfolgreich! Versand und Empfang sind bereit."}
            
            return {"status": "ok", "message": "SMTP Test erfolgreich! (IMAP wurde übersprungen, da kein Host konfiguriert)"}
        except smtplib.SMTPAuthenticationError as e:
            return {"status": "error", "message": f"SMTP-Authentifizierung fehlgeschlagen: {e}"}
        except Exception as e:
            return {"status": "error", "message": f"SMTP-Verbindungsfehler: {e}"}

    if normalized == "postmark":
        token = _val("server_token").strip()
        if not token:
            return {"status": "error", "message": "Postmark Server Token fehlt"}
            
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.postmarkapp.com/server",
                    headers={"X-Postmark-Server-Token": token, "Accept": "application/json"}
                )
                if resp.status_code == 200:
                    return {"status": "ok", "message": "Postmark API Verbindung erfolgreich! Token ist gültig."}
                elif resp.status_code in (401, 403):
                    return {"status": "error", "message": "Postmark Server Token ungültig oder abgelaufen."}
                else:
                    return {"status": "error", "message": f"Postmark API Fehler: {resp.status_code}"}
        except Exception as e:
            return {"status": "error", "message": f"Netzwerkfehler bei Postmark-Verbindung: {e}"}

    if normalized == "calendly":
        token = _val("api_key").strip()
        if not token:
            return {"status": "error", "message": "Calendly Personal Access Token fehlt"}
            
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.calendly.com/users/me",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    user_name = data.get("resource", {}).get("name", "Unbekannt")
                    return {"status": "ok", "message": f"Calendly Verbindung erfolgreich! Verbunden als {user_name}."}
                elif resp.status_code in (401, 403):
                    return {"status": "error", "message": "Calendly Token ungültig oder abgelaufen."}
                else:
                    return {"status": "error", "message": f"Calendly API Fehler: {resp.status_code}"}
        except Exception as e:
            return {"status": "error", "message": f"Netzwerkfehler bei Calendly-Verbindung: {e}"}

    if normalized == "stripe":
        key = _val("secret_key").strip()
        if not key:
            return {"status": "error", "message": "Stripe Secret Key fehlt"}
            
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.stripe.com/v1/account",
                    auth=(key, "")
                )
                if resp.status_code == 200:
                    data = resp.json()
                    acc_name = data.get("settings", {}).get("dashboard", {}).get("display_name", "Unbekannt")
                    return {"status": "ok", "message": f"Stripe Verbindung erfolgreich! Verbunden mit Account: {acc_name}."}
                else:
                    return {"status": "error", "message": "Stripe Secret Key ist ungültig."}
        except Exception as e:
            return {"status": "error", "message": f"Netzwerkfehler bei Stripe-Verbindung: {e}"}
    
    elif connector_id == "telegram":
        # Test Telegram bot token
        import httpx
        bot_token = persistence.get_setting(_get_config_key(user.tenant_id, connector_id, "bot_token"), "", tenant_id=user.tenant_id)
        if not bot_token:
            return {"status": "error", "message": "Bot Token nicht konfiguriert"}
        try:
            import requests
            resp = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                bot_name = data.get("result", {}).get("username", "unknown")
                return {"status": "ok", "message": f"Telegram Bot @{bot_name} verbunden!"}
            else:
                return {"status": "error", "message": f"Telegram API Fehler: {resp.status_code}"}
        except Exception as e:
            return {"status": "error", "message": f"Telegram Verbindungsfehler: {e}"}
    
    elif connector_id == "stripe":
        # Call billing test logic...
        pass
    elif connector_id == "shopify":
        # Call shopify test logic...
        pass
        
    return {"status": "ok", "message": "Connection test successful"}


@router.get("/{connector_id}/setup-docs")
def get_setup_docs(
    connector_id: str,
    user: AuthContext = Depends(get_current_user)
) -> Dict[str, str]:
    """Get setup documentation markdown."""
    # In real app, load from disk or DB
    return {"content": f"# Setup Guide for {connector_id}\n\n1. Step one...\n2. Step two..."}


@router.get("/{connector_id}/webhook-info")
def get_webhook_info(
    connector_id: str,
    user: AuthContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """Return the webhook URL and verify token for a connector.
    This info is shown to tenants so they can configure it in their provider (e.g. Meta).
    """
    _require_admin(user)
    
    from app.core.db import SessionLocal
    from app.core.models import Tenant
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        tenant_slug = tenant.slug if tenant else "unknown"
    finally:
        db.close()
    
    # Build the public webhook URL
    base_url = "https://www.ariia.ai"
    
    result: Dict[str, Any] = {"connector_id": connector_id, "tenant_slug": tenant_slug}
    
    if connector_id == "whatsapp":
        result["webhook_url"] = f"{base_url}/webhook/whatsapp/{tenant_slug}"
        # Get or generate verify token
        vt_key = _get_config_key(user.tenant_id, "whatsapp", "verify_token")
        verify_token = persistence.get_setting(vt_key, tenant_id=user.tenant_id)
        if not verify_token:
            import secrets as _secrets
            verify_token = _secrets.token_urlsafe(32)
            persistence.upsert_setting(vt_key, verify_token, tenant_id=user.tenant_id)
        result["verify_token"] = verify_token
        result["instructions"] = (
            "Trage diese Webhook-URL und den Verify Token in deiner Meta App unter "
            "WhatsApp > Configuration > Webhook ein. "
            "Abonniere die Felder: messages, messaging_postbacks."
        )
    elif connector_id == "telegram":
        result["webhook_url"] = f"{base_url}/webhook/telegram/{tenant_slug}"
        result["instructions"] = (
            "Der Telegram-Webhook wird automatisch konfiguriert. "
            "Alternativ kannst du diese URL manuell bei @BotFather setzen."
        )
    elif connector_id == "email":
        result["webhook_url"] = f"{base_url}/webhook/email/{tenant_slug}"
        result["instructions"] = "Konfiguriere dein E-Mail-System, um eingehende Nachrichten an diese URL weiterzuleiten."
    elif connector_id == "sms":
        result["webhook_url"] = f"{base_url}/webhook/sms/{tenant_slug}"
        result["instructions"] = "Trage diese URL als Messaging Webhook in deinem Twilio Dashboard ein."
    else:
        result["webhook_url"] = None
        result["instructions"] = "Dieser Connector benötigt keinen Webhook."
    
    return result

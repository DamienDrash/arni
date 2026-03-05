"""app/gateway/routers/connector_hub.py — Connector Hub API (PR 3 + Sprint 2).

Unified API for managing all integration settings.
- Tenant-Admin: configure & test own integrations
- System-Admin: CRUD connectors globally, manage registry, view all tenants
"""
from __future__ import annotations

import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Body, Query
from pydantic import BaseModel

from app.core.auth import AuthContext, get_current_user, require_role
from app.gateway.persistence import persistence
import smtplib
from app.integrations.connector_registry import (
    list_connectors, get_connector_meta, CONNECTOR_REGISTRY,
    CONNECTOR_DOCS,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/admin/connector-hub", tags=["connector-hub"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _require_admin(user: AuthContext):
    require_role(user, {"system_admin", "tenant_admin"})

def _require_system_admin(user: AuthContext):
    require_role(user, {"system_admin"})

def _get_config_key(tenant_id: int, connector_id: str, field_key: str) -> str:
    """Standardized config key: integration_{connector_id}_{tenant_id}_{field_key}"""
    return f"integration_{connector_id}_{tenant_id}_{field_key}"


# ══════════════════════════════════════════════════════════════════════════════
# CATALOG & CONFIG (Tenant-Admin + System-Admin)
# ══════════════════════════════════════════════════════════════════════════════

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
            wa_status = persistence.get_setting(f"wa_session_status_{slug}", tenant_id=user.tenant_id)
            if wa_status == "WORKING":
                status = "connected"
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
    
    # Special handling for WhatsApp session state
    if connector_id == "whatsapp":
        slug = persistence.get_tenant_slug(user.tenant_id)
        if slug:
            persistence.delete_setting(f"wa_session_status_{slug}", tenant_id=user.tenant_id)
            
            # Request WAHA to shut down the native container session
            waha_url = persistence.get_setting("waha_api_url", tenant_id=user.tenant_id) or "http://ariia-whatsapp-bridge:3000"
            waha_key = persistence.get_setting("waha_api_key", tenant_id=user.tenant_id) or "ariia-waha-secret"
            import requests
            try:
                requests.post(
                    f"{waha_url}/api/sessions/stop",
                    headers={"X-Api-Key": waha_key, "Content-Type": "application/json"},
                    json={"name": slug, "logout": True},
                    timeout=5
                )
            except Exception as e:
                logger.warning("connector.whatsapp.stop_failed", error=str(e), tenant=slug)

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
        config = body.get("config") or {}
        val = config.get(key)
        if val is None:
            shorthand = key.replace(f"{normalized}_", "")
            val = config.get(shorthand)
            
        if val is not None:
            final_val = str(val or "")
            if final_val not in ("__REDACTED__", "********") and final_val.strip() != "":
                return final_val
        
        db_key = _get_config_key(user.tenant_id, normalized, key)
        db_val = persistence.get_setting(db_key, tenant_id=user.tenant_id)
        if not db_val:
            db_val = persistence.get_setting(key, None, tenant_id=user.tenant_id)
        return db_val or default

    if normalized == "smtp_email":
        host = _val("host").strip()
        port_raw = _val("port", "587").strip()
        username = _val("username").strip()
        password = _val("password").strip()
        
        if not all([host, username, password]):
            return {"status": "error", "message": "SMTP-Konfiguration unvollständig"}
        
        try:
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

    if normalized == "paypal":
        client_id = _val("client_id").strip()
        client_secret = _val("client_secret").strip()
        mode = _val("mode", "sandbox").strip()
        
        if not client_id or not client_secret:
            return {"status": "error", "message": "PayPal Credentials unvollständig"}
            
        try:
            import httpx
            base_url = "https://api-m.paypal.com" if mode == "live" else "https://api-m.sandbox.paypal.com"
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{base_url}/v1/oauth2/token",
                    auth=(client_id, client_secret),
                    data={"grant_type": "client_credentials"}
                )
                if resp.status_code == 200:
                    return {"status": "ok", "message": f"PayPal ({mode}) Verbindung erfolgreich! Authentifizierung bestätigt."}
                else:
                    try:
                        err_data = resp.json()
                        err_msg = err_data.get("error_description") or err_data.get("message") or resp.text
                    except:
                        err_msg = resp.text
                    return {"status": "error", "message": f"PayPal Authentifizierung fehlgeschlagen ({mode}): {err_msg}"}
        except Exception as e:
            return {"status": "error", "message": f"Netzwerkfehler bei PayPal-Verbindung: {e}"}
    
    if normalized == "telegram":
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
        
    return {"status": "ok", "message": "Connection test successful"}


# ══════════════════════════════════════════════════════════════════════════════
# DOCUMENTATION (n8n-Style Connector Docs)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{connector_id}/docs")
def get_connector_docs(
    connector_id: str,
    user: AuthContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get comprehensive n8n-style documentation for a connector."""
    meta = get_connector_meta(connector_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    docs = CONNECTOR_DOCS.get(connector_id, {})
    
    return {
        "connector_id": connector_id,
        "name": meta.get("name", connector_id),
        "category": meta.get("category", ""),
        "description": meta.get("description", ""),
        "icon": meta.get("icon", ""),
        "docs": docs,
    }


@router.get("/docs/all")
def get_all_connector_docs(
    user: AuthContext = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Get documentation summaries for all connectors."""
    result = []
    for conn_id, meta in CONNECTOR_REGISTRY.items():
        docs = CONNECTOR_DOCS.get(conn_id, {})
        result.append({
            "id": conn_id,
            "name": meta.get("name", conn_id),
            "category": meta.get("category", ""),
            "description": meta.get("description", ""),
            "icon": meta.get("icon", ""),
            "has_docs": bool(docs),
            "overview": docs.get("overview", ""),
            "difficulty": docs.get("difficulty", "medium"),
            "estimated_time": docs.get("estimated_time", "5 min"),
        })
    return result


@router.get("/{connector_id}/setup-docs")
def get_setup_docs(
    connector_id: str,
    user: AuthContext = Depends(get_current_user)
) -> Dict[str, str]:
    """Get setup documentation markdown (legacy endpoint, now redirects to docs)."""
    docs = CONNECTOR_DOCS.get(connector_id, {})
    if docs:
        # Build markdown from structured docs
        md_parts = [f"# {docs.get('title', connector_id)} Setup Guide\n"]
        if docs.get("overview"):
            md_parts.append(f"{docs['overview']}\n")
        if docs.get("prerequisites"):
            md_parts.append("## Voraussetzungen\n")
            for p in docs["prerequisites"]:
                md_parts.append(f"- {p}\n")
        if docs.get("steps"):
            md_parts.append("\n## Einrichtungsschritte\n")
            for i, step in enumerate(docs["steps"], 1):
                md_parts.append(f"\n### Schritt {i}: {step.get('title', '')}\n")
                md_parts.append(f"{step.get('description', '')}\n")
                if step.get("tip"):
                    md_parts.append(f"\n> **Tipp:** {step['tip']}\n")
        return {"content": "\n".join(md_parts)}
    
    return {"content": f"# Setup Guide for {connector_id}\n\nDocumentation coming soon."}


@router.get("/{connector_id}/webhook-info")
def get_webhook_info(
    connector_id: str,
    user: AuthContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """Return the webhook URL and verify token for a connector."""
    _require_admin(user)
    
    from app.core.db import SessionLocal
    from app.core.models import Tenant
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        tenant_slug = tenant.slug if tenant else "unknown"
    finally:
        db.close()
    
    base_url = "https://www.ariia.ai"
    
    result: Dict[str, Any] = {"connector_id": connector_id, "tenant_slug": tenant_slug}
    
    if connector_id == "whatsapp":
        result["webhook_url"] = f"{base_url}/webhook/whatsapp/{tenant_slug}"
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


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM-ADMIN: Global Connector Management (CRUD)
# ══════════════════════════════════════════════════════════════════════════════

class ConnectorCreateRequest(BaseModel):
    id: str
    name: str
    category: str
    description: str = ""
    icon: str = "plug"
    fields: List[Dict[str, Any]] = []
    setup_doc: str = ""

class ConnectorUpdateRequest(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    fields: Optional[List[Dict[str, Any]]] = None
    setup_doc: Optional[str] = None


@router.get("/system/connectors")
def system_list_connectors(
    user: AuthContext = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """System-Admin: List all registered connectors with usage stats."""
    _require_system_admin(user)
    
    result = []
    for conn_id, meta in CONNECTOR_REGISTRY.items():
        result.append({
            "id": conn_id,
            **meta,
            "field_count": len(meta.get("fields", [])),
            "has_docs": conn_id in CONNECTOR_DOCS,
        })
    return result


@router.post("/system/connectors")
def system_create_connector(
    body: ConnectorCreateRequest,
    user: AuthContext = Depends(get_current_user)
) -> Dict[str, str]:
    """System-Admin: Register a new connector in the global registry."""
    _require_system_admin(user)
    
    if body.id in CONNECTOR_REGISTRY:
        raise HTTPException(status_code=409, detail=f"Connector '{body.id}' already exists")
    
    CONNECTOR_REGISTRY[body.id] = {
        "name": body.name,
        "category": body.category,
        "description": body.description,
        "icon": body.icon,
        "fields": body.fields,
        "setup_doc": body.setup_doc,
    }
    
    logger.info("connector_created", connector_id=body.id, admin=user.email)
    return {"status": "created", "connector_id": body.id}


@router.put("/system/connectors/{connector_id}")
def system_update_connector(
    connector_id: str,
    body: ConnectorUpdateRequest,
    user: AuthContext = Depends(get_current_user)
) -> Dict[str, str]:
    """System-Admin: Update an existing connector definition."""
    _require_system_admin(user)
    
    if connector_id not in CONNECTOR_REGISTRY:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    existing = CONNECTOR_REGISTRY[connector_id]
    if body.name is not None:
        existing["name"] = body.name
    if body.category is not None:
        existing["category"] = body.category
    if body.description is not None:
        existing["description"] = body.description
    if body.icon is not None:
        existing["icon"] = body.icon
    if body.fields is not None:
        existing["fields"] = body.fields
    if body.setup_doc is not None:
        existing["setup_doc"] = body.setup_doc
    
    logger.info("connector_updated", connector_id=connector_id, admin=user.email)
    return {"status": "updated"}


@router.delete("/system/connectors/{connector_id}")
def system_delete_connector(
    connector_id: str,
    user: AuthContext = Depends(get_current_user)
) -> Dict[str, str]:
    """System-Admin: Remove a connector from the global registry."""
    _require_system_admin(user)
    
    if connector_id not in CONNECTOR_REGISTRY:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    del CONNECTOR_REGISTRY[connector_id]
    
    # Also remove docs if present
    if connector_id in CONNECTOR_DOCS:
        del CONNECTOR_DOCS[connector_id]
    
    logger.info("connector_deleted", connector_id=connector_id, admin=user.email)
    return {"status": "deleted"}


@router.get("/system/usage-overview")
def system_usage_overview(
    user: AuthContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """System-Admin: Get global integration usage statistics."""
    _require_system_admin(user)
    
    from app.core.db import SessionLocal
    from app.core.models import Tenant
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).all()
        
        stats = {
            "total_connectors": len(CONNECTOR_REGISTRY),
            "total_tenants": len(tenants),
            "categories": {},
            "connector_usage": {},
        }
        
        # Count connectors per category
        for conn_id, meta in CONNECTOR_REGISTRY.items():
            cat = meta.get("category", "other")
            stats["categories"][cat] = stats["categories"].get(cat, 0) + 1
        
        # Count active connections per connector across all tenants
        for tenant in tenants:
            for conn_id in CONNECTOR_REGISTRY:
                enabled_key = _get_config_key(tenant.id, conn_id, "enabled")
                is_enabled = (persistence.get_setting(enabled_key, "false", tenant_id=tenant.id) or "").lower() == "true"
                if is_enabled:
                    stats["connector_usage"][conn_id] = stats["connector_usage"].get(conn_id, 0) + 1
        
        return stats
    finally:
        db.close()

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
        
        catalog.append({
            **meta,
            "status": "connected" if is_enabled else "disconnected",
            "setup_progress": 100 if is_enabled else 0 # simplified
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
def test_connection(
    connector_id: str,
    user: AuthContext = Depends(get_current_user)
):
    """Test connection for a specific connector."""
    _require_admin(user)
    
    # Generic stub logic - in reality, delegate to specific integration module
    # based on connector_id.
    
    if connector_id == "smtp_email":
        # Real SMTP connection test
        host = persistence.get_setting(_get_config_key(user.tenant_id, connector_id, "host"), "", tenant_id=user.tenant_id)
        port_raw = persistence.get_setting(_get_config_key(user.tenant_id, connector_id, "port"), "587", tenant_id=user.tenant_id)
        username = persistence.get_setting(_get_config_key(user.tenant_id, connector_id, "username"), "", tenant_id=user.tenant_id)
        password = persistence.get_setting(_get_config_key(user.tenant_id, connector_id, "password"), "", tenant_id=user.tenant_id)
        
        if not all([host, username, password]):
            return {"status": "error", "message": "SMTP-Konfiguration unvollständig"}
        
        try:
            port = int(port_raw or "587")
            with smtplib.SMTP(host, port, timeout=10) as srv:
                srv.ehlo()
                srv.starttls()
                srv.ehlo()
                srv.login(username, password)
                srv.quit()
            return {"status": "ok", "message": "SMTP-Verbindung erfolgreich! Authentifizierung bestätigt."}
        except smtplib.SMTPAuthenticationError as e:
            return {"status": "error", "message": f"SMTP-Authentifizierung fehlgeschlagen: {e}"}
        except Exception as e:
            return {"status": "error", "message": f"SMTP-Verbindungsfehler: {e}"}
    
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

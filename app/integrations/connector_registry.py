"""app/integrations/connector_registry.py — Connector Metadata Registry (PR 3).

Central definition of all integrations.
"""
from typing import List, Dict, Any

CONNECTOR_REGISTRY = {
    # ── Messaging ─────────────────────────────────────────────────────────────
    "whatsapp": {
        "name": "WhatsApp",
        "category": "messaging",
        "description": "Connect WhatsApp Business API via Meta Cloud.",
        "fields": [
            {"key": "mode", "label": "Mode", "type": "select", "options": ["qr", "api"]},
            {"key": "phone_number_id", "label": "Phone Number ID", "type": "text", "depends_on": "mode=api"},
            {"key": "access_token", "label": "Access Token", "type": "password", "depends_on": "mode=api"},
            {"key": "verify_token", "label": "Verify Token", "type": "text", "depends_on": "mode=api"},
            {"key": "app_secret", "label": "App Secret", "type": "password", "depends_on": "mode=api"},
        ],
        "setup_doc": "whatsapp.md",
        "icon": "whatsapp",
    },
    "telegram": {
        "name": "Telegram",
        "category": "messaging",
        "description": "Connect Telegram Bot API.",
        "fields": [
            {"key": "bot_token", "label": "Bot Token", "type": "password"},
            {"key": "admin_chat_id", "label": "Admin Chat ID", "type": "text", "optional": True},
        ],
        "setup_doc": "telegram.md",
        "icon": "telegram",
    },
    "sms": {
        "name": "SMS (Twilio)",
        "category": "messaging",
        "description": "Send and receive SMS via Twilio.",
        "fields": [
            {"key": "account_sid", "label": "Account SID", "type": "text"},
            {"key": "auth_token", "label": "Auth Token", "type": "password"},
            {"key": "phone_number", "label": "Twilio Phone Number", "type": "text"},
        ],
        "setup_doc": "sms.md",
        "icon": "message-circle",
    },
    
    # ── Members ───────────────────────────────────────────────────────────────
    "magicline": {
        "name": "Magicline",
        "category": "members",
        "description": "Sync members and check-ins from Magicline.",
        "fields": [
            {"key": "base_url", "label": "API Base URL", "type": "text"},
            {"key": "api_key", "label": "API Key", "type": "password"},
            {"key": "studio_id", "label": "Studio ID", "type": "text", "optional": True},
        ],
        "setup_doc": "magicline.md",
        "icon": "dumbbell",
    },
    "shopify": {
        "name": "Shopify",
        "category": "members",
        "description": "Sync customers from Shopify store.",
        "fields": [
            {"key": "domain", "label": "Shop Domain", "type": "text", "placeholder": "shop.myshopify.com"},
            {"key": "access_token", "label": "Admin API Token", "type": "password"},
        ],
        "setup_doc": "shopify.md",
        "icon": "shopping-bag",
    },
    
    # ── CRM ───────────────────────────────────────────────────────────────────
    "hubspot": {
        "name": "HubSpot",
        "category": "crm",
        "description": "Sync contacts with HubSpot CRM.",
        "fields": [
            {"key": "access_token", "label": "Private App Token", "type": "password"},
        ],
        "setup_doc": "hubspot.md",
        "icon": "users",
    },
}

def get_connector_meta(connector_id: str) -> Dict[str, Any] | None:
    return CONNECTOR_REGISTRY.get(connector_id)

def list_connectors() -> List[Dict[str, Any]]:
    return [{"id": k, **v} for k, v in CONNECTOR_REGISTRY.items()]

"""Shared dependencies for the Gateway routers.

Avoids circular imports by centralizing singleton initialization.
"""
import os
from typing import Optional

import structlog
from app.gateway.redis_bus import RedisBus
from app.gateway.persistence import persistence
from app.swarm.llm import LLMClient
from app.swarm.router.router import SwarmRouter
from app.integrations.telegram import TelegramBot
from app.integrations.whatsapp import WhatsAppClient
from config.settings import get_settings

logger = structlog.get_logger()
settings = get_settings()

# Initialize Singletons
redis_bus = RedisBus(redis_url=settings.redis_url)

# Swarm Components
# LLMClient can still be a global fallback if configured, but agents should use tenant keys.
llm_client = LLMClient(openai_api_key=settings.openai_api_key)
swarm_router = SwarmRouter(llm=llm_client)

# Active WebSockets (Ghost Mode)
active_websockets = []

def get_redis_bus() -> RedisBus:
    return redis_bus

def get_swarm_router() -> SwarmRouter:
    return swarm_router

def get_telegram_bot(tenant_id: int | None = None) -> TelegramBot:
    """Returns a tenant-aware TelegramBot instance."""
    token = ""
    admin_id = ""
    if tenant_id is not None:
        token = persistence.get_setting("telegram_bot_token", tenant_id=tenant_id) or ""
        admin_id = persistence.get_setting("telegram_admin_chat_id", tenant_id=tenant_id) or ""
    
    if not token:
        logger.warning("gateway.telegram_bot.missing_token", tenant_id=tenant_id)
        
    return TelegramBot(
        bot_token=token,
        admin_chat_id=admin_id,
    )

def _wa_setting(key: str, tenant_id: int) -> str:
    """Read WhatsApp setting from connector hub key, fallback to legacy key."""
    hub_key = f"integration_whatsapp_{tenant_id}_{key}"
    val = persistence.get_setting(hub_key, tenant_id=tenant_id)
    if val:
        return val
    legacy_map = {
        "access_token": "meta_access_token",
        "phone_number_id": "meta_phone_number_id",
        "app_secret": "meta_app_secret",
        "verify_token": "meta_verify_token",
    }
    legacy_key = legacy_map.get(key)
    if legacy_key:
        return persistence.get_setting(legacy_key, tenant_id=tenant_id) or ""
    return ""


def get_whatsapp_client(tenant_id: int | None = None) -> WhatsAppClient:
    """Returns a tenant-aware WhatsAppClient instance.
    Falls Meta Cloud Daten fehlen, wird die WAHA (WhatsApp Web) Konfiguration geladen.
    """
    token = ""
    phone_id = ""
    secret = ""
    waha_url = None
    waha_key = None
    
    if tenant_id is not None:
        token = _wa_setting("access_token", tenant_id)
        phone_id = _wa_setting("phone_number_id", tenant_id)
        secret = _wa_setting("app_secret", tenant_id)
        
        # Load WAHA bridge settings (Persistence first, then Env)
        waha_url = persistence.get_setting("waha_api_url", tenant_id=tenant_id)
        waha_key = persistence.get_setting("waha_api_key", tenant_id=tenant_id)
        
    # Global fallbacks if tenant-specific settings are missing
    if not waha_url:
        waha_url = "http://ariia-whatsapp-bridge:3000"
    if not waha_key:
        waha_key = "ariia-waha-secret"
        
    # If Meta token is missing, we prioritize WAHA
    if not token:
        # We nullify Meta fields to ensure WhatsAppClient chooses WAHA path
        return WhatsAppClient(
            access_token="",
            phone_number_id="",
            app_secret="",
            waha_api_url=waha_url,
            waha_api_key=waha_key
        )

    return WhatsAppClient(
        access_token=token,
        phone_number_id=phone_id,
        app_secret=secret,
        waha_api_url=waha_url,
        waha_api_key=waha_key
    )

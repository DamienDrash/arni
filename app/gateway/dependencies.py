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

def get_whatsapp_client(tenant_id: int | None = None) -> WhatsAppClient:
    """Returns a tenant-aware WhatsAppClient instance."""
    token = ""
    phone_id = ""
    secret = ""
    if tenant_id is not None:
        token = persistence.get_setting("meta_access_token", tenant_id=tenant_id) or ""
        phone_id = persistence.get_setting("meta_phone_number_id", tenant_id=tenant_id) or ""
        secret = persistence.get_setting("meta_app_secret", tenant_id=tenant_id) or ""

    return WhatsAppClient(
        access_token=token,
        phone_number_id=phone_id,
        app_secret=secret,
    )

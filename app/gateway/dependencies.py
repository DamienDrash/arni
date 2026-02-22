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
# TODO (Phase 3): Make LLMClient/Router per-request/tenant-aware
llm_client = LLMClient(openai_api_key=settings.openai_api_key)
swarm_router = SwarmRouter(llm=llm_client)

# Integration Clients
telegram_bot = TelegramBot(
    bot_token=settings.telegram_bot_token,
    admin_chat_id=settings.telegram_admin_chat_id,
)

whatsapp_verifier = WhatsAppClient(
    access_token=settings.meta_access_token,
    phone_number_id=settings.meta_phone_number_id,
    app_secret=settings.meta_app_secret,
)

# Active WebSockets (Ghost Mode)
active_websockets = []

def get_redis_bus() -> RedisBus:
    return redis_bus

def get_swarm_router() -> SwarmRouter:
    return swarm_router

def get_telegram_bot() -> TelegramBot:
    return telegram_bot

def get_whatsapp_client() -> WhatsAppClient:
    return whatsapp_verifier

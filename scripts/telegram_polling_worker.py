"""Multi-Tenant Telegram Polling Worker (Enterprise Edition).

Uses service discovery and resilient forwarding to ensure messages reach
the gateway regardless of internal IP changes.
"""
import asyncio
import os
import structlog
import httpx
from datetime import datetime, timezone

from config.settings import get_settings
from app.core.db import SessionLocal
from app.core.models import Tenant
from app.gateway.persistence import persistence
from app.integrations.telegram import TelegramBot

logger = structlog.get_logger()
settings = get_settings()

# Service Discovery - Use the docker service name
GATEWAY_URL = "http://ariia-core:8000"

async def forward_update(bot_token: str, tenant_slug: str, update: dict):
    """Forward a single update to the tenant-specific webhook endpoint."""
    url = f"{GATEWAY_URL}/webhook/telegram/{tenant_slug}"
    
    # 1. Fetch secret directly with explicit tenant_id
    db = SessionLocal()
    headers = {"Content-Type": "application/json"}
    try:
        t = db.query(Tenant).filter(Tenant.slug == tenant_slug).first()
        if t:
            # Bypass auto-resolution by passing tenant_id explicitly
            tenant_secret = persistence.get_setting("telegram_webhook_secret", tenant_id=t.id)
            if tenant_secret:
                headers["x-telegram-webhook-secret"] = tenant_secret
    finally:
        db.close()

    # 2. Forward with exponential backoff if backend is temporarily unreachable
    async with httpx.AsyncClient(timeout=15.0) as client:
        for attempt in range(5):
            try:
                resp = await client.post(url, json=update, headers=headers)
                if resp.status_code < 400:
                    logger.info("polling.forward_success", tenant=tenant_slug, update_id=update.get("update_id"))
                    return
                else:
                    logger.error("polling.forward_failed", status=resp.status_code, tenant=tenant_slug, body=resp.text[:100])
                    break # Usually authentication or 404, don't retry
            except Exception as e:
                wait_time = 2 ** attempt
                logger.error("polling.network_retry", error=str(e), tenant=tenant_slug, wait=wait_time)
                await asyncio.sleep(wait_time)

async def poll_bot(tenant_id: int, tenant_slug: str, token: str):
    """Independently poll a specific bot."""
    bot = TelegramBot(bot_token=token)
    offset = None
    
    logger.info("polling.bot_worker.started", tenant=tenant_slug)
    
    try:
        # Clear webhook to allow polling mode
        await bot.delete_webhook()
    except Exception as e:
        logger.warning("polling.webhook_clear_failed", tenant=tenant_slug, error=str(e))

    while True:
        try:
            # Long polling
            updates = await bot.get_updates(offset=offset, timeout=30)
            for u in updates:
                logger.info("polling.received_update", tenant=tenant_slug, update_id=u.get("update_id"))
                await forward_update(token, tenant_slug, u)
                offset = u.get("update_id") + 1
        except Exception as e:
            if "Conflict" in str(e):
                logger.warning("polling.conflict", tenant=tenant_slug)
                try: await bot.delete_webhook()
                except: pass
                await asyncio.sleep(5)
            else:
                logger.error("polling.error", tenant=tenant_slug, error=str(e))
                await asyncio.sleep(5)

async def main():
    logger.info("enterprise_polling.started", target=GATEWAY_URL)
    active_tasks = {}

    while True:
        db = SessionLocal()
        try:
            # Only poll bots for active tenants
            tenants = db.query(Tenant).filter(Tenant.is_active.is_(True)).all()
            for t in tenants:
                if t.id in active_tasks:
                    if active_tasks[t.id].done():
                        logger.warning("polling.worker_restart", tenant=t.slug)
                        del active_tasks[t.id]
                    else:
                        continue
                
                # Fetch token with explicit tenant_id
                token = persistence.get_setting("telegram_bot_token", tenant_id=t.id)
                if token:
                    logger.info("polling.spawn_tenant_worker", tenant=t.slug)
                    task = asyncio.create_task(poll_bot(t.id, t.slug, token))
                    active_tasks[t.id] = task
            
        except Exception as e:
            logger.error("polling.manager_loop_error", error=str(e))
        finally:
            db.close()
            
        await asyncio.sleep(20)

if __name__ == "__main__":
    asyncio.run(main())

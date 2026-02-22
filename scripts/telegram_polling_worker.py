"""Telegram Polling Worker (Sidecar).

Runs a long-polling loop to fetch updates from Telegram and forwards them
to the ARIIA Gateway webhook endpoint. This bypasses the need for a public
HTTPS webhook URL.
"""
import asyncio
import os
from pathlib import Path
import structlog
import httpx
from dotenv import load_dotenv
from app.integrations.telegram import TelegramBot

# Setup
load_dotenv()
logger = structlog.get_logger()

GATEWAY_URL = os.getenv("GATEWAY_INTERNAL_URL", "http://127.0.0.1:8000").rstrip("/")
WEBHOOK_ENDPOINT = f"{GATEWAY_URL}/webhook/telegram"
OFFSET_FILE = Path(os.getenv("TELEGRAM_OFFSET_FILE", "data/telegram_offset.txt"))
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()


def load_offset() -> int | None:
    try:
        if OFFSET_FILE.exists():
            raw = OFFSET_FILE.read_text(encoding="utf-8").strip()
            if raw.isdigit():
                return int(raw)
    except Exception as e:
        logger.warning("polling.offset_load_failed", error=str(e))
    return None


def save_offset(offset: int | None) -> None:
    if offset is None:
        return
    try:
        OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
        OFFSET_FILE.write_text(str(offset), encoding="utf-8")
    except Exception as e:
        logger.warning("polling.offset_save_failed", error=str(e))

async def forward_update(update: dict, client: httpx.AsyncClient):
    """Post update to local gateway."""
    try:
        # DEBUG: Print update to see chat_id
        print(f"📥 Received Update: {update}", flush=True)
        
        headers = {}
        if WEBHOOK_SECRET:
            headers["x-telegram-webhook-secret"] = WEBHOOK_SECRET
        resp = await client.post(WEBHOOK_ENDPOINT, json=update, headers=headers)
        if resp.status_code >= 400:
            body = (await resp.aread()).decode("utf-8", errors="ignore")[:300]
            logger.error(
                "polling.forward_failed",
                status=resp.status_code,
                endpoint=WEBHOOK_ENDPOINT,
                body_preview=body,
            )
    except Exception as e:
        logger.error("polling.forward_failed", error=str(e), endpoint=WEBHOOK_ENDPOINT)

async def run_polling():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("polling.no_token")
        return

    bot = TelegramBot(bot_token=token)
    
    # 1. Clear Webhook with Verification Loop
    max_retries = 5
    for attempt in range(max_retries):
        try:
            logger.info("polling.clearing_webhook", attempt=attempt+1)
            await bot.delete_webhook(drop_pending_updates=False)
            
            # Verify it's actually gone (Optional but good for debugging)
            # For now, just wait longer to ensure propagation
            await asyncio.sleep(2.0 + attempt) 
            
            # Try a test fetch to see if we get 409
            # If this succeeds (or throws timeout), we are good. 
            # If it throws 409, we loop again.
            await bot.get_updates(offset=None, timeout=1)
            
            logger.info("polling.webhook_cleared_confirmed")
            break
        except Exception as e:
            if "Conflict" in str(e):
                logger.warning("polling.conflict_detected_retrying", error=str(e))
                continue
            elif "Timed out" in str(e) or "ReadTimeout" in str(e):
                # Timeout means polling IS working (no conflict)
                logger.info("polling.webhook_cleared_confirmed_via_timeout")
                break
            else:
                logger.warning("polling.webhook_clear_error", error=str(e))
                # Treat other errors as non-fatal to the loop?
                pass
    else:
        logger.error("polling.failed_to_clear_webhook_after_retries")
        # Proceed anyway, maybe it works now?

    offset = load_offset()
    logger.info("polling.started", target=WEBHOOK_ENDPOINT, offset=offset)
    
    async with httpx.AsyncClient(timeout=15.0) as gateway_client:
        while True:
            try:
                updates = await bot.get_updates(offset=offset, timeout=10)
                
                if updates:
                    logger.info("polling.updates_received", count=len(updates), offset_used=offset)

                for update in updates:
                    update_id = update.get("update_id")
                    # Forward to Gateway
                    await forward_update(update, gateway_client)
                    
                    # Advance offset
                    offset = update_id + 1
                    save_offset(offset)
                    
            except Exception as e:
                logger.error("polling.loop_error", error=str(e))
                await asyncio.sleep(2) # Backoff

if __name__ == "__main__":
    asyncio.run(run_polling())

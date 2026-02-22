"""Shared utilities for Gateway routers.

Handles outbound message dispatch (WhatsApp, Telegram, SMS, Email) and Admin Broadcasts.
"""

import asyncio
import httpx
import structlog
from typing import Any, Optional

from app.gateway.schemas import Platform
from app.gateway.persistence import persistence
from app.gateway.dependencies import (
    active_websockets,
    telegram_bot,
    whatsapp_verifier,
)

logger = structlog.get_logger()

async def _send_sms_via_twilio(*, to: str, content: str, tenant_id: int | None) -> None:
    resolved_tenant = tenant_id or persistence.get_system_tenant_id()
    sid = persistence.get_setting("twilio_account_sid", "", tenant_id=resolved_tenant) or ""
    token = persistence.get_setting("twilio_auth_token", "", tenant_id=resolved_tenant) or ""
    from_number = persistence.get_setting("twilio_sms_number", "", tenant_id=resolved_tenant) or ""
    if not sid or not token or not from_number:
        raise RuntimeError(f"Twilio SMS config incomplete for tenant {resolved_tenant}")
    async with httpx.AsyncClient(timeout=20.0, auth=(sid, token)) as client:
        resp = await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data={"To": to, "From": from_number, "Body": content},
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"Twilio SMS failed ({resp.status_code})")


async def _send_email_via_postmark(*, to_email: str, subject: str, content: str, tenant_id: int | None) -> None:
    resolved_tenant = tenant_id or persistence.get_system_tenant_id()
    token = persistence.get_setting("postmark_server_token", "", tenant_id=resolved_tenant) or ""
    from_email = persistence.get_setting("email_outbound_from", "", tenant_id=resolved_tenant) or ""
    if not token or not from_email:
        raise RuntimeError(f"Postmark email config incomplete for tenant {resolved_tenant}")
    payload = {
        "From": from_email,
        "To": to_email,
        "Subject": subject,
        "TextBody": content,
        "MessageStream": persistence.get_setting("postmark_message_stream", "outbound", tenant_id=resolved_tenant) or "outbound",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            "https://api.postmarkapp.com/email",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": token,
            },
            json=payload,
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"Postmark email failed ({resp.status_code})")


async def send_to_user(user_id: str, platform: Platform, content: str, metadata: dict[str, Any] = None) -> None:
    """Send a message to a user via the appropriate channel."""
    if not content:
        return

    metadata = metadata or {}

    try:
        if platform == Platform.WHATSAPP:
            await whatsapp_verifier.send_text(user_id, content)
            logger.info("bridge.reply_sent", to=user_id)

        elif platform == Platform.TELEGRAM:
             # Send via Telegram API
             # Meta: use chat_id from metadata if available, else user_id
             chat_id = metadata.get("chat_id", user_id)
             # Use parse_mode=None to avoid Markdown errors with raw user input
             await telegram_bot.send_message(chat_id, content, parse_mode=None)
             logger.info("telegram.reply_sent", to=chat_id)
        elif platform == Platform.SMS:
            await _send_sms_via_twilio(
                to=user_id,
                content=content[:1550],
                tenant_id=metadata.get("tenant_id"),
            )
            logger.info("sms.reply_sent", to=user_id)
        elif platform == Platform.EMAIL:
            subject = (metadata.get("subject") or "Re: Deine Nachricht an ARIIA").strip()[:150]
            await _send_email_via_postmark(
                to_email=user_id,
                subject=subject,
                content=content,
                tenant_id=metadata.get("tenant_id"),
            )
            logger.info("email.reply_sent", to=user_id)
        elif platform in {Platform.PHONE, Platform.VOICE}:
            logger.info("voice.reply_buffered", to=user_id, note="Outbound voice synthesis not yet wired")
        
        else:
            logger.wariiang("gateway.unknown_platform", platform=platform, user_id=user_id)
             
    except Exception as e:
        logger.error("gateway.send_failed", error=str(e), user_id=user_id, platform=platform)
        raise e


async def broadcast_to_admins(message: dict[str, Any]) -> None:
    """Send a message to all connected WebSocket clients (Admin Dashboard)."""
    disconnected = []
    for ws in active_websockets:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in active_websockets:
            active_websockets.remove(ws)

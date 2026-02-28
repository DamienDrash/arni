"""Shared utilities for Gateway routers.

Handles outbound message dispatch (WhatsApp, Telegram, SMS, Email) and Admin Broadcasts.
"""

import asyncio
import httpx
import structlog
from datetime import datetime, timezone
from typing import Any, Optional

from app.gateway.schemas import Platform
from app.gateway.persistence import persistence
from app.gateway.dependencies import (
    active_websockets,
    get_telegram_bot,
    get_whatsapp_client,
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



async def _send_email_via_smtp(*, to_email: str, subject: str, content: str, tenant_id: int | None) -> None:
    """Send email via SMTP (tenant-specific or system-level fallback)."""
    resolved_tenant = tenant_id or persistence.get_system_tenant_id()
    
    # Try tenant-specific SMTP first
    host = persistence.get_setting("smtp_host", None, tenant_id=resolved_tenant)
    username = persistence.get_setting("smtp_username", None, tenant_id=resolved_tenant)
    password = persistence.get_setting("smtp_password", None, tenant_id=resolved_tenant)
    port_raw = persistence.get_setting("smtp_port", "587", tenant_id=resolved_tenant)
    from_email = persistence.get_setting("smtp_from_email", None, tenant_id=resolved_tenant)
    from_name = persistence.get_setting("smtp_from_name", "ARIIA", tenant_id=resolved_tenant)
    
    # Fallback to platform-level (system) SMTP settings
    if not all([host, username, password]):
        host = persistence.get_setting("platform_email_smtp_host", None, tenant_id=1)
        port_raw = persistence.get_setting("platform_email_smtp_port", "587", tenant_id=1)
        username = persistence.get_setting("platform_email_smtp_user", None, tenant_id=1)
        password = persistence.get_setting("platform_email_smtp_pass", None, tenant_id=1)
        from_email = persistence.get_setting("platform_email_from_addr", username, tenant_id=1)
        from_name = persistence.get_setting("platform_email_from_name", "ARIIA", tenant_id=1)
        logger.info("gateway.email.using_system_smtp", tenant_id=resolved_tenant)
    
    if not from_email:
        from_email = username
    
    if not all([host, username, password, from_email]):
        raise RuntimeError(f"SMTP email config incomplete for tenant {resolved_tenant}")
    
    from app.integrations.email import SMTPMailer
    port = int(port_raw or "587")
    mailer = SMTPMailer(
        host=host,
        port=port,
        username=username,
        password=password,
        from_email=from_email,
        from_name=from_name,
        use_starttls=True,
    )
    await asyncio.to_thread(mailer.send_text_mail, to_email, subject, content)
    logger.info("email.sent_via_smtp", to=to_email, tenant_id=resolved_tenant)

async def send_to_user(
    user_id: str, 
    platform: Platform, 
    content: str, 
    metadata: dict[str, Any] = None,
    tenant_id: int | None = None
) -> None:
    """Send a message to a user via the appropriate channel."""
    if not content:
        return

    metadata = metadata or {}
    resolved_tid = tenant_id or metadata.get("tenant_id")
    
    # Gold Standard Fix: If tid is still missing, recover it from the active session
    if resolved_tid is None:
        try:
            # We look up the session globally to identify the tenant owner of this conversation
            session = persistence.get_session_global(user_id) 
            if session:
                resolved_tid = session.tenant_id
                logger.info("gateway.tenant_resolved_from_session", user_id=user_id, tenant_id=resolved_tid)
        except Exception as e:
            logger.warning("gateway.tenant_resolution_failed", user_id=user_id, error=str(e))
            pass
            
    # Final fallback if it's a global system notification
    if resolved_tid is None:
        resolved_tid = persistence.get_system_tenant_id()

    try:
        if platform == Platform.WHATSAPP:
            wa_client = get_whatsapp_client(resolved_tid)
            await wa_client.send_text(user_id, content)
            logger.info("bridge.reply_sent", to=user_id, tenant_id=resolved_tid)

        elif platform == Platform.TELEGRAM:
             # Send via Telegram API
             chat_id = metadata.get("chat_id", user_id)
             tg_bot = get_telegram_bot(resolved_tid)
             await tg_bot.send_message(chat_id, content, parse_mode=None)
             logger.info("telegram.reply_sent", to=chat_id, tenant_id=resolved_tid)
             
        elif platform == Platform.SMS:
            await _send_sms_via_twilio(
                to=user_id,
                content=content[:1550],
                tenant_id=resolved_tid,
            )
            logger.info("sms.reply_sent", to=user_id, tenant_id=resolved_tid)
            
        elif platform == Platform.EMAIL:
            subject = (metadata.get("subject") or "Re: Deine Nachricht an ARIIA").strip()[:150]
            # Try Postmark first, then SMTP fallback
            postmark_token = persistence.get_setting("postmark_server_token", "", tenant_id=resolved_tid) or ""
            postmark_from = persistence.get_setting("email_outbound_from", "", tenant_id=resolved_tid) or ""
            if postmark_token and postmark_from:
                await _send_email_via_postmark(
                    to_email=user_id,
                    subject=subject,
                    content=content,
                    tenant_id=resolved_tid,
                )
                logger.info("email.reply_sent_postmark", to=user_id, tenant_id=resolved_tid)
            else:
                await _send_email_via_smtp(
                    to_email=user_id,
                    subject=subject,
                    content=content,
                    tenant_id=resolved_tid,
                )
                logger.info("email.reply_sent_smtp", to=user_id, tenant_id=resolved_tid)
            
        elif platform in {Platform.PHONE, Platform.VOICE}:
            logger.info("voice.reply_buffered", to=user_id, note="Outbound voice synthesis not yet wired")
        
        else:
            logger.warning("gateway.unknown_platform", platform=platform, user_id=user_id)
        
        # Gold Standard: Save to DB so it appears in history
        try:
            import asyncio
            # We run this in a thread to avoid blocking the reply flow, 
            # but we do it BEFORE the broadcast to ensure data exists when frontend refreshes.
            persistence.save_message(
                user_id=user_id,
                role="assistant",
                content=content,
                platform=platform,
                metadata=metadata,
                tenant_id=resolved_tid
            )
        except Exception as db_err:
            logger.error("gateway.outbound_save_failed", error=str(db_err))

        # Gold Standard: Always broadcast outbound messages to Ghost Mode (Admin Dashboard)
        # We ensure tenant_id is included so the dashboard can filter correctly.
        await broadcast_to_admins({
            "type": "ghost.message_out",
            "user_id": user_id,
            "tenant_id": resolved_tid,
            "platform": platform.value if hasattr(platform, 'value') else str(platform),
            "response": content,
            "message_id": f"out-{datetime.now(timezone.utc).timestamp()}",
            "metadata": metadata
        }, tenant_id=resolved_tid)
             
    except Exception as e:
        logger.error("gateway.send_failed", error=str(e), user_id=user_id, platform=platform, tenant_id=resolved_tid)
        raise e


async def broadcast_to_admins(message: dict[str, Any], tenant_id: int | None = None) -> None:
    """Send a message to all connected WebSocket clients (Admin Dashboard) for a specific tenant."""
    from app.gateway.dependencies import active_websockets
    
    # If no tenant_id provided, we broadcast to all
    targets = []
    if tenant_id is not None:
        targets = active_websockets.get(tenant_id, [])
    else:
        for ws_list in active_websockets.values():
            targets.extend(ws_list)

    disconnected = []
    for ws in targets:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
            
    # Cleanup disconnected
    for ws in disconnected:
        for tid in list(active_websockets.keys()):
            if ws in active_websockets[tid]:
                active_websockets[tid].remove(ws)

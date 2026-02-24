"""ARIIA v2.0 – Webhook Router.

Handles inbound messages from WhatsApp, Telegram, Instagram, Facebook Messenger,
Google Business Messages, SMS, and Email.
"""

import asyncio
import base64
import hmac
import json
import re
import urllib.parse
from uuid import uuid4
from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, Header, HTTPException, Request, Response, Form, Query
from pydantic import BaseModel, ValidationError

from app.gateway.persistence import persistence
from app.gateway.schemas import InboundMessage, OutboundMessage, Platform, WebhookPayload
from app.gateway.redis_bus import RedisBus
from app.gateway.dependencies import (
    redis_bus,
    get_telegram_bot,
    get_whatsapp_client,
    swarm_router,
    get_settings,
)
from app.gateway.utils import send_to_user, broadcast_to_admins, _send_email_via_postmark
from app.core.models import Tenant
from app.core.db import SessionLocal
from app.core.redis_keys import (
    token_key,
    user_token_key,
    human_mode_key,
    dialog_context_key,
)
from app.gateway.member_matching import match_member_by_phone
from app.gateway.persistence_helpers import save_inbound_to_db, save_outbound_to_db

logger = structlog.get_logger()
router = APIRouter(tags=["webhooks"])
settings = get_settings()

ARIIA_ERROR_MESSAGES = [
    "Hoppla, Hantel fallen gelassen... 🏋️ Versuch's gleich nochmal!",
    "Kurze technische Pause – ich bin gleich wieder da! 💪",
    "Da hat's kurz gehakt. Schreib mir nochmal, ich bin ready! 🔥",
]
HANDOFF_KEYWORDS = {
    "mitarbeiter",
    "support",
    "mensch",
    "human",
    "agent",
    "berater",
    "service",
}

# --- Helper Functions (Private) ---

def _resolve_tenant_id(metadata: dict[str, Any] | None = None) -> int | None:
    if metadata and metadata.get("tenant_id") is not None:
        try:
            return int(metadata.get("tenant_id"))
        except (TypeError, ValueError):
            pass
    return None # Explicitly return None, no default fallback allowed.


def _resolve_tenant_id_by_slug(tenant_slug: str) -> int | None:
    slug = (tenant_slug or "").strip().lower()
    if not slug:
        return None
    db = SessionLocal()
    try:
        row = db.query(Tenant).filter(Tenant.slug == slug, Tenant.is_active.is_(True)).first()
        return int(row.id) if row else None
    finally:
        db.close()

def _bool_setting(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}

def _mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return "deine hinterlegte E-Mail"
    local, domain = email.split("@", 1)
    if not local:
        return f"***@{domain}"
    if len(local) <= 2:
        masked_local = f"{local[0]}*"
    else:
        masked_local = f"{local[0]}{'*' * (len(local) - 2)}{local[-1]}"
    return f"{masked_local}@{domain}"


def _verify_twilio_signature(
    *,
    auth_token: str,
    request_url: str,
    form_data: dict[str, str],
    signature: str,
) -> bool:
    if not auth_token:
        return False
    if not signature:
        return False
    to_sign = request_url
    for key in sorted(form_data.keys()):
        to_sign += f"{key}{form_data[key]}"
    digest = hmac.new(auth_token.encode("utf-8"), to_sign.encode("utf-8"), "sha1").digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature.strip())

# --- Schema ---
class EmailInboundPayload(BaseModel):
    From: str
    To: str | None = None
    Subject: str | None = None
    TextBody: str | None = None
    HtmlBody: str | None = None
    MessageID: str | None = None
    InReplyTo: str | None = None


# --- Core Logic: Process & Reply ---
# This was previously in main.py, moving it here as it's the core of webhook handling.

async def _send_verification_email(
    to_email: str,
    token: str,
    member_name: str | None = None,
    tenant_id: int | None = None,
) -> bool:
    # Logic extracted from main.py
    host = persistence.get_setting("smtp_host", "smtp_host", tenant_id=tenant_id)
    port_raw = persistence.get_setting("smtp_port", "587", tenant_id=tenant_id)
    username = persistence.get_setting("smtp_username", "", tenant_id=tenant_id)
    password = persistence.get_setting("smtp_password", "", tenant_id=tenant_id)
    from_email = persistence.get_setting("smtp_from_email", username, tenant_id=tenant_id)
    from_name = persistence.get_setting("smtp_from_name", "Ariia", tenant_id=tenant_id)
    subject = persistence.get_setting("verification_email_subject", "Dein ARIIA Verifizierungscode", tenant_id=tenant_id)
    use_starttls = _bool_setting(persistence.get_setting("smtp_use_starttls", "true", tenant_id=tenant_id))

    if not all([host, username, password, from_email]):
        logger.warning("gateway.verification.smtp_missing_config")
        return False

    greeting_name = member_name.strip() if member_name else ""
    greeting = f"Hallo {greeting_name}," if greeting_name else "Hallo,"
    body = (
        f"{greeting}\n\n"
        "dein ARIIA Verifizierungscode lautet:\n\n"
        f"{token}\n\n"
        "Der Code ist 24 Stunden gültig. Bitte gib ihn im Chat ein, um die Verifizierung abzuschließen.\n\n"
        "Wenn du diese Anfrage nicht gestartet hast, ignoriere diese E-Mail."
    )
    try:
        from app.integrations.email import SMTPMailer

        port = int(port_raw or "587")
        mailer = SMTPMailer(
            host=host,
            port=port,
            username=username,
            password=password,
            from_email=from_email,
            from_name=from_name,
            use_starttls=use_starttls,
        )
        await asyncio.to_thread(mailer.send_text_mail, to_email, subject, body)
        return True
    except Exception as exc:
        logger.error("gateway.verification.email_send_failed", error=str(exc))
        return False


async def process_and_reply(message: InboundMessage) -> None:
    """Core pipeline: Inbound -> Redis -> Swarm -> Reply."""
    try:
        # 1. Extract metadata (Names, etc.)
        user_name_extracted = None
        phone_number_extracted = None
        member_id_extracted = None
        
        if message.platform == Platform.TELEGRAM:
             meta = message.metadata or {}
             first = meta.get("first_name", "")
             username = meta.get("username", "")
             phone = meta.get("phone_number")
             if first and username:
                 user_name_extracted = f"{first} (@{username})"
             elif first:
                 user_name_extracted = first
             elif username:
                 user_name_extracted = f"@{username}"
             if phone:
                 phone_number_extracted = phone

        # 2. Token Verification Check
        content = message.content.strip() if message.content else ""
        if re.match(r"^\d{6}$", content):
            token = content
            bus = RedisBus(settings.redis_url)
            await bus.connect()
            try:
                t_id = message.tenant_id or persistence.get_system_tenant_id()
                data_str = await bus.client.get(token_key(t_id, token))
                if data_str:
                    if isinstance(data_str, bytes):
                        data_str = data_str.decode("utf-8")
                    data = json.loads(data_str)
                    
                    member_id_extracted = data.get("member_id")
                    token_user_id = data.get("user_id")
                    token_phone_number = data.get("phone_number")
                    
                    if token_user_id and str(token_user_id) != str(message.user_id):
                        await send_to_user(message.user_id, message.platform, "⚠️ Dieser Code gehört zu einem anderen Account.", tenant_id=message.tenant_id)
                        return

                    if not member_id_extracted:
                        phone_candidate = token_phone_number or phone_number_extracted
                        if not phone_candidate:
                            existing_session = await asyncio.to_thread(persistence.get_or_create_session, message.user_id, message.platform, tenant_id=message.tenant_id)
                            phone_candidate = existing_session.phone_number

                        if phone_candidate:
                            matched_member = await asyncio.to_thread(match_member_by_phone, phone_candidate, message.tenant_id)
                            if matched_member:
                                member_id_extracted = matched_member.member_number or str(matched_member.customer_id)

                    if member_id_extracted:
                        await bus.client.delete(token_key(t_id, token))
                        if token_user_id:
                            await bus.client.delete(user_token_key(t_id, str(token_user_id)))
                        
                        # Gold Standard Fix: Explicitly update the session in DB
                        await asyncio.to_thread(
                            persistence.get_or_create_session, 
                            message.user_id, 
                            message.platform, 
                            tenant_id=message.tenant_id,
                            member_id=member_id_extracted
                        )
                        
                        await send_to_user(message.user_id, message.platform, "✅ Verifizierung erfolgreich! Dein Account ist nun verknüpft.", tenant_id=message.tenant_id)
                        
                        # Update session
                        asyncio.create_task(asyncio.to_thread(
                            persistence.save_message,
                            user_id=message.user_id,
                            role="user",
                            content=f"[Token] {token} (Verified)",
                            platform=message.platform,
                            metadata={"verified": True, "token": token},
                            user_name=user_name_extracted,
                            phone_number=phone_number_extracted,
                            member_id=member_id_extracted,
                            tenant_id=message.tenant_id
                        ))
                        return
            finally:
                await bus.disconnect()

        # 5. Broadcast to Ghost Mode
        await broadcast_to_admins({
            "type": "ghost.message_in",
            "message_id": message.message_id,
            "user_id": message.user_id,
            "content": message.content,
            "platform": message.platform,
        })

        # Gold Standard: Check if user is known/verified. If not, trigger contact request.
        session = await asyncio.to_thread(persistence.get_or_create_session, message.user_id, message.platform, tenant_id=message.tenant_id)
        if not session.member_id and message.platform == Platform.TELEGRAM:
            # We check if we already asked for contact recently to avoid spamming
            bus = RedisBus(settings.redis_url)
            await bus.connect()
            asked_key = f"asked_contact:{message.user_id}"
            already_asked = await bus.client.get(asked_key)
            if not already_asked:
                await bus.client.setex(asked_key, 300, "1")
                await bus.disconnect()
                tg_bot = get_telegram_bot(message.tenant_id)
                welcome_msg = "Hallo! 👋 Ich würde dir gerne helfen, muss dich aber zuerst kurz in unserem System finden. Klicke bitte unten auf '📱 Kontakt teilen', damit ich dein Profil zuordnen kann."
                # Sending with a special keyboard for contact sharing
                keyboard = {
                    "keyboard": [[{"text": "📱 Kontakt teilen", "request_contact": True}]],
                    "resize_keyboard": True,
                    "one_time_keyboard": True
                }
                await tg_bot.send_message(message.user_id, welcome_msg, reply_markup=keyboard)
                return
            await bus.disconnect()

        # 6. Swarm Routing
        result = await swarm_router.route(message)
        
        # 7. Reply
        if result.content:
            await send_to_user(
                message.user_id, 
                message.platform, 
                result.content, 
                metadata=message.metadata,
                tenant_id=message.tenant_id
            )
            
    except Exception as e:
        logger.error("swarm.reply_failed", error=str(e))
        import random
        await send_to_user(message.user_id, message.platform, random.choice(ARIIA_ERROR_MESSAGES))


# --- Routes ---

@router.get("/webhook/whatsapp")
async def webhook_verify(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
) -> Any:
    """Legacy single-tenant verification."""
    return {"error": "Legacy verification disabled. Use /webhook/whatsapp/{tenant_slug}"}

async def _process_whatsapp_payload(raw_body: bytes, x_hub_signature_256: str | None, tenant_id: int | None) -> int:
    """Shared logic for WhatsApp payload processing."""
    wa_client = get_whatsapp_client(tenant_id)
    if wa_client.app_secret:
        if not wa_client.verify_webhook_signature(raw_body, x_hub_signature_256 or ""):
            raise HTTPException(status_code=403, detail="Invalid webhook signature")

    try:
        payload = WebhookPayload.model_validate_json(raw_body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    messages_processed = 0
    for entry in payload.entry:
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})
            wa_messages = value.get("messages", [])
            for msg in wa_messages:
                resolved_tid = tenant_id if tenant_id is not None else _resolve_tenant_id({"tenant_id": value.get("tenant_id")})
                
                if resolved_tid is None:
                    logger.warning("webhook.tenant_resolution_failed", platform="whatsapp")
                    raise HTTPException(status_code=403, detail="Tenant resolution failed. Mapping required.")

                inbound = InboundMessage(
                    message_id=msg.get("id", str(uuid4())),
                    platform=Platform.WHATSAPP,
                    user_id=msg.get("from", "unknown"),
                    content=msg.get("text", {}).get("body", ""),
                    content_type=msg.get("type", "text"),
                    metadata={"raw_type": msg.get("type"), "profile": value.get("contacts", [])},
                    tenant_id=resolved_tid,
                )
                
                channel = redis_bus.get_tenant_channel(RedisBus.CHANNEL_INBOUND, resolved_tid)
                await redis_bus.publish(channel, inbound.model_dump_json())
                
                messages_processed += 1
                asyncio.create_task(save_inbound_to_db(inbound))
                asyncio.create_task(process_and_reply(inbound))
    return messages_processed

@router.post("/webhook/whatsapp")
async def webhook_inbound(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="x-hub-signature-256"),
) -> dict[str, str]:
    """Legacy single-tenant inbound."""
    raw_body = await request.body()
    messages_processed = await _process_whatsapp_payload(raw_body, x_hub_signature_256, tenant_id=None)
    return {"status": "ok", "processed": str(messages_processed)}

@router.get("/webhook/whatsapp/{tenant_slug}")
async def webhook_verify_tenant(
    tenant_slug: str,
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
) -> Any:
    tenant_id = _resolve_tenant_id_by_slug(tenant_slug)
    if tenant_id is None:
        raise HTTPException(status_code=404, detail="Unknown tenant")
    
    expected_token = persistence.get_setting("meta_verify_token", tenant_id=tenant_id)
    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        return int(hub_challenge)
    return {"error": "Verification failed"}

@router.post("/webhook/whatsapp/{tenant_slug}")
async def webhook_inbound_tenant(
    tenant_slug: str,
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="x-hub-signature-256"),
) -> dict[str, str]:
    tenant_id = _resolve_tenant_id_by_slug(tenant_slug)
    if tenant_id is None:
        raise HTTPException(status_code=404, detail="Unknown tenant")
    
    raw_body = await request.body()
    messages_processed = await _process_whatsapp_payload(raw_body, x_hub_signature_256, tenant_id=tenant_id)
    return {"status": "ok", "processed": str(messages_processed)}


@router.post("/webhook/telegram/{tenant_slug}")
async def webhook_telegram_tenant(
    tenant_slug: str,
    payload: dict[str, Any],
    x_telegram_webhook_secret: str | None = Header(default=None, alias="x-telegram-webhook-secret"),
) -> dict[str, str]:
    tenant_id = _resolve_tenant_id_by_slug(tenant_slug)
    if tenant_id is None:
        raise HTTPException(status_code=404, detail="Unknown tenant")
        
    # Secret Check
    raw_secret = persistence.get_setting("telegram_webhook_secret", tenant_id=tenant_id)
    if raw_secret and not hmac.compare_digest(raw_secret.strip(), (x_telegram_webhook_secret or "").strip()):
         raise HTTPException(status_code=403, detail="Invalid webhook secret")
    
    tg_bot = get_telegram_bot(tenant_id)
    norm = tg_bot.normalize_update(payload)
    if not norm:
        return {"status": "ignored"}

    # Handle Contact Sharing directly
    if "contact" in payload.get("message", {}):
        contact = payload["message"]["contact"]
        phone = contact.get("phone_number")
        if phone:
            # 1. Save phone to session
            await asyncio.to_thread(persistence.get_or_create_session, str(contact["user_id"]), Platform.TELEGRAM, tenant_id=tenant_id, phone_number=phone)
            # 2. Try to match member
            matched = await asyncio.to_thread(match_member_by_phone, phone, tenant_id)
            if matched:
                # 3. Generate Token & Send Email
                import random
                token = f"{random.randint(100000, 999999)}"
                bus = RedisBus(settings.redis_url)
                await bus.connect()
                await bus.client.setex(token_key(tenant_id, token), 86400, json.dumps({
                    "user_id": str(contact["user_id"]),
                    "member_id": matched.member_number or str(matched.customer_id),
                    "phone_number": phone
                }))
                await bus.disconnect()
                
                email_sent = await _send_verification_email(matched.email, token, matched.first_name, tenant_id=tenant_id)
                if email_sent:
                    msg = f"Ich habe dich gefunden, {matched.first_name}! 😊 Ich habe dir soeben einen 6-stelligen Code an {matched.email[:3]}*** gesendet. Bitte gib den Code hier ein."
                else:
                    msg = "Ich habe dich gefunden, konnte aber keine Mail senden. Bitte wende dich an den Support."
                
                await send_to_user(str(contact["user_id"]), Platform.TELEGRAM, msg, tenant_id=tenant_id)
                return {"status": "ok"}
            else:
                await send_to_user(str(contact["user_id"]), Platform.TELEGRAM, "Ich konnte deine Nummer leider keinem Mitglied zuordnen. Bitte wende dich an das Team vor Ort.", tenant_id=tenant_id)
                return {"status": "ok"}

    inbound = InboundMessage(
        message_id=norm["message_id"],
        platform=Platform.TELEGRAM,
        user_id=norm["user_id"],
        content=norm["content"],
        content_type=norm.get("content_type", "text"),
        metadata=norm.get("metadata", {}),
        tenant_id=tenant_id,
    )
    
    channel = redis_bus.get_tenant_channel(RedisBus.CHANNEL_INBOUND, tenant_id)
    await redis_bus.publish(channel, inbound.model_dump_json())
    asyncio.create_task(save_inbound_to_db(inbound))
    asyncio.create_task(process_and_reply(inbound))
    return {"status": "ok"}


# ─────────────────────────────────────────────────────────────────────
# Instagram DM Webhooks (Meta Graph API)
# ─────────────────────────────────────────────────────────────────────

@router.get("/webhook/instagram/{tenant_slug}")
async def webhook_instagram_verify(
    tenant_slug: str,
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
) -> Any:
    """Verify Instagram webhook subscription for a tenant."""
    tenant_id = _resolve_tenant_id_by_slug(tenant_slug)
    if tenant_id is None:
        raise HTTPException(status_code=404, detail="Unknown tenant")

    expected_token = persistence.get_setting("instagram_verify_token", tenant_id=tenant_id)
    if not expected_token:
        expected_token = persistence.get_setting("meta_verify_token", tenant_id=tenant_id)

    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        return int(hub_challenge)
    return {"error": "Verification failed"}


@router.post("/webhook/instagram/{tenant_slug}")
async def webhook_instagram_inbound(
    tenant_slug: str,
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="x-hub-signature-256"),
) -> dict[str, str]:
    """Handle inbound Instagram DM messages for a tenant."""
    tenant_id = _resolve_tenant_id_by_slug(tenant_slug)
    if tenant_id is None:
        raise HTTPException(status_code=404, detail="Unknown tenant")

    raw_body = await request.body()

    # Signature verification
    app_secret = persistence.get_setting("instagram_app_secret", tenant_id=tenant_id)
    if not app_secret:
        app_secret = persistence.get_setting("meta_app_secret", tenant_id=tenant_id)
    if app_secret:
        from app.integrations.instagram.client import InstagramClient
        temp_client = InstagramClient(page_id="", access_token="", app_secret=app_secret)
        if not temp_client.verify_webhook_signature(raw_body, x_hub_signature_256 or ""):
            raise HTTPException(status_code=403, detail="Invalid webhook signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Invalid JSON")

    from app.integrations.normalizer import MessageNormalizer
    normalizer = MessageNormalizer()
    messages = normalizer.normalize_instagram(payload)
    messages_processed = 0

    for msg in messages:
        msg.tenant_id = tenant_id
        channel = redis_bus.get_tenant_channel(RedisBus.CHANNEL_INBOUND, tenant_id)
        await redis_bus.publish(channel, msg.model_dump_json())
        asyncio.create_task(save_inbound_to_db(msg))
        asyncio.create_task(process_and_reply(msg))
        messages_processed += 1

    return {"status": "ok", "processed": str(messages_processed)}


# ─────────────────────────────────────────────────────────────────────
# Facebook Messenger Webhooks (Meta Send/Receive API)
# ─────────────────────────────────────────────────────────────────────

@router.get("/webhook/facebook/{tenant_slug}")
async def webhook_facebook_verify(
    tenant_slug: str,
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
) -> Any:
    """Verify Facebook Messenger webhook subscription for a tenant."""
    tenant_id = _resolve_tenant_id_by_slug(tenant_slug)
    if tenant_id is None:
        raise HTTPException(status_code=404, detail="Unknown tenant")

    expected_token = persistence.get_setting("facebook_verify_token", tenant_id=tenant_id)
    if not expected_token:
        expected_token = persistence.get_setting("meta_verify_token", tenant_id=tenant_id)

    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        return int(hub_challenge)
    return {"error": "Verification failed"}


@router.post("/webhook/facebook/{tenant_slug}")
async def webhook_facebook_inbound(
    tenant_slug: str,
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="x-hub-signature-256"),
) -> dict[str, str]:
    """Handle inbound Facebook Messenger messages for a tenant."""
    tenant_id = _resolve_tenant_id_by_slug(tenant_slug)
    if tenant_id is None:
        raise HTTPException(status_code=404, detail="Unknown tenant")

    raw_body = await request.body()

    # Signature verification
    app_secret = persistence.get_setting("facebook_app_secret", tenant_id=tenant_id)
    if not app_secret:
        app_secret = persistence.get_setting("meta_app_secret", tenant_id=tenant_id)
    if app_secret:
        from app.integrations.facebook.client import FacebookMessengerClient
        temp_client = FacebookMessengerClient(page_id="", page_access_token="", app_secret=app_secret)
        if not temp_client.verify_webhook_signature(raw_body, x_hub_signature_256 or ""):
            raise HTTPException(status_code=403, detail="Invalid webhook signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Invalid JSON")

    from app.integrations.normalizer import MessageNormalizer
    normalizer = MessageNormalizer()
    messages = normalizer.normalize_facebook(payload)
    messages_processed = 0

    for msg in messages:
        msg.tenant_id = tenant_id
        channel = redis_bus.get_tenant_channel(RedisBus.CHANNEL_INBOUND, tenant_id)
        await redis_bus.publish(channel, msg.model_dump_json())
        asyncio.create_task(save_inbound_to_db(msg))
        asyncio.create_task(process_and_reply(msg))
        messages_processed += 1

    return {"status": "ok", "processed": str(messages_processed)}


# ─────────────────────────────────────────────────────────────────────
# Google Business Messages Webhooks
# ─────────────────────────────────────────────────────────────────────

@router.post("/webhook/google-business/{tenant_slug}")
async def webhook_google_business_inbound(
    tenant_slug: str,
    request: Request,
) -> dict[str, str]:
    """Handle inbound Google Business Messages for a tenant.

    Google Business Messages does not use a verify-token flow like Meta.
    Instead, the webhook URL is registered in the Business Communications console.
    """
    tenant_id = _resolve_tenant_id_by_slug(tenant_slug)
    if tenant_id is None:
        raise HTTPException(status_code=404, detail="Unknown tenant")

    raw_body = await request.body()
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Invalid JSON")

    from app.integrations.normalizer import MessageNormalizer
    normalizer = MessageNormalizer()
    msg = normalizer.normalize_google_business(payload)

    if not msg:
        return {"status": "ignored"}

    msg.tenant_id = tenant_id
    channel = redis_bus.get_tenant_channel(RedisBus.CHANNEL_INBOUND, tenant_id)
    await redis_bus.publish(channel, msg.model_dump_json())
    asyncio.create_task(save_inbound_to_db(msg))
    asyncio.create_task(process_and_reply(msg))

    return {"status": "ok", "processed": "1"}

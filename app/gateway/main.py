"""ARNI v1.4 – Hybrid Gateway (Full Integration).

@BACKEND: Webhook Ingress (Task 1.5) + WebSocket Control (Task 1.6)
Integrates Redis Bus, Health, Webhook, and WebSocket endpoints.
"""

import asyncio
import base64
import hmac
import json
import os
import urllib.parse
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
import structlog
from fastapi import FastAPI, Form, Header, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError

from app.gateway.redis_bus import RedisBus
from app.gateway.schemas import (
    InboundMessage,
    OutboundMessage,
    Platform,
    SystemEvent,
    WebhookPayload,
)
from config.settings import Settings, get_settings
from app.core.instrumentation import setup_instrumentation
from app.integrations.telegram import TelegramBot
from app.integrations.whatsapp import WhatsAppClient
from app.voice.pipeline import process_voice_message, generate_voice_reply
from app.gateway.member_matching import match_member_by_phone
from app.core.auth import ensure_default_tenant_and_admin
from app.core.db import run_migrations, SessionLocal
from app.core.models import Tenant
from app.core.redis_keys import (
    token_key,
    user_token_key,
    human_mode_key,
    dialog_context_key,
)

logger = structlog.get_logger()

# Arni-style error messages (AGENTS.md §4 – no stack traces to user)
ARNI_ERROR_MESSAGES = [
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

# --- Globals ---
settings: Settings = get_settings()
redis_bus = RedisBus(redis_url=settings.redis_url)
active_websockets: list[WebSocket] = []
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Persistence (Sprint 13)
from app.gateway.persistence import persistence # Use shared singleton
from app.gateway.persistence_helpers import save_inbound_to_db, save_outbound_to_db
# persistence = PersistenceService() # Removed local instance


def _resolve_tenant_id(metadata: dict[str, Any] | None = None) -> int | None:
    if metadata and metadata.get("tenant_id") is not None:
        try:
            return int(metadata.get("tenant_id"))
        except (TypeError, ValueError):
            pass
    return persistence.get_default_tenant_id()


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
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_cors_origins(raw: str) -> list[str]:
    origins = [item.strip() for item in (raw or "").split(",") if item.strip()]
    return origins or ["http://localhost:3000"]


def _enforce_startup_guards() -> None:
    if not settings.is_production:
        return

    weak_auth_secret = settings.auth_secret in {"", "change-me-long-random-secret", "changeme", "password123"}
    weak_acp_secret = settings.acp_secret in {"", "arni-acp-secret-changeme", "changeme", "password123"}
    weak_tg_secret = settings.telegram_webhook_secret in {"", "change-me-telegram-webhook-secret"}
    if weak_auth_secret or weak_acp_secret or weak_tg_secret:
        raise RuntimeError("Refusing startup in production due to weak/default secrets.")

    if settings.auth_transition_mode or settings.auth_allow_header_fallback:
        raise RuntimeError("Refusing startup in production with legacy auth transition flags enabled.")


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    """Application lifespan: connect Redis on startup, disconnect on shutdown."""
    background_tasks: list[asyncio.Task] = []
    _enforce_startup_guards()
    ensure_default_tenant_and_admin()
    run_migrations()
    os.makedirs(os.path.join(BASE_DIR, "data", "knowledge", "members"), exist_ok=True)
    # Seed billing plans (S4.2) — idempotent, safe to run on every startup
    try:
        from app.core.feature_gates import seed_plans
        seed_plans()
    except Exception as _e:
        logger.warning("arni.gateway.billing_seed_skipped", error=str(_e))
    logger.info("arni.gateway.startup", version="1.4.0", env=settings.environment)
    try:
        await redis_bus.connect()
    except Exception:
        logger.warning("arni.gateway.redis_unavailable", msg="Starting without Redis")

    # Initial member sync (best-effort) so admin/member lookup has fresh data.
    # Run in background to avoid blocking gateway startup.
    async def _run_members_sync() -> None:
        try:
            from app.integrations.magicline.members_sync import sync_members_from_magicline

            await asyncio.to_thread(sync_members_from_magicline)
        except Exception as e:
            logger.warning("arni.gateway.members_sync_skipped", error=str(e))

    background_tasks.append(asyncio.create_task(_run_members_sync()))
    try:
        from app.memory.member_memory_analyzer import scheduler_loop
        background_tasks.append(asyncio.create_task(scheduler_loop()))
    except Exception as e:
        logger.warning("arni.gateway.member_memory_scheduler_skipped", error=str(e))
    try:
        from app.integrations.magicline.scheduler import magicline_sync_scheduler_loop
        background_tasks.append(asyncio.create_task(magicline_sync_scheduler_loop()))
    except Exception as e:
        logger.warning("arni.gateway.magicline_scheduler_skipped", error=str(e))
    
    # TELEGRAM NOTE: We use Polling Sidecar (scripts/telegram_polling_worker.py)
    # because we don't have HTTPS for Webhook.
    # Do NOT register webhook here to avoid 409 Conflict.

    yield
    for task in background_tasks:
        task.cancel()
    await redis_bus.disconnect()
    logger.info("arni.gateway.shutdown")


app = FastAPI(
    title="ARNI Gateway",
    description="ARNI – Multi-Tenant AI Agent Gateway – FastAPI + Redis Pub/Sub + WebSocket",
    version="1.4.0",
    lifespan=lifespan,
)

# Setup Instrumentation (Sprint 7b)
setup_instrumentation(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(settings.cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# --- ACP Router (Sprint 6a) ---
from app.acp.server import router as acp_router
app.include_router(acp_router)

# --- Admin Router (Sprint 13) ---
from app.gateway.admin import router as admin_router
app.include_router(admin_router)

# --- Auth Router (Restore Sprint 16) ---
from app.gateway.auth import router as auth_router
app.include_router(auth_router)

# --- Stripe Billing Router (P2) ---
from app.gateway.routers.billing import router as billing_router
app.include_router(billing_router, prefix="/admin")



# ──────────────────────────────────────────
# Health Endpoint (Task 1.1)
# ──────────────────────────────────────────

@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health endpoint – returns system status.

    BMAD Benchmark: `curl http://185.209.228.251:8000/health` → `{"status": "ok"}`
    """
    redis_ok = await redis_bus.health_check()
    return {
        "status": "ok" if redis_ok else "degraded",
        "service": "arni-gateway",
        "version": "1.4.0",
        "redis": "connected" if redis_ok else "disconnected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ──────────────────────────────────────────
# Webhook Ingress (Task 1.5)
# ──────────────────────────────────────────


class EmailInboundPayload(BaseModel):
    From: str
    To: str | None = None
    Subject: str | None = None
    TextBody: str | None = None
    HtmlBody: str | None = None
    MessageID: str | None = None
    InReplyTo: str | None = None


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
    # Twilio signs URL + concatenated form params sorted by key (HMAC-SHA1, base64).
    to_sign = request_url
    for key in sorted(form_data.keys()):
        to_sign += f"{key}{form_data[key]}"
    digest = hmac.new(auth_token.encode("utf-8"), to_sign.encode("utf-8"), "sha1").digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature.strip())

@app.get("/webhook/whatsapp")
async def webhook_verify(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
) -> Any:
    """WhatsApp Webhook Verification (GET) — global fallback for legacy single-tenant setups."""
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_verify_token:
        logger.info("webhook.verified")
        return int(hub_challenge)
    logger.warning("webhook.verification_failed", mode=hub_mode)
    return {"error": "Verification failed"}


@app.get("/webhook/whatsapp/{tenant_slug}")
async def webhook_verify_tenant(
    tenant_slug: str,
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
) -> Any:
    """WhatsApp Webhook Verification for a specific tenant (S3.2)."""
    tenant_id = _resolve_tenant_id_by_slug(tenant_slug)
    if tenant_id is None:
        raise HTTPException(status_code=404, detail="Unknown tenant")
    expected_token = persistence.get_setting("wa_verify_token", settings.meta_verify_token, tenant_id=tenant_id) or settings.meta_verify_token
    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        logger.info("webhook.verified", tenant_slug=tenant_slug)
        return int(hub_challenge)
    logger.warning("webhook.verification_failed", mode=hub_mode, tenant_slug=tenant_slug)
    return {"error": "Verification failed"}


async def _process_whatsapp_payload(raw_body: bytes, x_hub_signature_256: str | None, tenant_id: int | None) -> int:
    """Shared logic for WhatsApp payload processing (used by both single- and multi-tenant routes)."""
    require_signature = bool(settings.meta_app_secret) and (settings.is_production or bool(x_hub_signature_256))
    if require_signature:
        if not _whatsapp_verifier.verify_webhook_signature(raw_body, x_hub_signature_256 or ""):
            logger.warning("webhook.whatsapp_forbidden", reason="invalid_signature")
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
                inbound = InboundMessage(
                    message_id=msg.get("id", str(uuid4())),
                    platform=Platform.WHATSAPP,
                    user_id=msg.get("from", "unknown"),
                    content=msg.get("text", {}).get("body", ""),
                    content_type=msg.get("type", "text"),
                    metadata={"raw_type": msg.get("type"), "profile": value.get("contacts", [])},
                    tenant_id=resolved_tid,
                )
                try:
                    await redis_bus.publish(RedisBus.CHANNEL_INBOUND, inbound.model_dump_json())
                    messages_processed += 1
                    logger.info("webhook.message_received", platform="whatsapp", message_id=inbound.message_id, tenant_id=resolved_tid)
                except Exception as e:
                    logger.error("webhook.publish_failed", error=str(e))
                asyncio.create_task(save_inbound_to_db(inbound))
                asyncio.create_task(process_and_reply(inbound))
    return messages_processed


@app.post("/webhook/whatsapp")
async def webhook_inbound(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="x-hub-signature-256"),
) -> dict[str, str]:
    """WhatsApp Webhook Ingress (POST) — legacy single-tenant route.

    Tenant is resolved from the payload. For new tenants, use /webhook/whatsapp/{tenant_slug}.
    """
    raw_body = await request.body()
    messages_processed = await _process_whatsapp_payload(raw_body, x_hub_signature_256, tenant_id=None)
    return {"status": "ok", "processed": str(messages_processed)}


@app.post("/webhook/whatsapp/{tenant_slug}")
async def webhook_inbound_tenant(
    tenant_slug: str,
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="x-hub-signature-256"),
) -> dict[str, str]:
    """WhatsApp Webhook Ingress for a specific tenant (S3.2).

    Tenant is unambiguously identified via URL slug — no payload parsing needed.
    Register this URL with Meta: https://api.arni.ai/webhook/whatsapp/{your-slug}
    """
    tenant_id = _resolve_tenant_id_by_slug(tenant_slug)
    if tenant_id is None:
        raise HTTPException(status_code=404, detail="Unknown tenant")
    raw_body = await request.body()
    messages_processed = await _process_whatsapp_payload(raw_body, x_hub_signature_256, tenant_id=tenant_id)
    return {"status": "ok", "processed": str(messages_processed)}


@app.post("/webhook/telegram")
async def webhook_telegram(
    payload: dict[str, Any],
    x_telegram_webhook_secret: str | None = Header(default=None, alias="x-telegram-webhook-secret"),
) -> dict[str, str]:
    """Telegram Webhook Ingress — legacy route (tenant resolved from metadata).
    For new tenants, use /webhook/telegram/{tenant_slug}.
    """
    return await _process_telegram_update(payload, x_telegram_webhook_secret, tenant_id=None)


@app.post("/webhook/telegram/{tenant_slug}")
async def webhook_telegram_tenant(
    tenant_slug: str,
    payload: dict[str, Any],
    x_telegram_webhook_secret: str | None = Header(default=None, alias="x-telegram-webhook-secret"),
) -> dict[str, str]:
    """Telegram Webhook Ingress for a specific tenant (S3.2).

    Tenant is unambiguously identified via URL slug.
    Register this URL with Telegram: https://api.arni.ai/webhook/telegram/{your-slug}
    """
    tenant_id = _resolve_tenant_id_by_slug(tenant_slug)
    if tenant_id is None:
        raise HTTPException(status_code=404, detail="Unknown tenant")
    return await _process_telegram_update(payload, x_telegram_webhook_secret, tenant_id=tenant_id)


async def _process_telegram_update(
    payload: dict[str, Any],
    x_telegram_webhook_secret: str | None,
    tenant_id: int | None,
) -> dict[str, str]:
    """Shared Telegram update processing logic."""
    raw_secret = getattr(settings, "telegram_webhook_secret", "")
    expected_secret = raw_secret.strip() if isinstance(raw_secret, str) else ""
    production_mode = bool(getattr(settings, "is_production", False))
    require_secret = bool(expected_secret) and (production_mode or bool(x_telegram_webhook_secret))
    if require_secret:
        if not hmac.compare_digest(expected_secret, (x_telegram_webhook_secret or "").strip()):
            logger.warning("webhook.telegram_forbidden", reason="invalid_secret")
            raise HTTPException(status_code=403, detail="Invalid webhook secret")
    elif production_mode:
        logger.error("webhook.telegram_unconfigured", reason="missing_secret")
        raise HTTPException(status_code=503, detail="Telegram webhook secret not configured")

    norm = _telegram_bot.normalize_update(payload)
    if not norm:
        return {"status": "ignored"}

    metadata = norm.get("metadata", {})
    metadata["chat_id"] = norm["chat_id"]
    metadata["username"] = norm.get("username")
    metadata["first_name"] = norm.get("first_name")

    resolved_tid = tenant_id if tenant_id is not None else _resolve_tenant_id(metadata)

    inbound = InboundMessage(
        message_id=norm["message_id"],
        platform=Platform.TELEGRAM,
        user_id=norm["user_id"],
        content=norm["content"],
        content_type=norm.get("content_type", "text"),
        metadata=metadata,
        tenant_id=resolved_tid,
    )

    if inbound.content.startswith("/"):
        cmd, args = _telegram_bot.parse_command(inbound.content)
        if str(inbound.user_id) == settings.telegram_admin_chat_id:
            await _telegram_bot.handle_command(cmd, args, norm["chat_id"])
            return {"status": "handled_command"}

    await redis_bus.publish(RedisBus.CHANNEL_INBOUND, inbound.model_dump_json())
    logger.info("webhook.message_received", platform="telegram", message_id=inbound.message_id, tenant_id=resolved_tid)
    asyncio.create_task(process_and_reply(inbound))
    return {"status": "ok"}


@app.post("/webhook/sms/{tenant_slug}")
async def webhook_sms(
    tenant_slug: str,
    request: Request,
    x_twilio_signature: str | None = Header(default=None, alias="x-twilio-signature"),
    from_number: str = Form(..., alias="From"),
    to_number: str = Form(default="", alias="To"),
    body: str = Form(default="", alias="Body"),
    message_sid: str = Form(default="", alias="MessageSid"),
) -> Response:
    tenant_id = _resolve_tenant_id_by_slug(tenant_slug)
    if tenant_id is None:
        raise HTTPException(status_code=404, detail="Unknown tenant")

    enabled = _bool_setting(persistence.get_setting("sms_channel_enabled", "false", tenant_id=tenant_id))
    if not enabled:
        raise HTTPException(status_code=503, detail="SMS channel disabled")

    twilio_auth_token = persistence.get_setting("twilio_auth_token", "", tenant_id=tenant_id) or ""
    if twilio_auth_token:
        forwarded_proto = request.headers.get("x-forwarded-proto")
        forwarded_host = request.headers.get("x-forwarded-host")
        request_url = str(request.url)
        if forwarded_host:
            proto = forwarded_proto or request.url.scheme
            request_url = f"{proto}://{forwarded_host}{request.url.path}"
            if request.url.query:
                request_url = f"{request_url}?{request.url.query}"
        form_data = {
            "From": from_number,
            "To": to_number,
            "Body": body,
            "MessageSid": message_sid,
        }
        if not _verify_twilio_signature(
            auth_token=twilio_auth_token,
            request_url=request_url,
            form_data=form_data,
            signature=x_twilio_signature or "",
        ):
            logger.warning("webhook.sms_forbidden", tenant_slug=tenant_slug, reason="invalid_signature")
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    inbound = InboundMessage(
        message_id=message_sid or str(uuid4()),
        platform=Platform.SMS,
        user_id=from_number.strip(),
        content=(body or "").strip(),
        content_type="text",
        tenant_id=tenant_id,
        metadata={
            "from_number": from_number,
            "to_number": to_number,
            "message_sid": message_sid,
            "tenant_slug": tenant_slug,
        },
    )
    await redis_bus.publish(RedisBus.CHANNEL_INBOUND, inbound.model_dump_json())
    asyncio.create_task(process_and_reply(inbound))
    return Response(content="<Response></Response>", media_type="application/xml")


@app.post("/webhook/email/{tenant_slug}")
async def webhook_email(
    tenant_slug: str,
    payload: EmailInboundPayload,
    x_arni_email_token: str | None = Header(default=None, alias="x-arni-email-token"),
) -> dict[str, str]:
    tenant_id = _resolve_tenant_id_by_slug(tenant_slug)
    if tenant_id is None:
        raise HTTPException(status_code=404, detail="Unknown tenant")

    enabled = _bool_setting(persistence.get_setting("email_channel_enabled", "false", tenant_id=tenant_id))
    if not enabled:
        raise HTTPException(status_code=503, detail="Email channel disabled")

    expected_token = (persistence.get_setting("postmark_inbound_token", "", tenant_id=tenant_id) or "").strip()
    require_token = bool(expected_token) and (settings.is_production or bool(x_arni_email_token))
    if require_token and not hmac.compare_digest(expected_token, (x_arni_email_token or "").strip()):
        logger.warning("webhook.email_forbidden", tenant_slug=tenant_slug, reason="invalid_token")
        raise HTTPException(status_code=403, detail="Invalid inbound email token")

    sender = (payload.From or "").strip().lower()
    content = (payload.TextBody or payload.HtmlBody or "").strip()
    if not sender or not content:
        return {"status": "ignored"}

    inbound = InboundMessage(
        message_id=(payload.MessageID or str(uuid4())).strip(),
        platform=Platform.EMAIL,
        user_id=sender,
        content=content,
        content_type="text",
        tenant_id=tenant_id,
        metadata={
            "from_email": sender,
            "to_email": (payload.To or "").strip().lower(),
            "subject": (payload.Subject or "").strip(),
            "in_reply_to": (payload.InReplyTo or "").strip(),
            "tenant_slug": tenant_slug,
        },
    )
    await redis_bus.publish(RedisBus.CHANNEL_INBOUND, inbound.model_dump_json())
    asyncio.create_task(process_and_reply(inbound))
    return {"status": "ok"}


@app.post("/voice/incoming/{tenant_slug}")
async def voice_incoming(tenant_slug: str, request: Request) -> Response:
    tenant_id = _resolve_tenant_id_by_slug(tenant_slug)
    if tenant_id is None:
        raise HTTPException(status_code=404, detail="Unknown tenant")

    enabled = _bool_setting(persistence.get_setting("voice_channel_enabled", "false", tenant_id=tenant_id))
    if not enabled:
        raise HTTPException(status_code=503, detail="Voice channel disabled")

    configured_stream = (persistence.get_setting("twilio_voice_stream_url", "", tenant_id=tenant_id) or "").strip()
    if configured_stream:
        stream_url = configured_stream
    else:
        host = request.headers.get("x-forwarded-host") or request.url.netloc
        proto = request.headers.get("x-forwarded-proto", "https")
        ws_proto = "wss" if proto == "https" else "ws"
        stream_url = f"{ws_proto}://{host}/voice/stream/{urllib.parse.quote(tenant_slug)}"

    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<Response><Connect><Stream url="{stream_url}"/></Connect></Response>'
    )
    return Response(content=twiml, media_type="application/xml")


@app.websocket("/voice/stream/{tenant_slug}")
async def voice_stream(ws: WebSocket, tenant_slug: str) -> None:
    await ws.accept()
    tenant_id = _resolve_tenant_id_by_slug(tenant_slug)
    if tenant_id is None:
        await ws.close(code=1008, reason="Unknown tenant")
        return
    logger.info("voice.stream.connected", tenant_slug=tenant_slug, tenant_id=tenant_id)
    try:
        while True:
            # Placeholder for Twilio <-> OpenAI Realtime bridge.
            await ws.receive_text()
    except WebSocketDisconnect:
        logger.info("voice.stream.disconnected", tenant_slug=tenant_slug, tenant_id=tenant_id)


# ──────────────────────────────────────────
# WebSocket Control – Ghost Mode (Task 1.6)
# ──────────────────────────────────────────

@app.websocket("/ws/control")
async def websocket_control(ws: WebSocket) -> None:
    """WebSocket endpoint for Admin Dashboard & Ghost Mode.

    Bidirectional channel for real-time control:
    - Admin can observe live messages (Ghost Mode)
    - Admin can inject messages into conversations
    - System events are pushed to connected admins

    BMAD Benchmark: WS Connect + Echo-Test bestanden
    """
    await ws.accept()
    active_websockets.append(ws)
    client_id = str(uuid4())[:8]
    logger.info("ws.connected", client_id=client_id, total=len(active_websockets))

    # Notify via Redis
    event = SystemEvent(
        event_type="admin.connected",
        source="gateway",
        payload={"client_id": client_id},
        severity="info",
    )
    try:
        await redis_bus.publish(RedisBus.CHANNEL_EVENTS, event.model_dump_json())
    except Exception:
        pass  # Redis may not be available

    try:
        while True:
            data = await ws.receive_text()
            logger.debug("ws.received", client_id=client_id, length=len(data))
            
            try:
                import json
                payload = json.loads(data)
                
                if payload.get("type") == "intervention":
                     # DEBUG LOG: See exactly what frontend sends
                     logger.info("ws.intervention_received", payload=payload)
                     
                     user_id = payload.get("user_id")
                     content = payload.get("content")
                     subtype = payload.get("subtype") # e.g. "request_contact"
                     
                     # Robust Platform Handling: Default to whatsapp, lower(), strip()
                     platform_str = payload.get("platform", "whatsapp").lower().strip()
                     
                     try:
                         platform = Platform(platform_str)
                     except ValueError:
                         logger.warning("ws.invalid_platform", platform=platform_str, default="whatsapp")
                         platform = Platform.WHATSAPP

                     if user_id:
                         # Case A: Contact Request (Special Flow)
                         if subtype == "request_contact" and platform == Platform.TELEGRAM:
                             msg_text = content or "Um deinen Account zu verifizieren, teile bitte deine Nummer."
                             await _telegram_bot.send_contact_request(user_id, msg_text)
                             logger.info("admin.contact_request", user_id=user_id)
                             
                             # Log as Assistant Message
                             from app.gateway.persistence import persistence
                             asyncio.create_task(asyncio.to_thread(
                                 persistence.save_message,
                                 user_id=user_id,
                                 role="assistant",
                                 content=f"[System] Contact Request: {msg_text}",
                                 platform=platform,
                                 metadata={"source": "admin", "type": "contact_request"},
                                 tenant_id=persistence.get_default_tenant_id(),
                             ))
                             
                         # Case B: Standard Message
                         elif content:
                             logger.info("admin.intervention", user_id=user_id, content=content, platform=platform)
                             
                             # Send to User
                             await send_to_user(user_id, platform, content)
                             
                             # Save to DB (Persistence)
                             # We use "assistant" role but mark it as admin in metadata
                             from app.gateway.persistence import persistence
                             asyncio.create_task(asyncio.to_thread(
                                 persistence.save_message,
                                 user_id=user_id,
                                 role="assistant",
                                 content=content,
                                 platform=platform,
                                 metadata={"source": "admin", "type": "intervention"},
                                 tenant_id=persistence.get_default_tenant_id(),
                             ))
                         
                         # Broadcast back to Admins (so others see it)
                         # ... existing broadcast code ...
                         if content or subtype == "request_contact": # Only broadcast if content exists, or we construct a fake one for req_contact
                             response_content = content or "[System Requested Contact]"
                             await broadcast_to_admins({
                                 "type": "ghost.message_out",
                                 "message_id": f"admin-{datetime.now().timestamp()}",
                                 "user_id": "Admin",
                                 "response": response_content,
                                 "platform": platform
                             })
                         
            except json.JSONDecodeError:
                # Echo legacy fallback
                await ws.send_json({
                    "type": "echo",
                    "client_id": client_id,
                    "data": data,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                logger.error("ws.handler_failed", error=str(e), data_preview=data[:100])
    except WebSocketDisconnect:
        active_websockets.remove(ws)
        logger.info("ws.disconnected", client_id=client_id, total=len(active_websockets))


# ──────────────────────────────────────────
# Swarm Router Integration (Task 2.10)
# ──────────────────────────────────────────

from app.swarm.llm import LLMClient
from app.swarm.router.router import SwarmRouter

_llm_client = LLMClient(openai_api_key=settings.openai_api_key)
_swarm_router = SwarmRouter(llm=_llm_client)
_telegram_bot = TelegramBot(
    bot_token=settings.telegram_bot_token,
    admin_chat_id=settings.telegram_admin_chat_id,
)
_wa_mode = persistence.get_setting("whatsapp_mode", None) or "qr"
_bridge_health = (
    persistence.get_setting("bridge_health_url", None) or "http://localhost:3000/health"
)
_bridge_base = _bridge_health.rsplit("/health", 1)[0].rstrip("/")
_whatsapp_verifier = WhatsAppClient(
    access_token=settings.meta_access_token,
    phone_number_id=settings.meta_phone_number_id,
    app_secret=settings.meta_app_secret,
    bridge_url=_bridge_base if _wa_mode == "qr" else "",
)


@app.post("/swarm/route")
async def swarm_route(message: InboundMessage) -> dict[str, Any]:
    """Route an inbound message through the Swarm Router.

    Flow: InboundMessage → Intent Classification → Agent → Response
    BMAD Benchmark: E2E Pipeline (Redis → Router → Agent → Response)
    """
    try:
        result = await _swarm_router.route(message)
        logger.info(
            "swarm.routed",
            message_id=message.message_id,
            agent_confidence=result.confidence,
            requires_confirmation=result.requires_confirmation,
        )
        return {
            "status": "ok",
            "response": result.content,
            "confidence": result.confidence,
            "requires_confirmation": result.requires_confirmation,
            "metadata": result.metadata,
        }
    except Exception as e:
        logger.error("swarm.route_failed", error=str(e), message_id=message.message_id)
        import random
        return {
            "status": "error",
            "response": random.choice(ARNI_ERROR_MESSAGES),
            "confidence": 0.0,
            "requires_confirmation": False,
            "metadata": {"error": True},
        }


def _runtime_setting_value(key: str, env_attr: str, default: str = "", tenant_id: int | None = None) -> str:
    db_value = persistence.get_setting(key, None, tenant_id=tenant_id)
    if db_value is not None and str(db_value).strip() != "":
        return str(db_value)
    return str(getattr(settings, env_attr, default) or default)


def _is_truthy(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


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


def _wants_human_handoff(content: str) -> bool:
    cleaned = (content or "").strip().lower()
    if not cleaned:
        return False
    if any(word in cleaned for word in HANDOFF_KEYWORDS):
        return True
    return "jemand" in cleaned and ("sprechen" in cleaned or "verbinden" in cleaned)


async def _send_verification_email(
    to_email: str,
    token: str,
    member_name: str | None = None,
    tenant_id: int | None = None,
) -> bool:
    host = _runtime_setting_value("smtp_host", "smtp_host", tenant_id=tenant_id)
    port_raw = _runtime_setting_value("smtp_port", "smtp_port", "587", tenant_id=tenant_id)
    username = _runtime_setting_value("smtp_username", "smtp_username", tenant_id=tenant_id)
    password = _runtime_setting_value("smtp_password", "smtp_password", tenant_id=tenant_id)
    from_email = _runtime_setting_value("smtp_from_email", "smtp_from_email", username, tenant_id=tenant_id)
    from_name = _runtime_setting_value("smtp_from_name", "smtp_from_name", "Arni", tenant_id=tenant_id)
    subject = _runtime_setting_value(
        "verification_email_subject",
        "verification_email_subject",
        "Dein ARNI Verifizierungscode",
        tenant_id=tenant_id,
    )
    use_starttls = _is_truthy(
        _runtime_setting_value("smtp_use_starttls", "smtp_use_starttls", "true", tenant_id=tenant_id),
        default=True,
    )

    if not all([host, username, password, from_email]):
        logger.warning("gateway.verification.smtp_missing_config")
        return False

    greeting_name = member_name.strip() if member_name else ""
    greeting = f"Hallo {greeting_name}," if greeting_name else "Hallo,"
    body = (
        f"{greeting}\n\n"
        "dein ARNI Verifizierungscode lautet:\n\n"
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
    """Process inbound message through Swarm Router and reply via WhatsApp Bridge.

    Flow: InboundMessage → SwarmRouter → AgentResponse → Bridge /send → WhatsApp
    Emergency: metadata.action == 'emergency_alert' → Telegram Admin Alert (AGENTS.md §2)
    Error: Arni-style fallback (AGENTS.md §4) – no stack traces to user
    """
    try:
        from config.settings import get_settings
        settings = get_settings()
        
        # PERSISTENCE: Save Inbound User Message
        from app.gateway.persistence import persistence
        from app.gateway.redis_bus import RedisBus
        import json
        import random
        import re
        
        # Sprint 13: Extract User Name for Session Update
        user_name_extracted = None
        phone_number_extracted = None
        member_id_extracted = None
        
        # --- A. Telegram Metadata ---
        if message.platform == Platform.TELEGRAM:
             # Try to construct a nice display name
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

        # --- B. Token Verification Logic ---
        content = message.content.strip() if message.content else ""
        logger.info("gateway.check_token", is_digit=content.isdigit(), len=len(content))
        
        if re.match(r"^\d{6}$", content):
            token = content
            logger.info("gateway.token_matched")
            
            # Check Redis
            bus = None
            try:
                bus = RedisBus(settings.redis_url)
                await bus.connect()
                
                t_id = message.tenant_id or persistence.get_default_tenant_id() or 0
                data_str = await bus.client.get(token_key(t_id, token))
                if data_str:
                    # Valid Token!
                    if isinstance(data_str, bytes):
                        data_str = data_str.decode("utf-8")
                    data = json.loads(data_str)

                    member_id_extracted = data.get("member_id")
                    token_user_id = data.get("user_id")
                    token_phone_number = data.get("phone_number")
                    if token_user_id and str(token_user_id) != str(message.user_id):
                        logger.warning(
                            "gateway.token_user_mismatch",
                            token_user_id=token_user_id,
                            current_user_id=message.user_id,
                        )
                        await send_to_user(
                            message.user_id,
                            message.platform,
                            "⚠️ Dieser Code gehört zu einem anderen Account.",
                        )
                        return

                    if not member_id_extracted:
                        phone_candidate = token_phone_number or phone_number_extracted
                        if not phone_candidate:
                            existing_session = await asyncio.to_thread(
                                persistence.get_or_create_session,
                                message.user_id,
                                message.platform,
                                tenant_id=message.tenant_id,
                            )
                            phone_candidate = existing_session.phone_number

                        if phone_candidate:
                            matched_member = await asyncio.to_thread(match_member_by_phone, phone_candidate, message.tenant_id)
                            if matched_member:
                                member_id_extracted = matched_member.member_number or str(matched_member.customer_id)
                                logger.info(
                                    "gateway.token_member_resolved_by_phone",
                                    user_id=message.user_id,
                                    member_id=member_id_extracted,
                                )
                    if member_id_extracted:
                        # Consume token only for completed verification.
                        await bus.client.delete(token_key(t_id, token))
                        if token_user_id:
                            await bus.client.delete(user_token_key(t_id, str(token_user_id)))
                        logger.info("gateway.token_verified", user_id=message.user_id, member_id=member_id_extracted)

                        # Auto-Reply Success
                        await send_to_user(message.user_id, message.platform, "✅ Verifizierung erfolgreich! Dein Account ist nun verknüpft.")

                        # Log System Reply
                        asyncio.create_task(asyncio.to_thread(
                            persistence.save_message,
                            user_id=message.user_id,
                            role="assistant",
                            content="✅ Verifizierung erfolgreich! Dein Account ist nun verknüpft.",
                            platform=message.platform,
                            metadata={"source": "system", "type": "verification"},
                            tenant_id=message.tenant_id,
                        ))

                        # Update Session with Member ID (Verification Complete)
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
                            tenant_id=message.tenant_id,
                        ))
                        return # Stop processing

                    # Token exists but cannot be mapped to a member yet.
                    await send_to_user(
                        message.user_id,
                        message.platform,
                        "⚠️ Code erkannt, aber noch keine Zuordnung möglich. Bitte teile zuerst deine Telefonnummer über den Kontakt-Button.",
                    )
                    asyncio.create_task(asyncio.to_thread(
                        persistence.save_message,
                        user_id=message.user_id,
                        role="assistant",
                        content="⚠️ Code erkannt, aber noch keine Zuordnung möglich. Bitte teile zuerst deine Telefonnummer über den Kontakt-Button.",
                        platform=message.platform,
                        metadata={"source": "system", "type": "verification_pending_contact"},
                        tenant_id=message.tenant_id,
                    ))
                    return
            except Exception as e:
                logger.error("gateway.token_check_failed", error=str(e))
            finally:
                if bus:
                    await bus.disconnect()
        
        # --- C. Verification Gate ---
        session = await asyncio.to_thread(
            persistence.get_or_create_session,
            message.user_id,
            message.platform,
            tenant_id=message.tenant_id,
        )

        if not session.member_id:
            # Not verified!
            logger.info("gateway.unverified_user_blocked", user_id=message.user_id)
            
            # Save the user attempt
            asyncio.create_task(asyncio.to_thread(
                persistence.save_message,
                user_id=message.user_id,
                role="user",
                content=message.content,
                platform=message.platform,
                metadata=message.metadata,
                user_name=user_name_extracted,
                phone_number=phone_number_extracted,
                tenant_id=message.tenant_id,
                # No member_id update here
            ))

            phone_for_match = phone_number_extracted or session.phone_number
            reply_text = "🔒 **Verifizierung erforderlich**\n\nBitte teile zuerst deine Telefonnummer über den Kontakt-Button."
            reply_type = "verification_required"

            if phone_number_extracted and session.phone_number != phone_number_extracted:
                await asyncio.to_thread(
                    persistence.get_or_create_session,
                    message.user_id,
                    message.platform,
                    user_name_extracted,
                    phone_number_extracted,
                    None,
                    message.tenant_id,
                )
                phone_for_match = phone_number_extracted

            if phone_for_match:
                try:
                    matched_member = await asyncio.to_thread(match_member_by_phone, phone_for_match, message.tenant_id)
                    if matched_member:
                        member_id = matched_member.member_number or str(matched_member.customer_id)
                        member_email = matched_member.email
                        if member_email:
                            active_token: str | None = None
                            bus = RedisBus(settings.redis_url)
                            await bus.connect()
                            try:
                                tid = message.tenant_id or persistence.get_default_tenant_id() or 0
                                existing_token_val = await bus.client.get(user_token_key(tid, message.user_id))
                                if existing_token_val:
                                    active_token = (
                                        existing_token_val.decode("utf-8")
                                        if isinstance(existing_token_val, bytes)
                                        else str(existing_token_val)
                                    )
                                if not active_token:
                                    active_token = f"{random.randint(0, 999999):06d}"
                                    token_data = {
                                        "member_id": member_id,
                                        "user_id": message.user_id,
                                        "phone_number": phone_for_match,
                                        "email": member_email,
                                    }
                                    await bus.client.setex(token_key(tid, active_token), 86400, json.dumps(token_data))
                                    await bus.client.setex(user_token_key(tid, message.user_id), 86400, active_token)
                                    logger.info(
                                        "gateway.verification.token_issued_email",
                                        user_id=message.user_id,
                                        member_id=member_id,
                                    )
                            finally:
                                await bus.disconnect()

                            sent = await _send_verification_email(
                                to_email=member_email,
                                token=active_token or "",
                                member_name=f"{matched_member.first_name} {matched_member.last_name}".strip(),
                                tenant_id=message.tenant_id,
                            )
                            if sent:
                                reply_text = (
                                    "📨 Ich habe dir einen 6-stelligen Verifizierungscode per E-Mail gesendet an "
                                    f"{_mask_email(member_email)}.\n\n"
                                    "Bitte sende den Code hier im Chat."
                                )
                                reply_type = "verification_code_sent"
                            else:
                                reply_text = (
                                    "⚠️ Ich konnte gerade keine Verifizierungs-E-Mail senden.\n\n"
                                    "Bitte versuche es gleich erneut oder kontaktiere den Support."
                                )
                                reply_type = "verification_email_failed"
                        else:
                            reply_text = (
                                "⚠️ Ich habe dich gefunden, aber es ist keine E-Mail im Mitgliederprofil hinterlegt.\n\n"
                                "Bitte melde dich kurz beim Studio-Team für die Verifizierung."
                            )
                            reply_type = "verification_email_missing"
                    else:
                        reply_text = (
                            "⚠️ Ich konnte deine Nummer noch keinem Mitglied zuordnen.\n\n"
                            "Bitte prüfe, ob deine Nummer in Magicline hinterlegt ist."
                        )
                        reply_type = "verification_no_member_match"
                except Exception as match_err:
                    logger.error("gateway.verification.failed", error=str(match_err), traceback=True)
                    reply_text = "⚠️ Die Verifizierung ist gerade nicht verfügbar. Bitte versuche es erneut."
                    reply_type = "verification_error"

            if message.platform == Platform.TELEGRAM:
                await _telegram_bot.send_message(
                    message.user_id,
                    reply_text,
                    reply_markup={
                        "keyboard": [[{"text": "📱 Telefonnummer teilen", "request_contact": True}]],
                        "resize_keyboard": True,
                        "one_time_keyboard": True,
                    }
                )
            else:
                await send_to_user(message.user_id, message.platform, reply_text)
            
            asyncio.create_task(asyncio.to_thread(
                persistence.save_message,
                user_id=message.user_id,
                role="assistant",
                content=reply_text,
                platform=message.platform,
                metadata={"source": "system", "type": reply_type},
                tenant_id=message.tenant_id,
            ))
            return

        if _wants_human_handoff(message.content):
            logger.info("gateway.handoff.requested", user_id=message.user_id, platform=message.platform)
            _hm_key = human_mode_key(message.tenant_id or persistence.get_default_tenant_id() or 0, message.user_id)
            try:
                await redis_bus.client.setex(_hm_key, 86400, "true")
            except Exception as e:
                logger.error("gateway.handoff.set_failed", user_id=message.user_id, error=str(e))
                fallback_bus = None
                try:
                    fallback_bus = RedisBus(settings.redis_url)
                    await fallback_bus.connect()
                    await fallback_bus.client.setex(_hm_key, 86400, "true")
                except Exception as fallback_error:
                    logger.error("gateway.handoff.fallback_set_failed", user_id=message.user_id, error=str(fallback_error))
                finally:
                    if fallback_bus:
                        await fallback_bus.disconnect()

            # Persist user request + system acknowledgement so Escalations and Live history are consistent.
            asyncio.create_task(asyncio.to_thread(
                persistence.save_message,
                user_id=message.user_id,
                role="user",
                content=message.content,
                platform=message.platform,
                metadata=message.metadata,
                user_name=user_name_extracted,
                phone_number=phone_number_extracted,
                member_id=session.member_id,
                tenant_id=message.tenant_id,
            ))
            handoff_reply = "Alles klar. Ich habe einen Kollegen aus dem Team für dich angefragt. Bitte kurz dranbleiben."
            await send_to_user(message.user_id, message.platform, handoff_reply)
            asyncio.create_task(asyncio.to_thread(
                persistence.save_message,
                user_id=message.user_id,
                role="assistant",
                content=handoff_reply,
                platform=message.platform,
                metadata={"source": "system", "type": "handoff_requested"},
                tenant_id=message.tenant_id,
            ))
            await broadcast_to_admins({
                "type": "ghost.message_out",
                "message_id": f"handoff-{datetime.now().timestamp()}",
                "user_id": "Arni",
                "response": handoff_reply,
                "platform": message.platform,
            })
            return

        # Pre-process Voice (Sprint 11)
        if message.content_type == "voice" and message.platform == Platform.TELEGRAM:
            # US-11.4: Async Voice Worker
            # Offload heavy voice processing to Redis Queue
            try:
                await redis_bus.push_to_queue(
                    RedisBus.CHANNEL_VOICE_QUEUE, 
                    message.model_dump_json()
                )
                logger.info("swarm.voice_queued", message_id=message.message_id)
                # Return immediately - Worker will handle reply
                return
            except Exception as e:
                logger.error("swarm.voice_queue_failed", error=str(e))
                # Fallback: Continue inline or fail? 
                # For now let's just log and fail to avoid blocking Gateway
                return

        # Broadcast Inbound to Ghost Mode admins
        await broadcast_to_admins({
            "type": "ghost.message_in",
            "message_id": message.message_id,
            "user_id": message.user_id,
            "content": message.content,
            "platform": message.platform,
        })

        # Attach active dialog context (if any) so Router/Agent can resolve follow-ups deterministically.
        dialog_ctx_key = dialog_context_key(message.tenant_id or persistence.get_default_tenant_id() or 0, message.user_id)
        raw_dialog_ctx = await redis_bus.client.get(dialog_ctx_key)
        if raw_dialog_ctx:
            try:
                parsed_ctx = json.loads(raw_dialog_ctx)
                if isinstance(parsed_ctx, dict):
                    message.metadata = dict(message.metadata or {})
                    message.metadata["dialog_context"] = parsed_ctx
            except Exception:
                logger.warning("gateway.dialog_context_parse_failed", user_id=message.user_id)

        # PERSISTENCE: Save Inbound User Message
        asyncio.create_task(asyncio.to_thread(
            persistence.save_message,
            user_id=message.user_id,
            role="user",
            content=message.content,
            platform=message.platform,
            metadata=message.metadata,
            user_name=user_name_extracted,
            phone_number=phone_number_extracted,
            member_id=member_id_extracted,
            tenant_id=message.tenant_id,
        ))

        # Feature gate: check monthly message limit before processing (S4.2)
        _t_id_gate = message.tenant_id or persistence.get_default_tenant_id() or 1
        try:
            from app.core.feature_gates import FeatureGate
            _gate = FeatureGate(tenant_id=_t_id_gate)
            _gate.check_message_limit()
        except HTTPException:
            raise
        except Exception as _gate_err:
            logger.warning("gateway.feature_gate_failed", error=str(_gate_err))

        result = await _swarm_router.route(message)
        logger.info(
            "swarm.reply_generated",
            message_id=message.message_id,
            confidence=result.confidence,
        )

        # Track usage (S4.2) — non-fatal
        try:
            _gate.increment_inbound_usage()
            _gate.increment_outbound_usage()
        except Exception as _usage_err:
            logger.warning("gateway.usage_tracking_failed", error=str(_usage_err))

        # Persist/clear structured dialog context from agent metadata.
        if result.metadata and isinstance(result.metadata.get("dialog_context"), dict):
            dialog_context = result.metadata["dialog_context"]
            if dialog_context.get("clear"):
                await redis_bus.client.delete(dialog_ctx_key)
                logger.info("gateway.dialog_context_cleared", user_id=message.user_id)
            else:
                await redis_bus.client.setex(dialog_ctx_key, 1800, json.dumps(dialog_context))
                logger.info(
                    "gateway.dialog_context_set",
                    user_id=message.user_id,
                    pending_action=dialog_context.get("pending_action"),
                )

        # Emergency Alert → Telegram (AGENTS.md §2)
        if result.metadata and result.metadata.get("action") == "emergency_alert":
            try:
                await _telegram_bot.send_emergency_alert(
                    user_id=message.user_id,
                    message_content=message.content,
                )
                logger.critical("medic.emergency_telegram_sent", user_id=message.user_id)
            except Exception as tg_err:
                logger.error("telegram.alert_failed", error=str(tg_err))

        # Send reply via WhatsApp Bridge or Telegram
        # Simplified using send_to_user helper (Refactored Sprint 13)
        if result.content:
             # Extract Voice Logic (kept inline or moved? keeping inline for now as it's complex)
             # Actually, let's keep the complex voice logic for Telegram here, 
             # but use send_to_user for Text.
             
             if message.platform == Platform.TELEGRAM:
                 # Check for Voice requirement
                 original_type = message.metadata.get("original_type", "text")
                 if original_type == "voice":
                      # ... existing voice logic ...
                      # For now invoking the same logic or skipping refactor for Voice to avoid breaking it.
                      # Let's just use send_to_user for the simple cases.
                     pass 
             
             # PERSISTENCE: Save Outbound Assistant Message
             # Save BEFORE sending to ensure we have a record even if delivery fails
             # Note: Ideally we'd update status to "sent" or "failed" later, but for now just logging content is key
             assistant_metadata = {"confidence": result.confidence, "source": "swarm"}
             if isinstance(result.metadata, dict):
                 assistant_metadata.update(result.metadata)

             asyncio.create_task(asyncio.to_thread(
                 persistence.save_message,
                 user_id=message.user_id,
                 role="assistant",
                 content=result.content,
                 platform=message.platform,
                 metadata=assistant_metadata,
                 user_name=user_name_extracted, # Use same name extraction to keep session updated
                 tenant_id=message.tenant_id,
             ))
             
             # Attempt Delivery
             outbound_meta = dict(message.metadata or {})
             if message.tenant_id is not None and "tenant_id" not in outbound_meta:
                 outbound_meta["tenant_id"] = message.tenant_id
             await send_to_user(
                 user_id=message.user_id,
                 platform=message.platform,
                 content=result.content,
                 metadata=outbound_meta,
             )

        # Publish outbound to Redis (for Dashboard/Ghost Mode)
        outbound = OutboundMessage(
            message_id=f"resp-{message.message_id}",
            platform=message.platform,
            user_id=message.user_id,
            content=result.content,
            reply_to=message.message_id,
            tenant_id=message.tenant_id,
        )
        await redis_bus.publish(RedisBus.CHANNEL_OUTBOUND, outbound.model_dump_json())

        # Save to DB (Persistence)
        asyncio.create_task(save_outbound_to_db(outbound))

        # Broadcast to Ghost Mode admins
        await broadcast_to_admins({
            "type": "ghost.message_out",
            "message_id": message.message_id,
            "response": result.content,
        })
    except Exception as e:
        logger.error("swarm.reply_failed", error=str(e), message_id=message.message_id)

        # Send Arni-style error to user (AGENTS.md §4)
        import random
        error_msg = random.choice(ARNI_ERROR_MESSAGES)
        try:
            if message.platform == Platform.WHATSAPP:
                await _whatsapp_verifier.send_text(message.user_id, error_msg)
                logger.info("bridge.error_reply_sent", to=message.user_id)
            elif message.platform == Platform.TELEGRAM:
                await send_to_user(
                    message.user_id,
                    message.platform,
                    "Kurz ein technischer Fehler. Schreib mir bitte nochmal.",
                    metadata=message.metadata,
                )
                
                # PERSISTENCE: Save System/Error Message
                asyncio.create_task(asyncio.to_thread(
                    persistence.save_message,
                    user_id=message.user_id,
                    role="assistant",
                    content="Kurz ein technischer Fehler. Schreib mir bitte nochmal.",
                    platform=message.platform,
                    metadata={"source": "system", "type": "error", "error_type": "exception"},
                    tenant_id=message.tenant_id,
                ))

                # BROADCAST: Live update for Admin Ghost Mode
                try:
                    await broadcast_to_admins({
                        "type": "ghost.message_out",
                        "message_id": f"error-{message.message_id}",
                        "user_id": message.user_id,
                        "response": "Kurz ein technischer Fehler. Schreib mir bitte nochmal.",
                        "platform": message.platform
                    })
                except Exception:
                    pass # Don't fail the error handler
        except Exception:
            logger.error("bridge.error_reply_failed")

        # Alert admin about system error
        try:
            await _telegram_bot.send_alert(
                f"System-Fehler bei Nachricht von {message.user_id[:5]}****:\n<code>{str(e)[:200]}</code>",
                severity="error",
            )
        except Exception:
            pass


async def process_inbound(message_json: str) -> None:
    """Legacy: Process an inbound Redis message (for Redis subscriber path)."""
    try:
        message = InboundMessage.model_validate_json(message_json)
        await process_and_reply(message)
    except Exception as e:
        logger.error("swarm.process_failed", error=str(e))



# ──────────────────────────────────────────
# Utility: Send Message to User (Bridge/Telegram)
# ──────────────────────────────────────────

async def _send_sms_via_twilio(*, to: str, content: str, tenant_id: int | None) -> None:
    resolved_tenant = tenant_id or persistence.get_default_tenant_id()
    sid = persistence.get_setting("twilio_account_sid", "", tenant_id=resolved_tenant) or ""
    token = persistence.get_setting("twilio_auth_token", "", tenant_id=resolved_tenant) or ""
    from_number = persistence.get_setting("twilio_sms_number", "", tenant_id=resolved_tenant) or ""
    if not sid or not token or not from_number:
        raise RuntimeError("Twilio SMS config incomplete")
    async with httpx.AsyncClient(timeout=20.0, auth=(sid, token)) as client:
        resp = await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data={"To": to, "From": from_number, "Body": content},
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"Twilio SMS failed ({resp.status_code})")


async def _send_email_via_postmark(*, to_email: str, subject: str, content: str, tenant_id: int | None) -> None:
    resolved_tenant = tenant_id or persistence.get_default_tenant_id()
    token = persistence.get_setting("postmark_server_token", "", tenant_id=resolved_tenant) or ""
    from_email = persistence.get_setting("email_outbound_from", "", tenant_id=resolved_tenant) or ""
    if not token or not from_email:
        raise RuntimeError("Postmark email config incomplete")
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
            await _whatsapp_verifier.send_text(user_id, content)
            logger.info("bridge.reply_sent", to=user_id)

        elif platform == Platform.TELEGRAM:
             # Send via Telegram API
             # Meta: use chat_id from metadata if available, else user_id
             chat_id = metadata.get("chat_id", user_id)
             # Use parse_mode=None to avoid Markdown errors with raw user input
             await _telegram_bot.send_message(chat_id, content, parse_mode=None)
             logger.info("telegram.reply_sent", to=chat_id)
        elif platform == Platform.SMS:
            await _send_sms_via_twilio(
                to=user_id,
                content=content[:1550],
                tenant_id=metadata.get("tenant_id"),
            )
            logger.info("sms.reply_sent", to=user_id)
        elif platform == Platform.EMAIL:
            subject = (metadata.get("subject") or "Re: Deine Nachricht an ARNI").strip()[:150]
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
            logger.warning("gateway.unknown_platform", platform=platform, user_id=user_id)
             
    except Exception as e:
        logger.error("gateway.send_failed", error=str(e), user_id=user_id, platform=platform)
        raise e


# ──────────────────────────────────────────
# Utility: Broadcast to all WebSocket clients
# ──────────────────────────────────────────

async def broadcast_to_admins(message: dict[str, Any]) -> None:
    """Send a message to all connected WebSocket clients (Admin Dashboard)."""
    disconnected: list[WebSocket] = []
    for ws in active_websockets:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        active_websockets.remove(ws)

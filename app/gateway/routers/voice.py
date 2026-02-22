"""ARIIA v1.4 – Voice Router.

Handles incoming voice calls (Twilio) and real-time media streams.
"""

import urllib.parse
from uuid import uuid4

import structlog
from fastapi import APIRouter, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from app.gateway.persistence import persistence
from app.gateway.dependencies import get_settings
from app.core.models import Tenant
from app.core.db import SessionLocal

logger = structlog.get_logger()
router = APIRouter(tags=["voice"])

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


@router.post("/voice/incoming/{tenant_slug}")
async def voice_incoming(tenant_slug: str, request: Request) -> Response:
    """Twilio Voice Webhook: Initiates a call."""
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


@router.websocket("/voice/stream/{tenant_slug}")
async def voice_stream(ws: WebSocket, tenant_slug: str) -> None:
    """Real-time Voice Stream (Twilio Media Stream)."""
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

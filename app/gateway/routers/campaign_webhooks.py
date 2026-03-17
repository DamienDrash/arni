"""app/gateway/routers/campaign_webhooks.py — Campaign delivery tracking webhooks."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import CampaignRecipient
from config.settings import get_settings

logger = structlog.get_logger()

router = APIRouter(prefix="/webhooks/campaigns", tags=["campaign-webhooks"])


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class DeliveryEvent(BaseModel):
    event_type: str  # delivered | opened | clicked | bounced | unsubscribed
    campaign_id: int
    recipient_id: int
    contact_id: int
    tenant_id: int
    timestamp: str


# ══════════════════════════════════════════════════════════════════════════════
# HMAC SIGNATURE VERIFICATION (MANDATORY)
# ══════════════════════════════════════════════════════════════════════════════

async def require_valid_webhook_signature(
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    """Mandatory HMAC verification — rejects unsigned requests."""
    from app.gateway.persistence import persistence

    secret = persistence.get_webhook_secret(provider, db) if hasattr(persistence, "get_webhook_secret") else None
    if not secret:
        s = get_settings()
        secret = getattr(s, f"{provider.upper()}_WEBHOOK_SECRET", None) or getattr(s, "CAMPAIGN_WEBHOOK_SECRET", None)

    if not secret:
        raise HTTPException(status_code=503, detail=f"Webhook secret not configured for provider: {provider}")

    signature = request.headers.get("X-Signature") or request.headers.get("X-Hub-Signature-256") or request.headers.get("X-Ariia-Signature")
    if not signature:
        raise HTTPException(status_code=401, detail="Missing webhook signature")

    body = await request.body()
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


# ══════════════════════════════════════════════════════════════════════════════
# POST /webhooks/campaigns/delivery
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/delivery")
async def receive_delivery_event(
    request: Request,
    db: Session = Depends(get_db),
):
    """Receive delivery status callbacks from channel providers.

    Writes events to a Redis stream for async processing.
    Returns 200 OK immediately (non-blocking).
    HMAC signature is mandatory.
    """
    await require_valid_webhook_signature("campaign", request, db)

    raw_body = await request.body()

    # Parse and validate body
    try:
        event = DeliveryEvent(**json.loads(raw_body))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    # Push to Redis stream for async analytics processing
    try:
        from app.gateway.dependencies import redis_bus
        if redis_bus._client:
            await redis_bus._client.xadd(
                "campaign:analytics_events",
                {
                    "event_type": event.event_type,
                    "campaign_id": str(event.campaign_id),
                    "recipient_id": str(event.recipient_id),
                    "contact_id": str(event.contact_id),
                    "tenant_id": str(event.tenant_id),
                    "timestamp": event.timestamp,
                },
            )
    except Exception as exc:
        # Non-blocking: log error but still return OK
        logger.error(
            "campaign_webhook.redis_xadd_failed",
            error=str(exc),
            campaign_id=event.campaign_id,
        )

    return {"status": "ok"}


# ══════════════════════════════════════════════════════════════════════════════
# GET /webhooks/campaigns/unsubscribe
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/unsubscribe", response_class=HTMLResponse)
async def one_click_unsubscribe(
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """One-click unsubscribe link handler.

    Token format: base64url("tenant_id:contact_id:campaign_id")
    Sets CampaignRecipient status to 'unsubscribed'.
    """
    try:
        # Decode token (base64url → "tenant_id:contact_id:campaign_id")
        padding = "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(token + padding).decode("utf-8")
        parts = decoded.split(":")
        if len(parts) != 3:
            raise ValueError("Invalid token format")
        tenant_id = int(parts[0])
        contact_id = int(parts[1])
        campaign_id = int(parts[2])
    except Exception:
        return HTMLResponse(
            content=_error_html("Ungültiger Abmelde-Link."),
            status_code=400,
        )

    # Find recipient — enforce tenant_id scoping
    recipient = db.query(CampaignRecipient).filter(
        CampaignRecipient.campaign_id == campaign_id,
        CampaignRecipient.contact_id == contact_id,
        CampaignRecipient.tenant_id == tenant_id,
    ).first()

    if not recipient:
        return HTMLResponse(
            content=_error_html("Empfänger nicht gefunden."),
            status_code=400,
        )

    recipient.status = "unsubscribed"
    db.commit()

    logger.info(
        "campaign_webhook.unsubscribed",
        campaign_id=campaign_id,
        contact_id=contact_id,
        tenant_id=tenant_id,
    )

    return HTMLResponse(content=_success_html())


# ══════════════════════════════════════════════════════════════════════════════
# HTML TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════

def _success_html() -> str:
    return """<!DOCTYPE html>
<html lang="de">
<head><meta charset="utf-8"><title>Abmeldung</title>
<style>body{font-family:sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;background:#f5f5f5}
.card{background:#fff;padding:2rem;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.1);text-align:center;max-width:400px}</style>
</head>
<body><div class="card"><h2>Abmeldung erfolgreich</h2><p>Sie wurden erfolgreich abgemeldet. Sie erhalten keine weiteren Nachrichten dieser Kampagne.</p></div></body>
</html>"""


def _error_html(message: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="utf-8"><title>Fehler</title>
<style>body{{font-family:sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;background:#f5f5f5}}
.card{{background:#fff;padding:2rem;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.1);text-align:center;max-width:400px;color:#c0392b}}</style>
</head>
<body><div class="card"><h2>Fehler</h2><p>{message}</p></div></body>
</html>"""

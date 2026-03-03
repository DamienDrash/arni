"""ARIIA v2.2 – Analytics Tracking Ingestion Endpoints.

Public (no auth) endpoints for tracking pixel opens, link clicks,
and channel webhooks. Events are pushed to a Redis queue for
asynchronous processing by the analytics worker.

@ARCH: Campaign Refactoring Phase 3, Task 3.3
"""
from __future__ import annotations

import json
import os
import time
from urllib.parse import unquote

import structlog
from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse, Response

logger = structlog.get_logger()

router = APIRouter(tags=["tracking"])

# 1x1 transparent GIF (43 bytes)
TRANSPARENT_GIF = (
    b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
    b"\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00"
    b"\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02"
    b"\x44\x01\x00\x3b"
)

# Known bot user-agent patterns to filter out
BOT_PATTERNS = [
    "googlebot", "bingbot", "yahoo", "baidu", "yandex",
    "bot", "crawler", "spider", "slurp", "mediapartners",
    "facebookexternalhit", "twitterbot", "linkedinbot",
    "whatsapp", "telegrambot", "applebot",
    "mail.ru", "seznambot", "duckduckbot",
    # Email pre-fetch / link scanners
    "mimecast", "barracuda", "proofpoint", "symantec",
    "messagelabs", "forcepoint",
]

REDIS_QUEUE_KEY = "campaign:analytics:events"


def _get_redis():
    """Lazy Redis connection."""
    import redis
    redis_url = os.environ.get("REDIS_URL", "redis://ariia-redis:6379/0")
    return redis.Redis.from_url(redis_url, decode_responses=True)


def _is_bot(user_agent: str) -> bool:
    """Check if the user-agent looks like a bot or email scanner."""
    if not user_agent:
        return False
    ua_lower = user_agent.lower()
    return any(pattern in ua_lower for pattern in BOT_PATTERNS)


def _push_event(event: dict):
    """Push a tracking event to the Redis queue for async processing."""
    try:
        r = _get_redis()
        r.rpush(REDIS_QUEUE_KEY, json.dumps(event))
    except Exception as e:
        logger.error("tracking.redis_push_failed", error=str(e))


# ── Open Tracking (Pixel) ────────────────────────────────────────────

@router.get("/track/open/{recipient_id}")
async def track_open(recipient_id: int, request: Request):
    """Tracking pixel endpoint. Returns a 1x1 transparent GIF.

    Called by email clients when the email is rendered. Writes an
    'opened' event to the Redis queue for async processing.
    """
    user_agent = request.headers.get("user-agent", "")
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "")

    if not _is_bot(user_agent):
        _push_event({
            "event_type": "opened",
            "recipient_id": recipient_id,
            "user_agent": user_agent,
            "ip_address": ip.split(",")[0].strip() if ip else "",
            "timestamp": time.time(),
        })

    return Response(
        content=TRANSPARENT_GIF,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


# ── Click Tracking (Link Redirect) ───────────────────────────────────

@router.get("/track/click/{recipient_id}")
async def track_click(
    recipient_id: int,
    request: Request,
    url: str = Query(..., description="Original destination URL"),
):
    """Link click tracker. Records the click and redirects to the target URL.

    All links in campaign emails are rewritten to pass through this
    endpoint. The original URL is passed as a query parameter.
    """
    user_agent = request.headers.get("user-agent", "")
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "")
    decoded_url = unquote(url)

    if not _is_bot(user_agent):
        _push_event({
            "event_type": "clicked",
            "recipient_id": recipient_id,
            "url": decoded_url,
            "user_agent": user_agent,
            "ip_address": ip.split(",")[0].strip() if ip else "",
            "timestamp": time.time(),
        })

    return RedirectResponse(url=decoded_url, status_code=302)


# ── Channel Webhooks ──────────────────────────────────────────────────

@router.post("/track/webhook/{channel}")
async def track_webhook(channel: str, request: Request):
    """Webhook receiver for channel-specific status updates.

    Handles delivery receipts, bounces, and unsubscribes from
    email providers (SendGrid, Mailgun), WhatsApp Business API,
    Twilio SMS, etc.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    logger.info("tracking.webhook_received", channel=channel, payload_keys=list(body.keys()))

    # Normalize events from different providers
    events = _normalize_webhook_events(channel, body)
    for event in events:
        _push_event(event)

    return {"status": "ok", "events_queued": len(events)}


def _normalize_webhook_events(channel: str, payload: dict) -> list[dict]:
    """Normalize webhook payloads from various providers into standard events."""
    events = []

    if channel == "email":
        # SendGrid / Mailgun style events
        raw_events = payload.get("events", payload.get("event-data", []))
        if isinstance(raw_events, dict):
            raw_events = [raw_events]
        for ev in raw_events:
            event_type = _map_email_event(ev.get("event", ev.get("type", "")))
            if event_type:
                events.append({
                    "event_type": event_type,
                    "recipient_id": ev.get("recipient_id"),
                    "channel": "email",
                    "metadata": ev,
                    "timestamp": time.time(),
                })

    elif channel == "whatsapp":
        # WhatsApp Business API status updates
        statuses = payload.get("statuses", [])
        for status in statuses:
            event_type = _map_whatsapp_status(status.get("status", ""))
            if event_type:
                events.append({
                    "event_type": event_type,
                    "channel": "whatsapp",
                    "metadata": status,
                    "timestamp": time.time(),
                })

    elif channel == "sms":
        # Twilio-style SMS status callbacks
        event_type = _map_sms_status(payload.get("MessageStatus", payload.get("status", "")))
        if event_type:
            events.append({
                "event_type": event_type,
                "channel": "sms",
                "metadata": payload,
                "timestamp": time.time(),
            })

    return events


def _map_email_event(raw: str) -> str | None:
    """Map provider-specific email event names to standard types."""
    mapping = {
        "delivered": "delivered",
        "open": "opened", "opened": "opened",
        "click": "clicked", "clicked": "clicked",
        "bounce": "bounced", "bounced": "bounced", "hard_bounce": "bounced",
        "unsubscribe": "unsubscribed", "unsubscribed": "unsubscribed",
        "dropped": "bounced", "deferred": None,
    }
    return mapping.get(raw.lower())


def _map_whatsapp_status(raw: str) -> str | None:
    """Map WhatsApp status to standard event type."""
    mapping = {
        "sent": "sent", "delivered": "delivered",
        "read": "opened", "failed": "bounced",
    }
    return mapping.get(raw.lower())


def _map_sms_status(raw: str) -> str | None:
    """Map SMS status to standard event type."""
    mapping = {
        "sent": "sent", "delivered": "delivered",
        "undelivered": "bounced", "failed": "bounced",
    }
    return mapping.get(raw.lower())


# ── Public Unsubscribe Page ──────────────────────────────────────────

@router.get("/unsubscribe/{recipient_id}")
async def unsubscribe_page(recipient_id: int, request: Request):
    """Public unsubscribe page. Shows a confirmation and processes the opt-out.

    Sets consent_email=False on the contact and marks the recipient as
    unsubscribed. No authentication required – token-based via recipient_id.
    """
    from sqlalchemy.orm import Session
    from app.core.db import SessionLocal
    from app.core.models import CampaignRecipient, Campaign
    from app.core.contact_models import Contact
    from fastapi.responses import HTMLResponse

    db: Session = SessionLocal()
    try:
        recipient = db.query(CampaignRecipient).filter(
            CampaignRecipient.id == recipient_id
        ).first()

        if not recipient:
            return HTMLResponse(_unsubscribe_html(
                title="Link ungültig",
                message="Dieser Abmeldelink ist nicht mehr gültig.",
                success=False,
            ), status_code=404)

        # Get contact and campaign info
        contact = db.query(Contact).filter(Contact.id == recipient.contact_id).first()
        campaign = db.query(Campaign).filter(Campaign.id == recipient.campaign_id).first()

        contact_name = ""
        tenant_name = ""
        if contact:
            contact_name = contact.first_name or ""
            contact.consent_email = False
            logger.info("unsubscribe.contact_opted_out", contact_id=contact.id)

        if campaign:
            from app.core.models import Tenant
            tenant = db.query(Tenant).filter(Tenant.id == campaign.tenant_id).first()
            tenant_name = tenant.name if tenant else ""

        # Mark recipient as unsubscribed
        recipient.status = "unsubscribed"
        db.commit()

        # Push event to analytics queue
        _push_event({
            "event_type": "unsubscribed",
            "recipient_id": recipient_id,
            "contact_id": recipient.contact_id,
            "user_agent": request.headers.get("user-agent", ""),
            "ip_address": (request.headers.get("x-forwarded-for", "") or "").split(",")[0].strip(),
            "timestamp": time.time(),
        })

        return HTMLResponse(_unsubscribe_html(
            title="Erfolgreich abgemeldet",
            message=f"{contact_name}, du wurdest erfolgreich von E-Mail-Kampagnen von <strong>{tenant_name}</strong> abgemeldet. "
                    f"Du erhältst ab sofort keine weiteren Marketing-E-Mails mehr.",
            success=True,
        ))

    except Exception as e:
        logger.error("unsubscribe.error", error=str(e))
        return HTMLResponse(_unsubscribe_html(
            title="Fehler",
            message="Ein Fehler ist aufgetreten. Bitte versuche es später erneut.",
            success=False,
        ), status_code=500)
    finally:
        db.close()


def _unsubscribe_html(title: str, message: str, success: bool) -> str:
    """Render a styled unsubscribe confirmation page."""
    icon = "✓" if success else "✗"
    color = "#6ABF40" if success else "#E74C3C"
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{ margin:0; padding:0; background:#000; font-family:'Helvetica Neue',Arial,sans-serif; color:#fff; display:flex; align-items:center; justify-content:center; min-height:100vh; }}
    .card {{ background:#111; border-radius:12px; padding:48px 40px; max-width:480px; width:90%; text-align:center; border:1px solid #222; }}
    .icon {{ font-size:48px; color:{color}; margin-bottom:20px; }}
    h1 {{ font-size:24px; margin:0 0 16px; color:#fff; }}
    p {{ font-size:15px; line-height:1.7; color:#ccc; margin:0; }}
    p strong {{ color:#6ABF40; }}
    .footer {{ margin-top:32px; padding-top:20px; border-top:1px solid #333; font-size:12px; color:#666; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">{icon}</div>
    <h1>{title}</h1>
    <p>{message}</p>
    <div class="footer">Powered by ARIIA</div>
  </div>
</body>
</html>"""
